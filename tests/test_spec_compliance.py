import pytest
import os
from agent.state import AgentState
from agent.nodes.spec_compliance import spec_compliance_node

@pytest.mark.asyncio
async def test_spec_compliance_populates_results():
    state = AgentState(
        pr_number=1,
        pr_title="Add idempotency keys",
        pr_body="Fixes #15",
        pr_diff="diff --git a/src/payment_processor.py b/src/payment_processor.py\n+self._idempotency_ttl = 86400",
        linked_issue_number=15,
        repo_owner="owner",
        repo_name="demo-paymentservice"
    )
    # Mock loaded criteria
    state.acceptance_criteria = [
        "Every payment request must accept an idempotency_key string parameter",
        "idempotency_key must be validated — non-empty string, maximum 64 characters",
        "Cache TTL must be configurable via Config (not hardcoded)"
    ]
    
    # Run node
    state = await spec_compliance_node._func(state)
    
    assert len(state.spec_results) == 3
    # Check that the missing validation criterion is marked as MISSING
    missing_c = next(r for r in state.spec_results if "validation" in r["criterion"].lower() or "validated" in r["criterion"].lower())
    assert missing_c["status"] == "MISSING"
    
    # Check that hardcoded TTL is marked as PARTIAL
    partial_c = next(r for r in state.spec_results if "ttl" in r["criterion"].lower())
    assert partial_c["status"] == "PARTIAL"
    
    # Verify that they are routed to merge_blockers
    assert len(state.merge_blockers) >= 2
