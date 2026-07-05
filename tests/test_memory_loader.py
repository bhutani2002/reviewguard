import pytest
import base64
import json
from datetime import datetime, timedelta
from agent.state import AgentState
from agent.nodes.memory_loader import memory_loader_node
import agent.nodes.memory_loader

@pytest.mark.asyncio
async def test_memory_loader_loads_decisions_and_stale_detection(monkeypatch):
    # Setup state
    state = AgentState(
        pr_number=1,
        pr_title="Fix retry logic",
        pr_body="Fixes #3",
        # Modify src/retry_handler.py which matches TD-OLD
        pr_diff="diff --git a/src/retry_handler.py b/src/retry_handler.py\n--- a/src/retry_handler.py\n+++ b/src/retry_handler.py\n@@ -1,1 +1,2 @@\n+self.max_attempts = 5",
        linked_issue_number=3,
        repo_owner="owner",
        repo_name="demo-paymentservice"
    )
    
    # Setup mock file response with an old decision (> 366 days)
    old_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    mock_decisions_data = {
        "version": "1.0",
        "decisions": [
            {
                "id": "TD-002",
                "date": "2026-04-02",
                "topic": "retry_max_attempts",
                "description": "Maximum retry attempts is 3.",
                "relevant_files": ["src/retry_handler.py"]
            },
            {
                "id": "TD-OLD",
                "date": old_date,
                "topic": "retry_max_attempts",
                "description": "Old config standard",
                "relevant_files": ["src/retry_handler.py"]
            }
        ]
    }
    
    async def mock_call_github_mcp(tool_name: str, arguments: dict) -> dict:
        if tool_name == "get_file_contents" and "team-decisions.json" in arguments.get("path", ""):
            encoded = base64.b64encode(json.dumps(mock_decisions_data).encode("utf-8")).decode("utf-8")
            return {"content": encoded, "encoding": "base64"}
        # Fall back to default mock client implementation
        from agent.nodes.github_mcp_client import call_github_mcp
        return await call_github_mcp(tool_name, arguments)
        
    monkeypatch.setattr(agent.nodes.memory_loader, "call_github_mcp", mock_call_github_mcp)
    
    # Run memory loader node
    state = await memory_loader_node._func(state)
    
    # Check that bootstrap decisions are loaded
    assert len(state.team_decisions) > 0
    # TD-002 (retry attempts) should be in there
    td2 = next(d for d in state.team_decisions if d.get("id") == "TD-002")
    assert td2["topic"] == "retry_max_attempts"
    
    # Verify comments mining loaded mock thread learnings
    assert len(state.pr_thread_learnings) > 0
    
    # Verify that TD-OLD is flagged as stale
    assert any(d.get("id") == "TD-OLD" for d in state.stale_decisions)
