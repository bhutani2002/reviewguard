from google.adk.workflow import node
from agent.state import AgentState

@node
def confidence_router_node(state: AgentState) -> AgentState:
    """ConfidenceRouterNode routes findings using pure, deterministic Python logic."""
    state.auto_post_findings = []
    state.hitl_escalations = []
    state.merge_blockers = []

    # Combine both spec sync results and code review findings
    all_findings = state.spec_results + state.review_findings

    for finding in all_findings:
        if finding.get("suppressed_by_memory"):
            # skip — logged in audit only
            continue
            
        confidence = finding.get("confidence", "LOW")
        status = finding.get("status")  # Spec sync field
        category = finding.get("category")  # Code review field

        # Check conditions
        if status in ("MISSING", "PARTIAL") or category == "security":
            if confidence == "HIGH":
                state.merge_blockers.append(finding)
                state.auto_post_findings.append(finding)
            elif confidence == "MEDIUM":
                state.auto_post_findings.append(finding)
            elif confidence == "LOW":
                state.hitl_escalations.append(finding)
        else:
            if confidence == "HIGH":
                state.auto_post_findings.append(finding)
            elif confidence == "MEDIUM":
                state.auto_post_findings.append(finding)
            elif confidence == "LOW":
                state.hitl_escalations.append(finding)

    print(f"Confidence Routing: {len(state.auto_post_findings)} auto-post, {len(state.hitl_escalations)} HITL, {len(state.merge_blockers)} blockers.")
    return state
