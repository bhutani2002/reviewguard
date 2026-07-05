from google.adk.workflow import node
from agent.state import AgentState
from agent.nodes.github_mcp_client import call_github_mcp
from agent.mock_utils import MOCK_MODE

@node
async def security_alert_node(state: AgentState) -> AgentState:
    """SecurityAlertNode posts a security warning comment to the PR and requests changes."""
    findings_str = ""
    for idx, f in enumerate(state.security_findings, 1):
        findings_str += f"### {idx}. [{f['severity']}] {f['type']}\n- **Details:** {f['message']}\n"

    alert_body = f"""## 🚨 ReviewGuard Security Alert — PR #{state.pr_number}

**ReviewGuard has blocked this PR from verification due to critical security findings:**

{findings_str}

Please resolve all security findings and update the PR branch to re-run the verification agent.

---
*ReviewGuard v1.0 | Pre-LLM Security Screening Gate*
"""

    print("Posting security block warning to PR...")
    if MOCK_MODE:
        print(f"[MOCK MCP] Posted PR review: event=REQUEST_CHANGES")
        print(f"[MOCK MCP] Review body length: {len(alert_body)}")
        print(f"[MOCK MCP] Inline comments: 0")
    else:
        try:
            await call_github_mcp("create_pull_request_review", {
                "owner": state.repo_owner,
                "repo": state.repo_name,
                "pull_number": state.pr_number,
                "event": "REQUEST_CHANGES",
                "body": alert_body
            })
        except Exception as e:
            print(f"Error posting security alert review: {e}")

    state.security_alert_posted = True
    return state
