import os
import json
import base64
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession

# Mock database of issues and PRs for local testing/evaluations
MOCK_ISSUES = {
    15: {
        "title": "Add idempotency key support to payment processor",
        "body": """Currently, duplicate payment requests (network retries, double-clicks) can result in
duplicate charges. We need idempotency key support.

## Acceptance Criteria
1. Every payment request must accept an `idempotency_key` string parameter
2. Duplicate requests with the same key within the TTL window must return the cached response
3. `idempotency_key` must be validated — must be a non-empty string, max 64 chars
4. Cache TTL must be configurable via Config (not hardcoded)
5. If no idempotency_key is provided, generate a UUID automatically
6. Unit tests must cover: duplicate key returns same result, expired key allows re-processing"""
    },
    16: {
        "title": "Add jitter to retry handler to prevent thundering herd",
        "body": """Under high load, synchronized retries from multiple clients hit the payment gateway
at the same time, causing cascade failures. Adding random jitter will spread the load.

## Acceptance Criteria
1. Add random jitter between 0ms and Config.RETRY_JITTER_MS to each retry delay
2. Max retry attempts must remain at 3 (per TD-002, this is a team standard)
3. Jitter amount must be configurable via Config.RETRY_JITTER_MS (default 50ms)
4. The jitter must be added AFTER computing the exponential delay, not instead of it
5. Existing retry tests must still pass
6. Add a test specifically for jitter: delay must vary between runs on same attempt number"""
    },
    1: {
        "title": "Standardize all config values through config.py",
        "body": """All services are currently using hardcoded timeout and retry values scattered across files.
This is causing inconsistent behavior across environments.

Acceptance Criteria:
- [ ] Create a central Config class in config.py
- [ ] All timeout values must read from environment variables via Config
- [ ] All retry parameters must read from Config
- [ ] No numeric literals for business logic parameters anywhere in src/
- [ ] Existing tests must pass"""
    },
    3: {
        "title": "Define and enforce retry policy for payment processor",
        "body": """Currently each service implements its own retry logic inconsistently. We need a standard.

Acceptance Criteria:
- [ ] Centralize retry logic in RetryHandler class
- [ ] Maximum 3 retry attempts
- [ ] Exponential backoff starting at 100ms
- [ ] Maximum delay capped at 2000ms
- [ ] All services must use RetryHandler, no custom retry loops"""
    },
    8: {
        "title": "Evaluate singleton pattern for PaymentProcessor to reduce instantiation overhead",
        "body": "PaymentProcessor is being instantiated per-request. Evaluate if singleton would help."
    }
}

MOCK_PR_COMMENTS = {
    1: [
        {"body": "Hardcoded 30 here will bite us in staging where we use different timeouts. Move to Config.", "created_at": "2026-03-18T10:00:00Z"},
        {"body": "Good catch. Fixed — all values now in Config class.", "created_at": "2026-03-18T10:30:00Z"},
        {"body": "Approving. Let's make this a team rule going forward — no hardcoded values in src/.", "created_at": "2026-03-18T11:00:00Z"}
    ],
    3: [
        {"body": "Why 5 attempts? Let's do 3 to be safe.", "created_at": "2026-04-02T14:00:00Z"},
        {"body": "Load testing showed 5 attempts during an outage caused thundering herd. 3 is enough with the backoff.", "created_at": "2026-04-02T14:15:00Z"},
        {"body": "Makes sense. 3 it is. Let's document this decision somewhere.", "created_at": "2026-04-02T14:30:00Z"},
        {"body": "Added to team-decisions.json as TD-002", "created_at": "2026-04-02T14:45:00Z"}
    ],
    8: [
        {"body": "I tried this locally — it breaks 6 tests because they share state. Our parallel test suite can't handle it.", "created_at": "2026-05-14T09:00:00Z"},
        {"body": "Agreed, reverting. DI is the right approach here.", "created_at": "2026-05-14T09:15:00Z"},
        {"body": "Let's add this to team decisions so we don't revisit it.", "created_at": "2026-05-14T09:30:00Z"}
    ]
}

