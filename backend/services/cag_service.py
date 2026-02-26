"""CAG (Context-Augmented Generation) service.

Loads all 240 content descriptors into LLM context for semantic matching.
"""

import json

from sqlalchemy.orm import Session

from backend.db.models import ContentDescriptor


def load_all_descriptors(db: Session) -> list[dict]:
    """Load all content descriptors for CAG context."""
    rows = (
        db.query(ContentDescriptor)
        .order_by(ContentDescriptor.year_level_code, ContentDescriptor.strand_title)
        .all()
    )
    return [
        {
            "code": r.code,
            "text": r.text,
            "year_level_code": r.year_level_code,
            "strand_title": r.strand_title,
        }
        for r in rows
    ]


def build_cag_prompt(topic: str, year_level: str, strand: str, descriptors: list[dict]) -> str:
    """Build the CAG matching prompt with all descriptors in context."""
    descriptor_text = "\n".join(
        f"- [{d['code']}] ({d['year_level_code']} / {d['strand_title']}): {d['text']}"
        for d in descriptors
    )

    return f"""You are a curriculum matching expert for the Australian Mathematics Curriculum (ACARA v9).

A teacher wants to teach: "{topic}"
Year Level preference: {year_level}
Strand preference: {strand}

Below are ALL 240 content descriptors from the ACARA v9 Mathematics curriculum.
Find the 3-5 most relevant descriptors that match the teacher's topic.

CONTENT DESCRIPTORS:
{descriptor_text}

Return a JSON array of matches. Each match must have:
- "code": the descriptor code (e.g., "AC9M5N06")
- "text": the full descriptor text
- "year_level": the year level code
- "strand": the strand title
- "confidence": "high", "medium", or "low"
- "reason": brief explanation of why this matches

Prioritise descriptors from the requested year level and strand, but include relevant
descriptors from nearby year levels if they are a strong match.

Return ONLY valid JSON, no markdown formatting."""


def parse_cag_response(response_text: str) -> list[dict]:
    """Parse the LLM's JSON response into structured matches."""
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        matches = json.loads(text)
        if isinstance(matches, list):
            return matches
    except json.JSONDecodeError:
        pass
    return []
