"""Tests for SQLAlchemy ORM models."""

from backend.db.models import (
    AchievementStandard,
    ContentDescriptor,
    Elaboration,
    GenerationLog,
    PromptTemplate,
    ResourceType,
    Strand,
    TeachingFocus,
    YearLevel,
)


def test_year_level_creation(db_session):
    yl = YearLevel(code="MATMATY5", title="Year 5", sort_order=5, band="primary")
    db_session.add(yl)
    db_session.commit()

    result = db_session.query(YearLevel).filter_by(code="MATMATY5").first()
    assert result is not None
    assert result.title == "Year 5"
    assert result.band == "primary"


def test_strand_creation(db_session):
    s = Strand(code="NUM", title="Number")
    db_session.add(s)
    db_session.commit()

    result = db_session.query(Strand).filter_by(code="NUM").first()
    assert result is not None
    assert result.title == "Number"


def test_content_descriptor_with_relationships(db_session):
    yl = YearLevel(code="MATMATY5", title="Year 5", sort_order=5, band="primary")
    s = Strand(code="NUM", title="Number")
    db_session.add_all([yl, s])
    db_session.flush()

    cd = ContentDescriptor(
        code="AC9M5N06",
        text="solve problems involving addition and subtraction of fractions",
        year_level_code="MATMATY5",
        strand_title="Number",
    )
    db_session.add(cd)
    db_session.commit()

    result = db_session.query(ContentDescriptor).filter_by(code="AC9M5N06").first()
    assert result is not None
    assert result.year_level.title == "Year 5"
    assert result.strand.title == "Number"


def test_elaboration_relationship(db_session):
    yl = YearLevel(code="MATMATY5", title="Year 5", sort_order=5, band="primary")
    s = Strand(code="NUM", title="Number")
    cd = ContentDescriptor(
        code="AC9M5N06",
        text="solve problems involving fractions",
        year_level_code="MATMATY5",
        strand_title="Number",
    )
    elab = Elaboration(
        code="AC9M5N06_E1",
        text="using fraction walls to compare fractions",
        content_descriptor_code="AC9M5N06",
    )
    db_session.add_all([yl, s, cd, elab])
    db_session.commit()

    result = db_session.query(Elaboration).filter_by(code="AC9M5N06_E1").first()
    assert result.content_descriptor.code == "AC9M5N06"


def test_teaching_focus_and_resource_type(db_session):
    tf = TeachingFocus(name="Explicit Instruction", slug="explicit_instruction")
    rt = ResourceType(
        name="Worked Example Study",
        slug="worked_example_study",
        description="Step-by-step demonstrations",
        teaching_focus_slug="explicit_instruction",
    )
    db_session.add_all([tf, rt])
    db_session.commit()

    result = db_session.query(ResourceType).filter_by(slug="worked_example_study").first()
    assert result.teaching_focus.name == "Explicit Instruction"


def test_prompt_template_nullable_fks(db_session):
    tmpl = PromptTemplate(
        name="default_resource",
        resource_type_slug=None,
        teaching_focus_slug=None,
        year_band=None,
        template_body="Generate a {resource_type_name} for {year_level}",
        priority=0,
    )
    db_session.add(tmpl)
    db_session.commit()

    result = db_session.query(PromptTemplate).filter_by(name="default_resource").first()
    assert result.resource_type_slug is None
    assert result.priority == 0


def test_generation_log_model_exists():
    """GenerationLog model is defined (requires PostgreSQL for full testing)."""
    assert GenerationLog.__tablename__ == "generation_logs"
    assert hasattr(GenerationLog, "id")
    assert hasattr(GenerationLog, "request_payload")
    assert hasattr(GenerationLog, "status")
