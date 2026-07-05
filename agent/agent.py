import os
import json
import asyncio
import httpx
import uuid
from datetime import datetime
from google.adk.workflow import Workflow, Edge
from google.adk.apps.app import App

from agent.state import AgentState
from agent.mock_utils import MOCK_MODE, load_mock_fixture
from agent.nodes.security_screen import security_screen_node
from agent.nodes.spec_reader import spec_reader_node
from agent.nodes.memory_loader import memory_loader_node
from agent.nodes.spec_compliance import spec_compliance_node
from agent.nodes.code_review import code_review_node
from agent.nodes.confidence_router import confidence_router_node
from agent.nodes.audit_log import audit_log_node
from agent.nodes.github_comment import github_comment_node
from agent.nodes.security_alert import security_alert_node

# ── Mock mode warning ──────────────────────────────────────────────────────────
if MOCK_MODE:
    print("[WARNING] ReviewGuard running in MOCK mode - using local fixtures")
    print("    Set REVIEWGUARD_MOCK=false to use real GitHub MCP and Gemini")

# Define CustomWorkflow to support direct state execution without Pydantic exceptions
class CustomWorkflow(Workflow):
    def run(self, *args, **kwargs):
        if "ctx" in kwargs or "node_input" in kwargs:
            return super().run(*args, **kwargs)
        # Direct run call: execute sequential node runner
        state = args[0] if args else kwargs.get("state")
        return custom_run(state)

# Define the ADK 2.0 Workflow graph
root_workflow = CustomWorkflow(
    name="reviewguard_workflow",
    edges=[
        ("START", security_screen_node, {"passed": spec_reader_node, "blocked": security_alert_node}),
        (spec_reader_node, memory_loader_node, spec_compliance_node, code_review_node, confidence_router_node, audit_log_node, github_comment_node)
    ]
)

async def execute_node_tracked(node_name: str, func, state: AgentState, is_async: bool = True) -> AgentState:
    """Wrapper to run a node, track metrics, and generate diagnostics on failure."""
    log_entry = {
        "node": node_name,
        "start_time": datetime.now().isoformat(),
        "status": "IN_PROGRESS"
    }
    state.trace_logs.append(log_entry)
    try:
        if is_async:
            state = await func(state)
        else:
            state = func(state)
        log_entry["status"] = "SUCCESS"
        log_entry["end_time"] = datetime.now().isoformat()
        return state
    except Exception as e:
        log_entry["status"] = "FAILED"
        log_entry["end_time"] = datetime.now().isoformat()
        log_entry["error"] = str(e)
        
        diag_path = f"artifacts/logs/reviewguard_diag_{state.run_id}.log"
        with open(diag_path, "w", encoding="utf-8") as f:
            import traceback
            f.write(f"=== ReviewGuard Trace Diagnostics ===\n")
            f.write(f"Run ID: {state.run_id}\n")
            f.write(f"Failed Node: {node_name}\n")
            f.write(f"Error Message: {str(e)}\n\n")
            f.write(f"=== Execution Trace History ===\n")
            f.write(json.dumps(state.trace_logs, indent=2))
            f.write(f"\n\n=== Traceback ===\n")
            traceback.print_exc(file=f)
            
        print(f"Error in node {node_name}! Diagnostic log saved to: {diag_path}")
        raise e

async def custom_run(state: AgentState) -> AgentState:
    """Sequential runner matching standard CLI workflow invocation."""
    if not state.run_id:
        state.run_id = str(uuid.uuid4())
        
    print(f"Starting ReviewGuard Agent Run ID: {state.run_id}")
    
    # Run Node 1: Security Screen
    state = await execute_node_tracked("SecurityScreenNode", security_screen_node._func, state, is_async=False)
    
    if not state.security_passed:
        print("Security screen BLOCKED. Running security_alert_node...")
        await execute_node_tracked("SecurityAlertNode", security_alert_node._func, state, is_async=True)
        print("Workflow terminated due to security block.")
        return state

    print("Security screen passed. Running SpecReaderNode...")
    state = await execute_node_tracked("SpecReaderNode", spec_reader_node._func, state, is_async=True)
    
    print("Running MemoryLoaderNode...")
    state = await execute_node_tracked("MemoryLoaderNode", memory_loader_node._func, state, is_async=True)
    
    print("Running SpecComplianceNode...")
    state = await execute_node_tracked("SpecComplianceNode", spec_compliance_node._func, state, is_async=True)
    
    print("Running CodeReviewNode...")
    state = await execute_node_tracked("CodeReviewNode", code_review_node._func, state, is_async=True)
    
    print("Running ConfidenceRouterNode...")
    state = await execute_node_tracked("ConfidenceRouterNode", confidence_router_node._func, state, is_async=False)
    
    print("Running AuditLogNode...")
    state = await execute_node_tracked("AuditLogNode", audit_log_node._func, state, is_async=True)
    
    print("Running GitHubCommentNode...")
    await execute_node_tracked("GitHubCommentNode", github_comment_node._func, state, is_async=True)
    
    print("ReviewGuard execution completed successfully.")
    return state

root_agent = root_workflow

# ── Playground / agents-cli discovery ────────────────────────────────────────
app = App(
    name="reviewguard",
    root_agent=root_agent,
)

async def fetch_pr_diff(owner: str, repo: str, pr_number: int, token: str) -> str:
    """Fetch the PR diff directly from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        return r.text

# ── GitHub Actions entrypoint ─────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    
    # Parse mock scenario if provided
    scenario_path = "evals/datasets/partial_pr.json"
    for i, arg in enumerate(sys.argv):
        if arg == "--mock-scenario" and i + 1 < len(sys.argv):
            scenario_path = sys.argv[i + 1]
            os.environ["REVIEWGUARD_MOCK_SCENARIO"] = scenario_path
            
    if MOCK_MODE:
        with open(scenario_path, "r", encoding="utf-8") as f:
            scenario = json.load(f)
        inp = scenario["input"]
        pr_num = inp["pr_number"]
        pr_title = inp["pr_title"]
        pr_body = inp.get("pr_body", "")
        repo_owner = inp["repo_owner"]
        repo_name = inp["repo_name"]
    else:
        pr_num = int(os.environ["PR_NUMBER"])
        pr_title = os.environ["PR_TITLE"]
        pr_body = os.environ.get("PR_BODY", "")
        repo_owner = os.environ["REPO_OWNER"]
        repo_name = os.environ["REPO_NAME"]
        pr_branch = os.environ.get("PR_BRANCH", "main")

    state = AgentState(
        pr_number=pr_num,
        pr_title=pr_title,
        pr_body=pr_body,
        pr_diff="",          # fetched by SpecReaderNode via GitHub MCP
        linked_issue_number=None,   # parsed from pr_body by SpecReaderNode
        repo_owner=repo_owner,
        repo_name=repo_name,
        pr_branch=pr_branch if not MOCK_MODE else "main",
        run_id=str(uuid.uuid4())
    )

    asyncio.run(root_agent.run(state))
