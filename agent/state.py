from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class AgentState:
    # Input
    pr_number: int
    pr_title: str
    pr_body: str
    pr_diff: str
    linked_issue_number: Optional[int]
    repo_owner: str
    repo_name: str
    pr_branch: str = "main"

    # Populated by SecurityScreenNode
    security_passed: bool = False
    security_findings: List[Dict[str, Any]] = field(default_factory=list)

    # Populated by SpecReaderNode
    acceptance_criteria: List[str] = field(default_factory=list)
    issue_title: str = ""
    issue_body: str = ""

    # Populated by MemoryLoaderNode
    team_decisions: List[Dict[str, Any]] = field(default_factory=list)
    pr_thread_learnings: List[Dict[str, Any]] = field(default_factory=list)
    stale_decisions: List[Dict[str, Any]] = field(default_factory=list)

    # Populated by SpecComplianceNode
    spec_results: List[Dict[str, Any]] = field(default_factory=list)
    # each dict: {criterion, status, confidence, evidence, line_ref}
    # status: SATISFIED | PARTIAL | MISSING

    # Populated by CodeReviewNode
    review_findings: List[Dict[str, Any]] = field(default_factory=list)
    # each dict: {finding, confidence, file, line, reasoning, category, suppressed_by_memory, memory_reference}
    complexity_report: Dict[str, Any] = field(default_factory=dict)

    # Populated by ConfidenceRouterNode
    auto_post_findings: List[Dict[str, Any]] = field(default_factory=list)
    hitl_escalations: List[Dict[str, Any]] = field(default_factory=list)
    merge_blockers: List[Dict[str, Any]] = field(default_factory=list)

    # Populated by AuditLogNode
    audit_markdown: str = ""
    audit_file_path: str = ""

    # Diagnostics and Tracking
    run_id: str = ""
    trace_logs: List[Dict[str, Any]] = field(default_factory=list)

    # Node-specific tracking flags and outputs
    security_alert_posted: bool = False
    hitl_issue_number: Optional[int] = None
    audit_file_url: str = ""
    pr_review_id: Optional[str] = None
