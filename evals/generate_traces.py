#!/usr/bin/env python3
"""
Evaluation trace generator.
Runs all 4 scenarios in mock mode and writes results to artifacts/traces/.
Usage: make eval-traces
"""
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime

os.environ["REVIEWGUARD_MOCK"] = "true"

DATASETS = [
    "evals/datasets/good_pr.json",
    "evals/datasets/partial_pr.json",
    "evals/datasets/injection_pr.json",
    "evals/datasets/secret_leak_pr.json",
]

Path("artifacts/traces").mkdir(parents=True, exist_ok=True)


async def run_scenario(path: str) -> dict:
    with open(path) as f:
        scenario = json.load(f)

    os.environ["REVIEWGUARD_MOCK_SCENARIO"] = path

    # Import here to pick up environment variables correctly
    from agent.state import AgentState
    from agent.agent import root_agent

    state = AgentState(
        pr_number=scenario["input"]["pr_number"],
        pr_title=scenario["input"]["pr_title"],
        pr_body=scenario["input"]["pr_body"],
        pr_diff="",
        linked_issue_number=scenario["input"].get("linked_issue_number"),
        repo_owner=scenario["input"]["repo_owner"],
        repo_name=scenario["input"]["repo_name"],
    )

    try:
        await root_agent.run(state)
        status = "completed"
        error = None
    except Exception as e:
        status = "error"
        error = str(e)

    expected = scenario["expected_outcome"]
    if expected == "security_blocked":
        passed = not state.security_passed
    elif expected == "no_blockers":
        passed = state.security_passed and len(state.merge_blockers) == 0
    elif expected == "merge_blocker_found":
        expected_count = scenario.get("expected_merge_blockers", 1)
        passed = state.security_passed and len(state.merge_blockers) >= expected_count
    else:
        passed = False

    return {
        "scenario_id": scenario["scenario_id"],
        "run_at": datetime.now().isoformat(),
        "status": status,
        "error": error,
        "expected_outcome": expected,
        "passed": passed,
        "actual": {
            "security_passed": state.security_passed,
            "merge_blockers": len(state.merge_blockers),
            "auto_posted": len(state.auto_post_findings),
            "hitl_escalations": len(state.hitl_escalations),
        },
    }


async def main():
    print("\n[EVAL] ReviewGuard Evaluation Suite")
    print("=" * 45)
    traces = []
    passed = 0

    for path in DATASETS:
        trace = await run_scenario(path)
        traces.append(trace)
        icon = "PASS" if trace["passed"] else "FAIL"
        print(f"  [{icon}]  {trace['scenario_id']}")
        if trace["passed"]:
            passed += 1

    output = {
        "generated_at": datetime.now().isoformat(),
        "total": len(traces),
        "passed": passed,
        "failed": len(traces) - passed,
        "traces": traces,
    }

    out_path = "artifacts/traces/generated_traces.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults: {passed}/{len(traces)} passed")
    print(f"Traces:  {out_path}\n")

    if passed < len(traces):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
