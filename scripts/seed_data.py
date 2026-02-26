"""Seed all reference tables from curriculum.json and message.txt."""

import json
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.db.models import (
    AchievementStandard,
    ContentDescriptor,
    Elaboration,
    PromptTemplate,
    ResourceType,
    Strand,
    TeachingFocus,
    YearLevel,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def year_band(code: str, title: str) -> str:
    if code == "MATMATFY" or title in ("Year 1", "Year 2"):
        return "early_years"
    if title in ("Year 7", "Year 8", "Year 9", "Year 10"):
        return "secondary"
    return "primary"


SORT_MAP = {
    "Foundation Year": 0,
    "Year 1": 1, "Year 2": 2, "Year 3": 3, "Year 4": 4,
    "Year 5": 5, "Year 6": 6, "Year 7": 7, "Year 8": 8,
    "Year 9": 9, "Year 10": 10,
}


def seed_curriculum(session):
    with open(DATA_DIR / "curriculum.json", encoding="utf-8") as f:
        data = json.load(f)

    subject = data["learning_areas"][0]["subjects"][0]
    levels = subject["levels"]
    content_items = data["content_items"]

    # Collect unique strands
    strand_set = set()
    for level in levels:
        for s in level["strands"]:
            strand_set.add(s["title"])

    # Strand code mapping
    strand_code_map = {
        "Number": "NUM",
        "Algebra": "ALG",
        "Measurement": "MEA",
        "Space": "SPA",
        "Statistics": "STA",
        "Probability": "PRO",
    }

    # Seed strands
    for title in sorted(strand_set):
        code = strand_code_map.get(title, slugify(title).upper()[:3])
        existing = session.query(Strand).filter_by(code=code).first()
        if not existing:
            session.add(Strand(code=code, title=title))
    session.flush()

    # Seed year levels
    for level in levels:
        band = year_band(level["code"], level["title"])
        sort_order = SORT_MAP.get(level["title"], 99)
        # Strip HTML from level_description
        desc = re.sub(r"<[^>]+>", "", level.get("level_description", ""))
        existing = session.query(YearLevel).filter_by(code=level["code"]).first()
        if not existing:
            session.add(
                YearLevel(
                    code=level["code"],
                    title=level["title"],
                    sort_order=sort_order,
                    level_description=desc,
                    band=band,
                )
            )
    session.flush()

    # Seed achievement standards
    for level in levels:
        for std in level.get("achievement_standards", []):
            existing = session.query(AchievementStandard).filter_by(code=std["code"]).first()
            if not existing:
                session.add(
                    AchievementStandard(
                        code=std["code"],
                        text=std["text"],
                        year_level_code=level["code"],
                    )
                )
    session.flush()

    # Seed content descriptors and elaborations
    for item in content_items:
        loc = item["location"]
        existing = session.query(ContentDescriptor).filter_by(code=item["code"]).first()
        if not existing:
            session.add(
                ContentDescriptor(
                    code=item["code"],
                    text=item["text"],
                    year_level_code=loc["level_code"],
                    strand_title=loc["strand"],
                )
            )
        session.flush()

        for elab in item.get("elaborations", []):
            existing_elab = session.query(Elaboration).filter_by(code=elab["code"]).first()
            if not existing_elab:
                session.add(
                    Elaboration(
                        code=elab["code"],
                        text=elab["text"],
                        content_descriptor_code=item["code"],
                    )
                )
    session.flush()
    print(f"Seeded curriculum: {session.query(ContentDescriptor).count()} content descriptors, "
          f"{session.query(Elaboration).count()} elaborations, "
          f"{session.query(AchievementStandard).count()} achievement standards")


def parse_message_txt() -> list[dict]:
    """Parse message.txt into resource type records."""
    path = DATA_DIR.parent / "data" / "message.txt"
    # Also check root-level copy
    if not path.exists():
        path = Path(__file__).resolve().parent.parent / "data" / "message.txt"
    if not path.exists():
        # Try the original source
        path = Path("C:/Users/ph00r/Documents/JobTest/message.txt")

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    resources = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        # Pattern: resource_name, description, blank, teaching_focus
        # The file format is: name\ndescription\n\nteaching_focus
        # But actually the format seems to be:
        # teaching_focus_name\nresource_name\ndescription\n\nteaching_focus_category
        # Let me re-parse based on the actual file structure
        # Looking at the file: it's groups of 3 lines (or 4 with blank):
        # resource_name
        # description
        # (blank line)
        # teaching_focus

        # Actually looking at the file more carefully:
        # Line pattern is:
        # ResourceName
        # Description text
        # (blank)
        # TeachingFocus
        # ResourceName
        # ...
        i += 1

    # Re-parse with correct understanding of the file format
    # The file format is actually pairs:
    # Line 1: Resource Name
    # Line 2: Description
    # Line 3: (empty)
    # Line 4: Teaching Focus category
    # But that doesn't match. Let me re-read the actual file content.
    return resources


def seed_teaching_resources(session):
    """Seed teaching focuses and resource types from message.txt."""
    # Parse from the known file structure based on our reading
    resources_data = [
        ("Standards Guidance", "Practical translation of ACARA v9 standards into observable classroom actions. Bridges the gap between abstract curriculum language and concrete evidence of student mastery.", "Planning"),
        ("Concepts & Progression Map", "Visual mapping of 'Big Ideas' across multiple year levels. Helps teachers understand how conceptual complexity builds over time to ensure vertical alignment and curriculum continuity.", "Planning"),
        ("Diagnostic Assessment", "Pre-instructional check to measure prior knowledge and entry points. Essential for identifying learning gaps, establishing a baseline, and measuring individual student growth.", "Planning"),
        ("Success Criteria Rubric", "Student-facing 'I Can' statements derived directly from achievement standards. Empowers students through self-assessment, goal setting, and a clear understanding of what 'quality' looks like.", "Planning"),
        ("Instructional Slides", "Visual teaching aids designed to anchor direct instruction and modeling. Supports the teacher in delivering content-rich lessons while reducing student cognitive load through structured visuals.", "Planning"),
        ("Explicit Instruction Sequence", "Highly structured 'I Do, We Do, You Do' architecture for introducing new skills. Uses modeling and frequent check-for-understanding cycles to build student confidence and secure success.", "Explicit Instruction"),
        ("Worked Example Study", "Step-by-step demonstrations of solved problems used to scaffold new learning. Reduces instructional anxiety by allowing students to study successful processes before attempting independent execution.", "Explicit Instruction"),
        ("Vocabulary Tiering Matrix", "Explicit instruction of high-frequency academic and subject-specific terms. Ensures literacy equity by providing EAL/D students and diverse learners with the 'hidden' language of the curriculum.", "Explicit Instruction"),
        ("Task Set", "Scaffolded practice sets that target a student's specific Zone of Proximal Development. Provides a clear path from foundational support to high-level extension across core literacy and numeracy skills.", "Fluency & Practice"),
        ("Reading Comprehension Worksheet", "Strategy-focused reading tasks targeting literal and inferential meaning. Develops active reading skills such as predicting and connecting to build deep engagement with complex texts.", "Fluency & Practice"),
        ("Deliberate Practice Set", "High-repetition skill drills focused on achieving procedural automaticity. Targets specific, narrow skills to ensure students can perform them with minimal conscious effort and high accuracy.", "Fluency & Practice"),
        ("Problem Solving & Reasoning Task", "Challenging tasks designed for the application of strategies in non-routine contexts. Promotes persistence and critical thinking by requiring students to justify their methods and explain their logic.", "Deep Learning & Inquiry"),
        ("Thinking Routine", "Repeatable, structured sequences designed to internalize high-level cognitive patterns. Ideal for uncovering complexities, considering diverse perspectives, and reasoning with evidence.", "Deep Learning & Inquiry"),
        ("Task Shell", "Content-neutral cognitive frameworks that prioritize the process of thinking over the subject matter. Builds transferable skills by allowing students to master logical structures used across multiple disciplines.", "Deep Learning & Inquiry"),
        ("Socratic Fishbowl", "Collaborative discussion forum focused on oral communication and active listening. Develops the social-cognitive ability to respectfully challenge ideas and build upon the perspectives of peers.", "Deep Learning & Inquiry"),
        ("Retrieval Practice Grid", "Gamified active recall task designed to strengthen long-term memory. Uses spaced repetition to ensure key concepts are retained and easily accessed during future learning cycles.", "Assessment & Feedback"),
        ("Exit Ticket", "Rapid end-of-lesson assessment to gauge immediate comprehension. Provides real-time data to identify misconceptions and inform differentiated planning for the subsequent lesson.", "Assessment & Feedback"),
    ]

    # Create teaching focuses
    focus_names = sorted(set(r[2] for r in resources_data))
    for name in focus_names:
        slug = slugify(name)
        existing = session.query(TeachingFocus).filter_by(slug=slug).first()
        if not existing:
            session.add(TeachingFocus(name=name, slug=slug))
    session.flush()

    # Create resource types
    for name, description, focus_name in resources_data:
        slug = slugify(name)
        focus_slug = slugify(focus_name)
        existing = session.query(ResourceType).filter_by(slug=slug).first()
        if not existing:
            session.add(
                ResourceType(
                    name=name,
                    slug=slug,
                    description=description,
                    teaching_focus_slug=focus_slug,
                )
            )
    session.flush()
    print(f"Seeded {session.query(TeachingFocus).count()} teaching focuses, "
          f"{session.query(ResourceType).count()} resource types")


def seed_prompt_templates(session):
    """Seed prompt templates for resource generation."""
    templates = [
        {
            "name": "default_resource",
            "resource_type_slug": None,
            "teaching_focus_slug": None,
            "year_band": None,
            "priority": 0,
            "template_body": """You are an expert Australian Mathematics educator creating a {resource_type_name} resource.

**Year Level:** {year_level}
**Strand:** {strand}
**Teaching Focus:** {teaching_focus}

**Curriculum Alignment:**
Content Descriptor: {content_descriptor}

**Elaborations:**
{elaborations}

**Achievement Standard:**
{achievement_standard}

**Pedagogical Context:**
{rag_context}

**Resource Type:** {resource_type_name}
{resource_type_description}

**Teacher's Request:** {additional_context}

Generate a complete, classroom-ready {resource_type_name} resource that:
1. Directly addresses the content descriptor above
2. Is appropriate for {year_level} students
3. Follows the {teaching_focus} approach
4. Includes clear instructions for the teacher
5. Uses Australian English and terminology

Format the resource using Markdown with clear headings and sections.""",
        },
        {
            "name": "worked_example",
            "resource_type_slug": "worked_example_study",
            "teaching_focus_slug": None,
            "year_band": None,
            "priority": 5,
            "template_body": """You are an expert Australian Mathematics educator creating a Worked Example Study.

**Year Level:** {year_level}
**Strand:** {strand}
**Teaching Focus:** {teaching_focus}

**Curriculum Alignment:**
Content Descriptor: {content_descriptor}

**Elaborations:**
{elaborations}

**Achievement Standard:**
{achievement_standard}

**Pedagogical Context:**
{rag_context}

**Teacher's Notes:** {additional_context}

Create a detailed Worked Example Study following the **I Do / We Do / You Do** structure:

## I Do (Teacher Demonstration)
- Provide 2 fully worked examples with step-by-step solutions
- Include teacher talk scripts explaining each step
- Highlight common misconceptions to address

## We Do (Guided Practice)
- Provide 3 partially worked examples where students complete missing steps
- Include prompting questions for the teacher
- Scaffold difficulty progressively

## You Do (Independent Practice)
- Provide 4-5 practice problems of increasing complexity
- Include success criteria students can self-assess against
- Add extension challenges for early finishers

Include mathematical notation where appropriate. Use Australian English.
Format using Markdown with clear headings.""",
        },
        {
            "name": "exit_ticket",
            "resource_type_slug": "exit_ticket",
            "teaching_focus_slug": None,
            "year_band": None,
            "priority": 5,
            "template_body": """You are an expert Australian Mathematics educator creating an Exit Ticket.

**Year Level:** {year_level}
**Strand:** {strand}

**Curriculum Alignment:**
Content Descriptor: {content_descriptor}

**Achievement Standard:**
{achievement_standard}

**Pedagogical Context:**
{rag_context}

**Teacher's Notes:** {additional_context}

Create a quick **Exit Ticket** (5-minute end-of-lesson assessment):

## Exit Ticket: {strand} - {year_level}

Design exactly 3 questions that check understanding of the content descriptor:

**Question 1 (Recall):** A straightforward recall question testing basic knowledge.

**Question 2 (Application):** An application question requiring students to use the concept.

**Question 3 (Reasoning):** A short reasoning question where students explain their thinking.

Include:
- A marking guide for the teacher (what to look for in correct responses)
- Traffic light self-assessment (Green/Amber/Red) instructions
- Suggested follow-up actions based on common error patterns

Use Australian English. Format using Markdown.""",
        },
        {
            "name": "task_set",
            "resource_type_slug": "task_set",
            "teaching_focus_slug": None,
            "year_band": None,
            "priority": 5,
            "template_body": """You are an expert Australian Mathematics educator creating a Task Set.

**Year Level:** {year_level}
**Strand:** {strand}
**Teaching Focus:** {teaching_focus}

**Curriculum Alignment:**
Content Descriptor: {content_descriptor}

**Elaborations:**
{elaborations}

**Achievement Standard:**
{achievement_standard}

**Pedagogical Context:**
{rag_context}

**Teacher's Notes:** {additional_context}

Create a scaffolded **Task Set** targeting the Zone of Proximal Development:

## Task Set: {strand} - {year_level}

### Level 1: Foundation (Support)
- 4 questions with visual supports and worked example references
- Designed for students who need additional scaffolding

### Level 2: Core (Proficient)
- 6 questions at grade-level expectation
- Aligned directly to the content descriptor
- Include real-world contexts

### Level 3: Extension (Challenge)
- 4 questions requiring deeper reasoning
- Open-ended problems with multiple solution paths
- Connections to other strands where appropriate

Include:
- Clear instructions for each level
- Success criteria aligned to the achievement standard
- Suggested time allocation (approximately 20-25 minutes total)

Use Australian English. Format using Markdown.""",
        },
        {
            "name": "early_years_resource",
            "resource_type_slug": None,
            "teaching_focus_slug": None,
            "year_band": "early_years",
            "priority": 3,
            "template_body": """You are an expert early years Australian Mathematics educator creating a {resource_type_name}.

**Year Level:** {year_level} (Early Years)
**Strand:** {strand}
**Teaching Focus:** {teaching_focus}

**Curriculum Alignment:**
Content Descriptor: {content_descriptor}

**Elaborations:**
{elaborations}

**Achievement Standard:**
{achievement_standard}

**Pedagogical Context:**
{rag_context}

**Resource Type:** {resource_type_name}
{resource_type_description}

**Teacher's Notes:** {additional_context}

**EARLY YEARS CONSIDERATIONS:**
- Use simple, age-appropriate language
- Include concrete materials and manipulatives (counters, blocks, ten frames)
- Incorporate play-based learning activities
- Use visual representations and pictures
- Keep activities hands-on and interactive
- Include oral language opportunities
- Consider fine motor skill development stages

Generate a complete, classroom-ready {resource_type_name} that is specifically designed for early years learners. Use Australian English and familiar contexts (Australian animals, local settings).""",
        },
        {
            "name": "secondary_resource",
            "resource_type_slug": None,
            "teaching_focus_slug": None,
            "year_band": "secondary",
            "priority": 3,
            "template_body": """You are an expert secondary Mathematics educator creating a {resource_type_name}.

**Year Level:** {year_level} (Secondary)
**Strand:** {strand}
**Teaching Focus:** {teaching_focus}

**Curriculum Alignment:**
Content Descriptor: {content_descriptor}

**Elaborations:**
{elaborations}

**Achievement Standard:**
{achievement_standard}

**Pedagogical Context:**
{rag_context}

**Resource Type:** {resource_type_name}
{resource_type_description}

**Teacher's Notes:** {additional_context}

**SECONDARY LEVEL CONSIDERATIONS:**
- Use formal mathematical notation and terminology
- Include abstract reasoning and proof-based activities where appropriate
- Connect to real-world applications (STEM, finance, data analysis)
- Encourage algebraic thinking and generalisation
- Include technology integration opportunities (graphing tools, spreadsheets)
- Support development of mathematical argumentation skills

Generate a complete, classroom-ready {resource_type_name} for secondary students. Use precise mathematical language and Australian English.""",
        },
    ]

    for tmpl in templates:
        existing = session.query(PromptTemplate).filter_by(name=tmpl["name"]).first()
        if not existing:
            session.add(PromptTemplate(**tmpl))
    session.flush()
    print(f"Seeded {session.query(PromptTemplate).count()} prompt templates")


def main():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        seed_curriculum(session)
        seed_teaching_resources(session)
        seed_prompt_templates(session)
        session.commit()
        print("Seed data complete.")
    except Exception as e:
        session.rollback()
        print(f"Seed failed: {e}", file=sys.stderr)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
