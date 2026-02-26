"""Template selection and variable resolution service."""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.db.models import (
    AchievementStandard,
    ContentDescriptor,
    Elaboration,
    PromptTemplate,
    ResourceType,
    TeachingFocus,
    YearLevel,
)


def select_template(
    db: Session,
    resource_type_slug: str,
    teaching_focus_slug: str,
    year_band: str,
) -> PromptTemplate | None:
    """Select the highest-priority matching template."""
    candidates = (
        db.query(PromptTemplate)
        .filter(
            or_(
                PromptTemplate.resource_type_slug == resource_type_slug,
                PromptTemplate.resource_type_slug.is_(None),
            ),
            or_(
                PromptTemplate.teaching_focus_slug == teaching_focus_slug,
                PromptTemplate.teaching_focus_slug.is_(None),
            ),
            or_(
                PromptTemplate.year_band == year_band,
                PromptTemplate.year_band.is_(None),
            ),
        )
        .order_by(PromptTemplate.priority.desc())
        .all()
    )
    return candidates[0] if candidates else None


def resolve_template(
    db: Session,
    template: PromptTemplate,
    matched_descriptor_code: str,
    year_level_code: str,
    resource_type_slug: str,
    teaching_focus_slug: str,
    rag_context: str,
    additional_context: str,
) -> tuple[str, dict]:
    """Resolve all {variable} placeholders in a template from DB lookups.

    Returns (resolved_prompt, variables_dict).
    """
    variables = {}

    # Content descriptor
    cd = db.query(ContentDescriptor).filter_by(code=matched_descriptor_code).first()
    variables["content_descriptor"] = cd.text if cd else "N/A"

    # Elaborations
    elabs = db.query(Elaboration).filter_by(content_descriptor_code=matched_descriptor_code).all()
    variables["elaborations"] = "\n".join(f"- {e.text}" for e in elabs) if elabs else "N/A"

    # Year level
    yl = db.query(YearLevel).filter_by(code=year_level_code).first()
    variables["year_level"] = yl.title if yl else year_level_code
    variables["strand"] = cd.strand_title if cd else "N/A"

    # Achievement standard
    standards = db.query(AchievementStandard).filter_by(year_level_code=year_level_code).all()
    variables["achievement_standard"] = "\n".join(s.text for s in standards) if standards else "N/A"

    # Resource type
    rt = db.query(ResourceType).filter_by(slug=resource_type_slug).first()
    variables["resource_type_name"] = rt.name if rt else resource_type_slug
    variables["resource_type_description"] = rt.description if rt else ""

    # Teaching focus
    tf = db.query(TeachingFocus).filter_by(slug=teaching_focus_slug).first()
    variables["teaching_focus"] = tf.name if tf else teaching_focus_slug

    # RAG context and additional context
    variables["rag_context"] = rag_context or "No additional pedagogical context retrieved."
    variables["additional_context"] = additional_context or "No additional context provided."

    # Resolve
    resolved = template.template_body
    for key, value in variables.items():
        resolved = resolved.replace(f"{{{key}}}", str(value))

    return resolved, variables
