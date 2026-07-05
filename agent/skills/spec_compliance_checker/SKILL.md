---
name: spec_compliance_checker
description: Extracts and normalizes acceptance criteria from issue bodies.
---

# Spec Compliance Checker Skill

## Purpose

Extracts and normalizes acceptance criteria from GitHub issue bodies.
Handles multiple formats: numbered lists, bullet points, checkbox lists (- [ ] format),
plain prose with "must", "should", "shall" language.

## When to use

Called by SpecReaderNode after fetching the raw issue body.
Input: raw issue markdown string
Output: list of normalized criterion strings

## Behavior

- Numbered list: extract each numbered item as one criterion
- Checkbox list: extract each checkbox item (ignore checked/unchecked state)
- Bullet list: extract each bullet as criterion if it sounds testable
- Prose: extract sentences containing "must", "should", "shall", "required", "needs to"
- Deduplicate. Normalize whitespace. Strip markdown formatting from text.
- Return empty list if no criteria found. Never invent criteria.
