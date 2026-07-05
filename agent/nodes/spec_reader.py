from google.adk.workflow import node
from agent.state import AgentState
from agent.nodes.github_mcp_client import call_github_mcp
from agent.skills.spec_compliance_checker.spec_compliance_checker import extract_criteria
from agent.mock_utils import MOCK_MODE, load_mock_fixture

@node
async def spec_reader_node(state: AgentState) -> AgentState:
    """SpecReaderNode to retrieve acceptance criteria from linked issue."""
    import re
    # 1. Fetch PR files and construct diff in live mode if not already set
    if not MOCK_MODE and not state.pr_diff:
        print(f"Fetching PR files for PR #{state.pr_number} via GitHub MCP...")
        try:
            files_data = await call_github_mcp("get_pull_request_files", {
                "owner": state.repo_owner,
                "repo": state.repo_name,
                "pull_number": state.pr_number
            })
            files_list = files_data if isinstance(files_data, list) else files_data.get("files", [])
            diff_parts = []
            for f in files_list:
                filename = f.get("filename", "")
                patch = f.get("patch", "")
                diff_parts.append(f"--- a/{filename}\n+++ b/{filename}\n{patch}")
            state.pr_diff = "\n".join(diff_parts)
            print(f"Successfully constructed PR diff from MCP files list, length: {len(state.pr_diff)} characters.")
        except Exception as e:
            print(f"Error fetching PR files via MCP: {e}")

    # 2. Fetch PR details (title/body) if missing or manual fallback
    if not MOCK_MODE and (not state.pr_title or "Manual" in state.pr_title):
        print(f"Fetching PR details for PR #{state.pr_number} via GitHub MCP...")
        try:
            pr_data = await call_github_mcp("get_pull_request", {
                "owner": state.repo_owner,
                "repo": state.repo_name,
                "pull_number": state.pr_number
            })
            if isinstance(pr_data, dict):
                state.pr_title = pr_data.get("title", state.pr_title)
                state.pr_body = pr_data.get("body", state.pr_body)
                print(f"Loaded real PR title: '{state.pr_title}'")
        except Exception as e:
            print(f"Error fetching PR details via MCP: {e}")

    if not state.linked_issue_number:
        match = re.search(r"(?:fixes|closes|resolves|issue)\s*#?(\d+)", (state.pr_body or "") + " " + (state.pr_title or ""), re.IGNORECASE)
        if match:
            state.linked_issue_number = int(match.group(1))
            print(f"Parsed linked issue #{state.linked_issue_number} from PR title/body.")

    if not state.linked_issue_number and not MOCK_MODE:
        print("No linked issue found for this PR.")
        state.acceptance_criteria = []
        return state
        
    if MOCK_MODE:
        print(f"Fetching mock issue #{state.linked_issue_number}...")
        state.issue_title = "Mock Issue Title"
        state.issue_body = load_mock_fixture("issue_body") or ""
    else:
        print(f"Fetching issue #{state.linked_issue_number}...")
        try:
            issue_data = await call_github_mcp("get_issue", {
                "owner": state.repo_owner,
                "repo": state.repo_name,
                "issue_number": state.linked_issue_number
            })
            state.issue_title = issue_data.get("title", "")
            state.issue_body = issue_data.get("body", "")
        except Exception as e:
            print(f"Error calling GitHub MCP get_issue: {e}")
            state.acceptance_criteria = []
            return state

    # Parse criteria using our specialized skill
    state.acceptance_criteria = extract_criteria(state.issue_body)
    print(f"Extracted {len(state.acceptance_criteria)} acceptance criteria.")
    return state
