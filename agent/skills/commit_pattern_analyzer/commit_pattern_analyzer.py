import os
import json
from agent.llm_client import generate_text

MOCK_MINED_PATTERNS = [
    {
        "topic": "hardcoded_config_values",
        "decision": "rejected",
        "description": "All configurable values must come from config.py or environment variables.",
        "confidence": "HIGH",
        "first_seen_pr": 1,
        "last_seen_pr": 1,
        "frequency": 1,
        "source": "pr_comment"
    },
    {
        "topic": "retry_max_attempts",
        "decision": "standardized",
        "description": "Maximum retry attempts is 3. This value must come from Config.RETRY_MAX_ATTEMPTS.",
        "confidence": "HIGH",
        "first_seen_pr": 3,
        "last_seen_pr": 3,
        "frequency": 1,
        "source": "pr_comment"
    },
    {
        "topic": "singleton_pattern",
        "decision": "rejected",
        "description": "Do not use singleton pattern for service classes. Use dependency injection instead.",
        "confidence": "HIGH",
        "first_seen_pr": 8,
        "last_seen_pr": 8,
        "frequency": 1,
        "source": "pr_comment"
    }
]

async def analyze_commit_patterns(prs_data: list, existing_decisions: list) -> list:
    """Mines closed PR comments to extract team decisions and coding patterns."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key.startswith("your_") or api_key == "dummy":
        return MOCK_MINED_PATTERNS

    # Prepare input for LLM
    pr_comments_summary = []
    for pr in prs_data:
        comments = pr.get("comments", [])
        comment_bodies = [c["body"] for c in comments if "body" in c]
        if comment_bodies:
            pr_comments_summary.append({
                "pr_number": pr.get("number"),
                "pr_title": pr.get("title"),
                "comments": comment_bodies
            })

    if not pr_comments_summary:
        return []

    prompt = f"""You are mining GitHub PR comment threads to extract team coding standards, decisions, and patterns.

PR Comments Data:
{json.dumps(pr_comments_summary, indent=2)}

Return a JSON array of extracted standards/decisions. Each standard:
{{
  "topic": "short topic label (e.g. retry_max_attempts, singleton_pattern)",
  "decision": "accepted" | "rejected" | "standardized",
  "description": "what was decided in plain English",
  "confidence": "HIGH" | "MEDIUM",
  "first_seen_pr": pr_number,
  "last_seen_pr": pr_number,
  "frequency": count,
  "source": "pr_comment"
}}

Only extract items where a clear standard or consensus was expressed or agreed in the comments.
"""
    try:
        response_text = await generate_text(prompt, role="intermediate", response_mime_type="application/json")
        data = json.loads(response_text)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "learnings" in data:
            return data["learnings"]
        return MOCK_MINED_PATTERNS
    except Exception as e:
        print(f"Error calling LLM in commit_pattern_analyzer: {e}")
        return MOCK_MINED_PATTERNS