MOCK_PRS = [
    {"number": 1, "title": "Standardize all config values through config.py", "state": "closed"},
    {"number": 3, "title": "Define and enforce retry policy for payment processor", "state": "closed"},
    {"number": 8, "title": "Evaluate singleton pattern for PaymentProcessor", "state": "closed"}
]

MOCK_DECISIONS_JSON = """{
  "version": "1.0",
  "last_updated": "2026-06-15",
  "repo": "demo-paymentservice",
  "decisions": [
    {
      "id": "TD-001",
      "date": "2026-03-18",
      "topic": "hardcoded_config_values",
      "decision": "rejected",
      "severity": "merge_blocker",
      "description": "All configurable values must come from config.py or environment variables. Hardcoded values anywhere else are a merge blocker without exception.",
      "rationale": "Had a production incident where timeout was hardcoded to 30s in one service and 60s in another, causing inconsistent behavior. Config.py is the single source of truth.",
      "pr_reference": "PR #1",
      "raised_by": "raag",
      "relevant_files": ["src/config.py", "src/*.py"],
      "keywords": ["hardcoded", "magic number", "literal value", "constant"],
      "source": "json_bootstrap"
    },
    {
      "id": "TD-002",
      "date": "2026-04-02",
      "topic": "retry_max_attempts",
      "decision": "standardized",
      "severity": "merge_blocker",
      "description": "Maximum retry attempts is 3. This value must come from Config.RETRY_MAX_ATTEMPTS. Any PR setting a different value or hardcoding attempts is a merge blocker.",
      "rationale": "Agreed after load testing showed 5 attempts caused thundering herd during outages. 3 with exponential backoff is the sweet spot for our SLAs.",
      "pr_reference": "PR #3",
      "raised_by": "raag",
      "relevant_files": ["src/retry_handler.py"],
      "keywords": ["retry", "attempts", "max_retries", "retry_count"],
      "source": "json_bootstrap"
    },
    {
      "id": "TD-003",
      "date": "2026-05-14",
      "topic": "singleton_pattern",
      "decision": "rejected",
      "severity": "suggestion",
      "description": "Do not use singleton pattern for service classes. Use dependency injection instead.",
      "rationale": "Singletons cause test isolation issues in our parallel pytest suite. DI allows proper mocking.",
      "pr_reference": "PR #8",
      "raised_by": "raag",
      "relevant_files": ["src/*.py", "tests/*.py"],
      "keywords": ["singleton", "global instance", "module-level instance"],
      "source": "json_bootstrap"
    },
    {
      "id": "TD-004",
      "date": "2026-05-28",
      "topic": "exception_handling_style",
      "decision": "standardized",
      "severity": "merge_blocker",
      "description": "All service exceptions must be wrapped in ServiceException (or its subclasses) with error_code and user_message fields. Raw exceptions (ValueError, RuntimeError, etc.) must never propagate to callers.",
      "rationale": "API consumers need consistent error shapes. Raw exceptions were leaking implementation details to clients.",
      "pr_reference": "PR #11",
      "raised_by": "raag",
      "relevant_files": ["src/exceptions.py", "src/*.py"],
      "keywords": [
        "raise ValueError",
        "raise RuntimeError",
        "raise Exception",
        "bare raise"
      ],
      "source": "json_bootstrap"
    },
    {
      "id": "TD-005",
      "date": "2026-06-10",
      "topic": "circuit_breaker_bypass",
      "decision": "rejected",
      "severity": "merge_blocker",
      "description": "The circuit breaker in PaymentProcessor must never be bypassed or removed. Any PR that removes the can_proceed() check or adds a flag to skip it is a merge blocker.",
      "rationale": "Had a cascading failure when the circuit breaker was commented out during debugging and accidentally merged. Cost us 45 minutes of downtime.",
      "pr_reference": "PR #18",
      "raised_by": "raag",
      "relevant_files": ["src/payment_processor.py"],
      "keywords": ["circuit breaker", "can_proceed", "skip_circuit", "bypass"],
      "source": "json_bootstrap"
    },
    {
      "id": "TD-006",
      "date": "2026-06-15",
      "topic": "idempotency_cache_implementation",
      "decision": "standardized",
      "severity": "suggestion",
      "description": "Idempotency cache TTL must come from Config.IDEMPOTENCY_CACHE_TTL_SECONDS. In-memory dict is acceptable for current scale. Redis migration planned for Q3.",
      "rationale": "Current load is <100 req/s. In-memory is fine. But TTL must be configurable so we can tune without deploys.",
      "pr_reference": "PR #21",
      "raised_by": "raag",
      "relevant_files": ["src/payment_processor.py"],
      "keywords": ["idempotency", "cache", "ttl", "86400", "cache_ttl"],
      "source": "json_bootstrap"
    }
  ]
}"""

