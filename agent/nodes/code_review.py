import os
import json
import base64
from google.adk.workflow import node
from agent.state import AgentState
from agent.llm_client import generate_text
from agent.nodes.github_mcp_client import call_github_mcp
from agent.skills.complexity_scorer.complexity_scorer import score_complexity
from agent.mock_utils import MOCK_MODE, load_mock_fixture

# Mock findings for Issue #15/16 in the demo PR
MOCK_REVIEW_FINDINGS = [
    {
        "finding": "Hardcoded TTL value 86400 used. Configurable TTL should come from Config.IDEMPOTENCY_CACHE_TTL_SECONDS.",
        "confidence": "HIGH",
        "file": "src/payment_processor.py",
        "line": 46,
        "reasoning": "Violates TD-001 and TD-006: config values must come from config.py or environment variables.",
        "category": "maintainability",
        "suppressed_by_memory": False,
        "memory_reference": None
    },
    {
        "finding": "max_attempts is hardcoded to 5, which violates team standard of 3.",
        "confidence": "HIGH",
        "file": "src/payment_processor.py",
        "line": 85,
        "reasoning": "Violates TD-002: Maximum retry attempts is standardized to 3 and must come from Config.",
        "category": "correctness",
        "suppressed_by_memory": False,
        "memory_reference": None
    },
    {
        "finding": "Consider implementing PaymentProcessor as a Singleton to save resources.",
        "confidence": "MEDIUM",
        "file": "src/payment_processor.py",
        "line": 35,
        "reasoning": "A reviewer suggested singleton pattern, but this is already settled by the team.",
        "category": "style",
        "suppressed_by_memory": True,
        "memory_reference": "TD-003"
    }
]

def parse_changed_files(pr_diff: str) -> list:
    """Extract filenames from a diff string."""
    files = []
    for line in pr_diff.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:])
    return files

def extract_file_content(file_data) -> str:
    """Safely extract and decode content from call_github_mcp get_file_contents response."""
    if not file_data:
        return ""
    if isinstance(file_data, str):
        return file_data
    if isinstance(file_data, dict):
        if "content" in file_data:
            content_b64 = file_data.get("content", "")
            try:
                clean_b64 = "".join(content_b64.split())
                missing_padding = len(clean_b64) % 4
                if missing_padding:
                    clean_b64 += "=" * (4 - missing_padding)
                return base64.b64decode(clean_b64).decode("utf-8")
            except Exception:
                pass
        if "text" in file_data:
            return file_data.get("text", "")
        # Fallback: if it's already a parsed JSON dictionary, serialize it back to string
        try:
            return json.dumps(file_data)
        except Exception:
            pass
    return ""

@node
async def code_review_node(state: AgentState) -> AgentState:
    """CodeReviewNode to check code quality and memory cross-references."""
    changed_files = parse_changed_files(state.pr_diff)
    
    # 1. Fetch changed files contents and run complexity scorer
    file_contents = {}
    if MOCK_MODE:
        state.complexity_report = load_mock_fixture("complexity_report")
    else:
        for filepath in changed_files:
            # Skip workflow files and non-Python source files to avoid noise
            if filepath.startswith(".github/") or not filepath.endswith(".py"):
                continue
            try:
                file_data = await call_github_mcp("get_file_contents", {
                    "owner": state.repo_owner,
                    "repo": state.repo_name,
                    "path": filepath,
                    "branch": state.pr_branch
                })
                content_str = extract_file_content(file_data)
                if content_str:
                    file_contents[filepath] = content_str
            except Exception as e:
                print(f"Warning: Could not fetch {filepath} contents: {e}")

        if file_contents:
            state.complexity_report = score_complexity(file_contents)
        else:
            state.complexity_report = {}

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if MOCK_MODE or not api_key or api_key.startswith("your_") or api_key == "dummy":
        print("[MOCK LLM] Returning mock code review findings.")
        state.review_findings = MOCK_REVIEW_FINDINGS
        return state

    # 2. Run LLM review with fallback LLMs
    print("Running code review analysis with fallback LLMs...")
    
    # Format team decisions and stale decisions for prompt context
    team_decisions_summary = json.dumps([
        {
            "id": d.get("id"),
            "topic": d.get("topic"),
            "decision": d.get("decision"),
            "description": d.get("description"),
            "relevant_files": d.get("relevant_files")
        } for d in state.team_decisions if d.get("id") not in [s.get("id") for s in state.stale_decisions]
    ], indent=2)

    stale_decisions_summary = json.dumps([
        {
            "id": s.get("id"),
            "topic": s.get("topic"),
            "description": s.get("description")
        } for s in state.stale_decisions
    ], indent=2)

    prompt = f"""You are a senior code reviewer. Review this PR diff.

Team context (decisions already made — do NOT re-raise these):
{team_decisions_summary}

Potentially stale decisions (flag if relevant, don't suppress):
{stale_decisions_summary}

Complexity report:
{json.dumps(state.complexity_report, indent=2)}

PR diff:
{state.pr_diff}

Return a JSON array of findings. Each finding:
{{
  "finding": "specific, actionable description of the issue",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "file": "filename",
  "line": line_number_or_null,
  "reasoning": "why this is a problem, with reference to the diff",
  "category": "correctness" | "security" | "performance" | "style" | "maintainability",
  "suppressed_by_memory": false,
  "memory_reference": null
}}

Rules:
- Do NOT review, flag, or report findings in any files inside the '.github/' folder (such as workflow YAML files) or any non-source files. Only review actual Python source code files.
- Do NOT flag missing imports, missing implementations, or class definitions that are not shown in the diff. Assume they exist elsewhere in the repository and are imported correctly.
- Do NOT flag anything covered by team_decisions_summary (they are suppressed/already decided).
- If a finding relates to a potentially stale decision, include it with confidence MEDIUM and note the stale decision in memory_reference.
- Be specific. Reference actual lines, variable names, function names from the diff.
- Do not invent issues not visible in the diff.
- Maximum 10 findings. Prioritize by severity.
"""
    try:
        response_text = await generate_text(prompt, role="final", response_mime_type="application/json")
        findings = json.loads(response_text)
        
        if not isinstance(findings, list):
            if isinstance(findings, dict):
                findings = findings.get("findings", findings.get("issues", [findings]))
            else:
                findings = []
        
        # 3. Cross-reference findings with team decisions to double check suppressions
        clean_findings = []
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            finding_file = finding.get("file", "") or ""
            # Strictly ignore any findings related to workflow configuration files or non-Python files
            if finding_file.startswith(".github/") or (finding_file and not finding_file.endswith(".py")):
                continue
                
            finding_text = finding.get("finding", "").lower()
            
            for decision in state.team_decisions:
                decision_topic = decision.get("topic", "").replace("_", " ").lower()
                decision_desc = decision.get("description", "").lower()
                
                # Check if this finding tries to re-litigate a decision
                if (decision_topic in finding_text or any(kw in finding_text for kw in decision.get("keywords", []))) \
                   and decision.get("id") not in [s.get("id") for s in state.stale_decisions]:
                    
                    # If it is a VIOLATION of a rejected practice (like hardcoding a key),
                    # it should not be suppressed. If it is re-litigating a topic (like singleton), it is suppressed.
                    if decision.get("decision") == "rejected" and "consider" in finding_text:
                        finding["suppressed_by_memory"] = True
                        finding["memory_reference"] = decision.get("id")
                        break
            clean_findings.append(finding)
        state.review_findings = clean_findings
    except Exception as e:
        print(f"Error calling LLM in code_review_node: {e}")
        state.review_findings = MOCK_REVIEW_FINDINGS

    return state
