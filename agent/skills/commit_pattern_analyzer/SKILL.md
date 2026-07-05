---
name: commit_pattern_analyzer
description: Mines closed PR comment threads to extract team decisions and coding patterns.
---

# Commit Pattern Analyzer Skill

## Purpose

Mines closed PR comment threads to extract team decisions and coding patterns.
This is how ReviewGuard learns from actual human discussions, not just config files.

## Input

List of PR objects, each with: pr_number, pr_title, review_comments (list of comment bodies + dates)

## Output

List of extracted learnings:
{
  "topic": "short topic label",
  "decision": "accepted" | "rejected" | "standardized",
  "description": "what was decided in plain English",
  "confidence": "HIGH" | "MEDIUM",
  "first_seen_pr": pr_number,
  "last_seen_pr": pr_number,
  "frequency": count,
  "source": "pr_comment"
}

## Staleness signal

If a decision was last enforced >366 days ago AND the relevant files have changed
in the last 180 days: mark confidence as MEDIUM even if originally HIGH.
