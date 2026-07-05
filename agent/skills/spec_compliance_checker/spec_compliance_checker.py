import re
from typing import List

def clean_markdown(text: str) -> str:
    """Strip basic markdown formatting and clean whitespace."""
    # Strip links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Strip backticks
    text = text.replace('`', '')
    # Strip bold/italic stars
    text = re.sub(r'\*+', '', text)
    # Clean whitespace
    return text.strip()

def extract_criteria(issue_body: str) -> List[str]:
    """Extract and normalize acceptance criteria from an issue body."""
    if not issue_body:
        return []

    criteria = []
    lines = issue_body.splitlines()
    in_notes = False
    
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
            
        # Ignore Notes section if it starts with ## Notes
        if line_strip.lower().startswith("## notes"):
            in_notes = True
            continue
        if in_notes and line_strip.startswith("#"):
            in_notes = False  # Exit notes if new heading starts

        if in_notes:
            continue

        # 1. Checkbox list item: - [ ] or - [x]
        checkbox_match = re.match(r'^[-\*\+]\s+\[[ xX]?\]\s+(.+)$', line_strip)
        if checkbox_match:
            content = checkbox_match.group(1)
            criteria.append(clean_markdown(content))
            continue

        # 2. Numbered list item: 1. or 1)
        numbered_match = re.match(r'^\d+[\.\)]\s+(.+)$', line_strip)
        if numbered_match:
            content = numbered_match.group(1)
            criteria.append(clean_markdown(content))
            continue

        # 3. Bullet list item (excluding checkboxes)
        bullet_match = re.match(r'^[-\*\+]\s+(.+)$', line_strip)
        if bullet_match:
            content = bullet_match.group(1)
            # Filter bullet points that sound like testable criteria or statements
            # Lowercase keywords for validation
            content_lower = content.lower()
            if any(kw in content_lower for kw in ["must", "should", "shall", "required", "needs to", "validate", "support", "test"]):
                criteria.append(clean_markdown(content))
            elif len(content.split()) >= 3:  # fallback: any descriptive bullet points
                criteria.append(clean_markdown(content))
            continue

        # 4. Plain prose sentences containing key verbs
        sentences = re.split(r'(?<=[.!?])\s+', line_strip)
        for sentence in sentences:
            sent_lower = sentence.lower()
            if any(kw in sent_lower for kw in ["must", "should", "shall", "required", "needs to"]):
                # Ensure it's not a heading or extremely short phrase
                if not sentence.startswith("#") and len(sentence.split()) >= 4:
                    criteria.append(clean_markdown(sentence))

    # Deduplicate while preserving order
    seen = set()
    unique_criteria = []
    for c in criteria:
        if c and c not in seen:
            seen.add(c)
            unique_criteria.append(c)

    return unique_criteria
