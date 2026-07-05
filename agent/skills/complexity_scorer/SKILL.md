---
name: complexity_scorer
description: Scores changed files in a PR diff for code complexity indicators (cyclomatic complexity, nesting depth, function length).
---

# Complexity Scorer Skill

## Purpose

Scores changed files in a PR diff for code complexity indicators.
Provides concrete numbers for the CodeReviewNode to reason against.

## Metrics computed

- Cyclomatic complexity approximation: count of if/elif/else/for/while/try/except/and/or
- Nesting depth: maximum indentation depth in the file
- Function length: lines per function/method
- File length: total lines

## When to use

Called by CodeReviewNode before the LLM review prompt.
Input: dict of {filename: file_content} for changed files
Output: dict of {filename: {cyclomatic, max_nesting, avg_function_length, total_lines}}

## Thresholds (flag if exceeded)

- cyclomatic > 10: flag as HIGH complexity
- max_nesting > 4: flag as DEEP nesting
- avg_function_length > 50: flag as LONG functions
- total_lines > 300: flag as LARGE file
