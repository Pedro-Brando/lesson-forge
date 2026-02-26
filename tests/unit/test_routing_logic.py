"""Tests for teaching focus routing logic."""

from backend.workflow.steps.teaching_router import (
    TEACHING_FOCUS_NOTES,
    YEAR_BAND_NOTES,
)


def test_all_teaching_focuses_have_notes():
    expected = [
        "explicit_instruction",
        "deep_learning_inquiry",
        "fluency_practice",
        "assessment_feedback",
        "planning",
    ]
    for focus in expected:
        assert focus in TEACHING_FOCUS_NOTES, f"Missing notes for {focus}"
        assert len(TEACHING_FOCUS_NOTES[focus]) > 20


def test_all_year_bands_have_notes():
    expected = ["early_years", "primary", "secondary"]
    for band in expected:
        assert band in YEAR_BAND_NOTES, f"Missing notes for {band}"
        assert len(YEAR_BAND_NOTES[band]) > 20


def test_explicit_instruction_notes_contain_ido():
    notes = TEACHING_FOCUS_NOTES["explicit_instruction"]
    assert "I Do" in notes
    assert "We Do" in notes
    assert "You Do" in notes


def test_inquiry_notes_contain_thinking():
    notes = TEACHING_FOCUS_NOTES["deep_learning_inquiry"]
    assert "thinking" in notes.lower() or "inquiry" in notes.lower()


def test_assessment_notes_contain_criteria():
    notes = TEACHING_FOCUS_NOTES["assessment_feedback"]
    assert "success criteria" in notes.lower() or "assessment" in notes.lower()


def test_early_years_notes_contain_concrete():
    notes = YEAR_BAND_NOTES["early_years"]
    assert "concrete" in notes.lower() or "hands-on" in notes.lower()


def test_secondary_notes_contain_formal():
    notes = YEAR_BAND_NOTES["secondary"]
    assert "formal" in notes.lower() or "abstract" in notes.lower()


def test_fluency_notes_contain_zpd():
    notes = TEACHING_FOCUS_NOTES["fluency_practice"]
    assert "Zone of Proximal Development" in notes or "fluency" in notes.lower()
