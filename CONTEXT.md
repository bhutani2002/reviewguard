---
antigravity:
  workspace: reviewguard
  skills:
    - reviewguard-spec-check
    - complexity-scorer
    - commit-pattern-analyzer
  agent_module: agent.agent
  app_attribute: app
  playground_url: http://127.0.0.1:8080/dev-ui/?app=app
---

# ReviewGuard — Antigravity Project Context

## What this project is

ReviewGuard is a Google ADK 2.0 multi-agent PR verification system.
It is NOT a generic code review bot.
It is a confidence-aware, memory-backed agent that verifies PRs against spec AND team history.

## Architecture

7-node ADK 2.0 Workflow graph:
SecurityScreenNode -> SpecReaderNode -> MemoryLoaderNode -> SpecComplianceNode
-> CodeReviewNode -> ConfidenceRouterNode -> AuditLogNode

## Key constraints — always respect these

- SecurityScreenNode NEVER uses an LLM. Pure Python regex. Always runs first.
- SecurityScreenNode must detect: AWS keys, GitHub tokens, generic api keys, prompt injections, private IP addresses, .env files, and PII.
- ConfidenceRouterNode NEVER uses an LLM. Pure routing logic. Always runs last before audit.
- Memory comes from TWO sources: team-decisions.json (bootstrap) + PR comment threads (mined).
- The agent NEVER auto-approves PRs. Max action is request_changes or comment.
- The agent NEVER commits to main branch. Audit logs go to review-artifacts/ folder only.
- All GitHub operations go through GitHub MCP. No direct PyGitHub calls in node logic.
- [skip ci] must be appended to audit commits.
