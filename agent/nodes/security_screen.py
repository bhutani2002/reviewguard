import re
from google.adk.workflow import node
from agent.state import AgentState
from agent.mock_utils import MOCK_MODE, load_mock_fixture

# Regex patterns
SECRETS_PATTERNS = {
    "AWS Key": r"AKIA[0-9A-Z]{16}",
    "GitHub Token": r"gh[p|o|u|r]_[a-zA-Z0-9]{30,40}|github_pat_[a-zA-Z0-9_]{82}",
    "Generic API Key": r"(?:api_key|api-key|apikey|secret|password|passwd|token)\s*[:=]\s*[\'\"]([a-zA-Z0-9\-_\+\/=]{20,})[\'\"]"
}

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(?:any\s+|your\s+|my\s+)?previous\s+instructions",
    r"disregard\s+(?:any\s+|your\s+|my\s+)?system\s+prompt",
    r"you\s+are\s+now",
    r"forget\s+everything",
    r"new\s+persona"
]

PRIVATE_IP_PATTERN = r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|\b192\.168\.\d{1,3}\.\d{1,3}\b|\b172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}\b"

PII_PATTERNS = {
    "Email": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
    "Credit Card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "US SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "Phone Number": r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b"
}

@node
def security_screen_node(state: AgentState) -> AgentState:
    """Security screen node running pre-LLM checks."""
    if MOCK_MODE:
        state.pr_diff = load_mock_fixture("pr_diff")
        
    findings = []
    has_high_severity = False
    
    # 1. Check for .env file contents in diff
    if "a/.env" in state.pr_diff or "b/.env" in state.pr_diff or "a/environment.env" in state.pr_diff:
        findings.append({
            "type": "ENV_LEAK",
            "severity": "HIGH",
            "message": "PR contains environment variable file (.env) in diff."
        })
        has_high_severity = True

    # 2. Check for secrets
    for name, pattern in SECRETS_PATTERNS.items():
        matches = re.findall(pattern, state.pr_diff)
        if matches:
            findings.append({
                "type": "SECRET_LEAK",
                "severity": "HIGH",
                "message": f"PR contains hardcoded secrets matching {name} pattern."
            })
            has_high_severity = True

    # 3. Check for prompt injections in PR description/body and diff
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, state.pr_body, re.IGNORECASE) or re.search(pattern, state.pr_diff, re.IGNORECASE):
            findings.append({
                "type": "PROMPT_INJECTION",
                "severity": "HIGH",
                "message": "PR body or code diff contains potential prompt injection phrases."
            })
            has_high_severity = True

    # 4. Check for private IPs (LOW severity)
    matches_ip = re.findall(PRIVATE_IP_PATTERN, state.pr_diff)
    if matches_ip:
        findings.append({
            "type": "PRIVATE_IP",
            "severity": "LOW",
            "message": f"PR diff contains private IP addresses: {list(set(matches_ip))[:3]}"
        })

    # 5. Check for PII (LOW severity)
    for pii_name, pii_pattern in PII_PATTERNS.items():
        matches_pii = re.findall(pii_pattern, state.pr_diff)
        if matches_pii:
            findings.append({
                "type": "PII_LEAK",
                "severity": "LOW",
                "message": f"PR diff contains potential PII matching {pii_name} pattern."
            })

    state.security_findings = findings
    state.security_passed = not has_high_severity
    return state
