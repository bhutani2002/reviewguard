from google.adk.workflow import node
from agent.state import AgentState
from agent.nodes.github_mcp_client import call_github_mcp
from agent.skills.spec_compliance_checker.spec_compliance_checker import extract_criteria
from agent.mock_utils import MOCK_MODE, load_mock_fixture

@node
async def spec_reader_node(state: AgentState) -> AgentState:
    """SpecReaderNode to retrieve acceptance criteria from linked issue."""
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
