from datetime import datetime
from google.adk.workflow import node
from agent.state import AgentState
from agent.nodes.github_mcp_client import call_github_mcp
from agent.nodes.audit_log import clean_slug
from agent.mock_utils import MOCK_MODE

@node
async def github_comment_node(state: AgentState) -> AgentState:
    """GitHubCommentNode posts inline findings and a structured summary review comment to the PR."""
    
    # 1. Format Spec Compliance Checklist
    spec_summary = ""
    for r in state.spec_results:
        status = r.get("status")
        criterion = r.get("criterion")
        evidence = r.get("evidence", "")
        
        if status == "SATISFIED":
            spec_summary += f"✅ **SATISFIED (HIGH)** — {criterion} — *\"{evidence}\"*\n"
        elif status == "PARTIAL":
            spec_summary += f"⚠️ **PARTIAL (HIGH)** — {criterion} — *\"{evidence}\"* — **MERGE BLOCKER**\n"
        elif status == "MISSING":
            spec_summary += f"❌ **MISSING (HIGH)** — {criterion} — **MERGE BLOCKER**\n"

    # 2. Format Code Review Findings (general and inline ones)
    code_review_summary = ""
    inline_comments = []
    
    for f in state.auto_post_findings:
        filepath = f.get("file")
        line_num = f.get("line")
        finding = f.get("finding")
        
        # If it has filepath and line, add it as an inline PR comment
        if filepath and line_num:
            inline_comments.append({
                "path": filepath,
                "line": int(line_num),
                "body": f"**[ReviewGuard - {f.get('confidence')} Confidence]** {finding}\n\n*Reasoning: {f.get('reasoning', '')}*"
            })
        
        # Also list in the main PR comment summary
        file_info = f"{filepath}:{line_num}" if line_num else filepath
        code_review_summary += f"- **[{f.get('category', 'review')}]** `{file_info}`: {finding}\n"

    if not code_review_summary:
        code_review_summary = "_No code review issues auto-posted._\n"

    # 3. Format Memory Applied
    memory_summary = ""
    suppressed_findings = [f for f in state.review_findings if f.get("suppressed_by_memory")]
    for sf in suppressed_findings:
        memory_summary += f"- Suppressed style warning about `{sf.get('category')}` based on team decision **{sf.get('memory_reference')}**\n"
        
    for sd in state.stale_decisions:
        memory_summary += f"- ⚠️ **Flagged Stale Decision {sd.get('id')}**: Decided on {sd.get('date')} (over 366 days old). Please verify if still valid.\n"

    if not memory_summary:
        memory_summary = "_No memory standards triggered._\n"

    # 4. HITL Escalations
    hitl_summary = ""
    if state.hitl_escalations:
        hitl_summary = f"⚠️ **{len(state.hitl_escalations)} low-confidence findings escalated** → *Human Review Requested*\n"
    else:
        hitl_summary = "✅ No low-confidence findings to escalate.\n"

    # 5. Full Audit Log Link
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = clean_slug(state.pr_title)
    audit_link = f"review-artifacts/{date_str}/pr-{state.pr_number}-{slug}.md"

    # Compile the final PR comment body
    pr_comment_body = f"""## 🔍 ReviewGuard Analysis

### 📋 Spec Compliance
{spec_summary if spec_summary else "_No linked issue / criteria to check._"}

### 🔎 Code Review
{code_review_summary}

### 🧠 Memory Applied
{memory_summary}

### ⚠️ HITL Escalations
{hitl_summary}

### 📄 Full Audit Log
[`{audit_link}`](https://github.com/{state.repo_owner}/{state.repo_name}/blob/main/{audit_link})

---
*ReviewGuard v1.0 | Confidence-aware | Memory-backed | ADK 2.0*
"""

    # Post review to the PR using GitHub MCP
    event_type = "REQUEST_CHANGES" if state.merge_blockers else "COMMENT"
    print(f"Posting PR review comments via GitHub MCP (Verdict: {event_type})...")
    if MOCK_MODE:
        print(f"[MOCK MCP] Posted PR review: event={event_type}")
        print(f"[MOCK MCP] Review body length: {len(pr_comment_body)}")
        print(f"[MOCK MCP] Inline comments: {len(inline_comments)}")
        state.pr_review_id = "mock_review_123"
    else:
        try:
            res = await call_github_mcp("create_pull_request_review", {
                "owner": state.repo_owner,
                "repo": state.repo_name,
                "pull_number": state.pr_number,
                "event": event_type,
                "body": pr_comment_body,
                "comments": inline_comments
            })
            if isinstance(res, dict) and "id" in res:
                state.pr_review_id = str(res["id"])
        except Exception as e:
            print(f"Error posting pull request review: {e}")

    return state