async def call_github_mcp(tool_name: str, arguments: dict) -> dict:
    """Run the GitHub MCP server in a stdio subprocess and call a tool. Fall back to mock data if GITHUB_TOKEN is missing or dummy."""
    github_token = os.getenv("GITHUB_TOKEN")
    
    # Check if we should use mock data
    if not github_token or github_token.startswith("your_") or github_token == "dummy":
        arg_summary = {k: (v if k not in ("body", "content") else f"<str len {len(v)}>") for k, v in arguments.items()}
        print(f"[MOCK MCP] call_github_mcp: {tool_name} with {arg_summary}")
        
        if tool_name == "get_issue":
            num = int(arguments.get("issue_number", 0))
            issue = MOCK_ISSUES.get(num, {"title": "Mock Issue", "body": "No acceptance criteria specified."})
            return {"title": issue["title"], "body": issue["body"]}
            
        elif tool_name == "get_pull_request_comments":
            num = int(arguments.get("pull_number", 0))
            comments = MOCK_PR_COMMENTS.get(num, [])
            return {"comments": comments}
            
        elif tool_name == "list_pull_requests":
            return {"pull_requests": MOCK_PRS}
            
        elif tool_name == "get_file_contents":
            path = arguments.get("path")
            if "team-decisions.json" in path:
                encoded = base64.b64encode(MOCK_DECISIONS_JSON.encode("utf-8")).decode("utf-8")
                return {"content": encoded, "encoding": "base64"}
            else:
                encoded = base64.b64encode(b'{"learnings": []}').decode("utf-8")
                return {"content": encoded, "encoding": "base64"}
                
        elif tool_name == "create_or_update_file_contents":
            path = arguments.get("path")
            content = arguments.get("content")
            print(f"[MOCK MCP] Committed file to {path}. Content length: {len(content)}")
            # Write locally to reviewguard/review-artifacts for local inspection
            local_path = os.path.join(os.getcwd(), path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success", "path": path}
            
        elif tool_name == "create_pull_request_review":
            event = arguments.get("event")
            body = arguments.get("body")
            comments = arguments.get("comments", [])
            print(f"[MOCK MCP] Posted PR review: event={event}")
            print(f"[MOCK MCP] Review body length: {len(body)}")
            print(f"[MOCK MCP] Inline comments: {len(comments)}")
            return {"status": "success", "review_id": 99999}
            
        elif tool_name == "create_issue":
            title = arguments.get("title")
            body = arguments.get("body")
            print(f"[MOCK MCP] Created HITL Issue: {title}")
            return {"number": 101, "title": title, "body": body}
            
        else:
            return {}

    # Real MCP Server Call
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={
            **os.environ,
            "GITHUB_PERSONAL_ACCESS_TOKEN": github_token,
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.call_tool(tool_name, arguments)
            if not response.content:
                return {}
            
            text_data = response.content[0].text
            try:
                return json.loads(text_data)
            except json.JSONDecodeError:
                return {"text": text_data}
