"""Tests for template selection and variable resolution."""

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
from backend.services.template_service import resolve_template, select_template


def _seed_fixtures(db):
    """Add minimal fixture data for template tests."""
    yl = YearLevel(code="MATMATY5", title="Year 5", sort_order=5, band="primary")
    s = Strand(code="NUM", title="Number")
    cd = ContentDescriptor(
        code="AC9M5N06", text="solve problems involving fractions",
        year_level_code="MATMATY5", strand_title="Number",
    )
    elab = Elaboration(
        code="AC9M5N06_E1", text="using fraction walls to compare",
        content_descriptor_code="AC9M5N06",
    )
    ast = AchievementStandard(
        code="ASMAT501", text="Students solve problems using fractions",
        year_level_code="MATMATY5",
    )
    tf = TeachingFocus(name="Explicit Instruction", slug="explicit_instruction")
    rt = ResourceType(
        name="Worked Example Study", slug="worked_example_study",
        description="Step-by-step demos", teaching_focus_slug="explicit_instruction",
    )

    # Templates
    default_tmpl = PromptTemplate(
        name="default_resource",
        resource_type_slug=None,
        teaching_focus_slug=None,
        year_band=None,
        template_body="Generate a {resource_type_name} for {year_level} about {content_descriptor}",
        priority=0,
    )
    specific_tmpl = PromptTemplate(
        name="worked_example",
        resource_type_slug="worked_example_study",
        teaching_focus_slug=None,
        year_band=None,
        template_body="Create I Do/We Do/You Do for {year_level}: {content_descriptor}\nElaborations: {elaborations}",
        priority=5,
    )
    band_tmpl = PromptTemplate(
        name="early_years_resource",
        resource_type_slug=None,
        teaching_focus_slug=None,
        year_band="early_years",
        template_body="Simple resource for {year_level}: {content_descriptor}",
        priority=3,
    )

    db.add_all([yl, s, cd, elab, ast, tf, rt, default_tmpl, specific_tmpl, band_tmpl])
    db.commit()


def test_select_template_specific_match(db_session):
    _seed_fixtures(db_session)
    tmpl = select_template(
        db_session, "worked_example_study", "explicit_instruction", "primary"
    )
    assert tmpl is not None
    assert tmpl.name == "worked_example"
    assert tmpl.priority == 5


def test_select_template_falls_back_to_default(db_session):
    _seed_fixtures(db_session)
    tmpl = select_template(
        db_session, "exit_ticket", "assessment_feedback", "primary"
    )
    assert tmpl is not None
    assert tmpl.name == "default_resource"


def test_select_template_year_band_match(db_session):
    _seed_fixtures(db_session)
    tmpl = select_template(
        db_session, "some_other_type", "some_focus", "early_years"
    )
    assert tmpl is not None
    # Should get early_years_resource (priority 3) over default (priority 0)
    assert tmpl.name == "early_years_resource"


def test_resolve_template_variables(db_session):
    _seed_fixtures(db_session)
    tmpl = db_session.query(PromptTemplate).filter_by(name="worked_example").first()
    resolved, variables = resolve_template(
        db=db_session,
        template=tmpl,
        matched_descriptor_code="AC9M5N06",
        year_level_code="MATMATY5",
        resource_type_slug="worked_example_study",
        teaching_focus_slug="explicit_instruction",
        rag_context="Some pedagogy context",
        additional_context="Focus on pizza sharing",
    )
    assert "Year 5" in resolved
    assert "solve problems involving fractions" in resolved
    assert "fraction walls" in resolved
    assert "year_level" in variables
    assert variables["year_level"] == "Year 5"


def test_resolve_template_missing_descriptor(db_session):
    _seed_fixtures(db_session)
    tmpl = db_session.query(PromptTemplate).filter_by(name="default_resource").first()
    resolved, variables = resolve_template(
        db=db_session,
        template=tmpl,
        matched_descriptor_code="NONEXISTENT",
        year_level_code="MATMATY5",
        resource_type_slug="worked_example_study",
        teaching_focus_slug="explicit_instruction",
        rag_context="",
        additional_context="",
    )
    assert "N/A" in resolved
