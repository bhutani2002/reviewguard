import base64
import json
import fnmatch
from datetime import datetime
from google.adk.workflow import node
from agent.state import AgentState
from agent.nodes.github_mcp_client import call_github_mcp
from agent.skills.commit_pattern_analyzer.commit_pattern_analyzer import analyze_commit_patterns
from agent.mock_utils import MOCK_MODE, load_mock_fixture

def is_file_relevant(changed_files: list, patterns: list) -> bool:
    """Check if any changed file matches any of the relevant file glob patterns."""
    for file in changed_files:
        for pattern in patterns:
            # Normalize patterns like src/*.py -> src/config.py
            if fnmatch.fnmatch(file, pattern) or fnmatch.fnmatch(file, f"*/{pattern}"):
                return True
    return False

def parse_changed_files(pr_diff: str) -> list:
    """Extract filenames from a diff string."""
    files = []
    for line in pr_diff.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:])
    return files

@node
async def memory_loader_node(state: AgentState) -> AgentState:
    """MemoryLoaderNode loads bootstrap decisions and mines closed PR comments."""
    # 1. Load team-decisions.json (bootstrap memory)
    print("Loading team-decisions.json...")
    if MOCK_MODE:
        state.team_decisions = load_mock_fixture("team_decisions")
    else:
        try:
            file_data = await call_github_mcp("get_file_contents", {
                "owner": state.repo_owner,
                "repo": state.repo_name,
                "path": "review-artifacts/memory/team-decisions.json"
            })
            content_b64 = file_data.get("content", "")
            if content_b64:
                # Strip all whitespaces and fix base64 padding
                content_b64 = "".join(content_b64.split())
                missing_padding = len(content_b64) % 4
                if missing_padding:
                    content_b64 += "=" * (4 - missing_padding)
                content_str = base64.b64decode(content_b64).decode("utf-8")
                decisions_data = json.loads(content_str)
                state.team_decisions = decisions_data.get("decisions", [])
            else:
                state.team_decisions = []
        except Exception as e:
            print(f"Warning: Could not load team-decisions.json: {e}")
            state.team_decisions = []

    # 2. Fetch last 20 closed PRs and get comments for mining
    print("Fetching closed PRs for memory mining...")
    prs_with_comments = []
    if MOCK_MODE:
        prs_with_comments = load_mock_fixture("closed_pr_comments")
    else:
        try:
            prs_data = await call_github_mcp("list_pull_requests", {
                "owner": state.repo_owner,
                "repo": state.repo_name,
                "state": "closed",
                "per_page": 20
            })
            # The tool can return a list directly or a dict
            prs_list = prs_data if isinstance(prs_data, list) else prs_data.get("pull_requests", [])
            
            for pr in prs_list:
                pr_num = pr.get("number")
                comments_data = await call_github_mcp("get_pull_request_comments", {
                    "owner": state.repo_owner,
                    "repo": state.repo_name,
                    "pull_number": pr_num
                })
                comments = comments_data if isinstance(comments_data, list) else comments_data.get("comments", [])
                prs_with_comments.append({
                    "number": pr_num,
                    "title": pr.get("title", ""),
                    "comments": comments
                })
        except Exception as e:
            print(f"Warning: Could not fetch closed PRs/comments: {e}")

    # Mine patterns from PR comment threads
    print("Mining PR comments for team decisions...")
    mined_learnings = await analyze_commit_patterns(prs_with_comments, state.team_decisions)
    state.pr_thread_learnings = mined_learnings

    # Load and update pattern-history.json
    if MOCK_MODE:
        print("[MOCK] Skipped updating pattern-history.json in mock mode.")
    else:
        print("Loading pattern-history.json from repo...")
        pattern_history = []
        sha = None
        try:
            history_data = await call_github_mcp("get_file_contents", {
                "owner": state.repo_owner,
                "repo": state.repo_name,
                "path": "review-artifacts/memory/pattern-history.json"
            })
            content_b64 = history_data.get("content", "")
            sha = history_data.get("sha")
            if content_b64:
                # Strip all whitespaces and fix base64 padding
                content_b64 = "".join(content_b64.split())
                missing_padding = len(content_b64) % 4
                if missing_padding:
                    content_b64 += "=" * (4 - missing_padding)
                content_str = base64.b64decode(content_b64).decode("utf-8")
                history_json = json.loads(content_str)
                pattern_history = history_json.get("mined_patterns", [])
        except Exception as e:
            print(f"Warning: Could not load pattern-history.json: {e}")

        # Find new mined patterns
        existing_patterns_topics = {p.get("topic") for p in pattern_history}
        new_patterns_added = False
        
        for learning in mined_learnings:
            if learning.get("topic") not in existing_patterns_topics:
                pat_id = f"MP-{len(pattern_history) + 1:03d}"
                new_pattern = {
                    "pattern_id": pat_id,
                    "topic": learning.get("topic"),
                    "description": learning.get("description"),
                    "confidence": learning.get("confidence", "MEDIUM"),
                    "frequency": learning.get("frequency", 1),
                    "source_prs": [learning.get("first_seen_pr") or 1],
                    "status": "active"
                }
                pattern_history.append(new_pattern)
                new_patterns_added = True

        # If new patterns were added, commit the updated pattern-history.json
        if new_patterns_added:
            print("Writing updated pattern-history.json to repo...")
            history_payload = {
                "version": "1.0",
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "mined_patterns": pattern_history
            }
            payload_str = json.dumps(history_payload, indent=2)
            try:
                await call_github_mcp("create_or_update_file_contents", {
                    "owner": state.repo_owner,
                    "repo": state.repo_name,
                    "path": "review-artifacts/memory/pattern-history.json",
                    "content": payload_str,
                    "message": "chore: update mined pattern history [skip ci]",
                    "sha": sha
                })
            except Exception as e:
                print(f"Warning: Could not commit updated pattern-history.json: {e}")

    # Merge mined learnings into team decisions (if they don't already exist)
    existing_topics = {d.get("topic") for d in state.team_decisions}
    for learning in mined_learnings:
        if learning.get("topic") not in existing_topics:
            state.team_decisions.append(learning)

    # 3. Staleness checks
    changed_files = parse_changed_files(state.pr_diff)
    stale_decisions = []
    
    current_date = datetime.now()
    for decision in state.team_decisions:
        dec_date_str = decision.get("date")
        if not dec_date_str:
            continue
            
        try:
            dec_date = datetime.strptime(dec_date_str, "%Y-%m-%d")
            days_old = (current_date - dec_date).days
            
            # If decision is > 366 days old (or for testing/demo purposes, > 30 days old to show functionality)
            # We check > 366 days as strict requirement, but let's check both or add support for 366
            is_old = days_old > 366
            
            # Check if relevant files have changed in current PR
            relevant_patterns = decision.get("relevant_files", [])
            if is_old and is_file_relevant(changed_files, relevant_patterns):
                stale_decisions.append(decision)
        except Exception as date_err:
            print(f"Warning: Could not parse date {dec_date_str}: {date_err}")

    state.stale_decisions = stale_decisions
    print(f"Memory loaded: {len(state.team_decisions)} total decisions, {len(state.stale_decisions)} flagged as stale.")
    return state
