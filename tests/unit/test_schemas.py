"""Tests for Pydantic request/response schemas."""

import pytest
from pydantic import ValidationError

from backend.api.schemas import (
    CAGMatch,
    CAGResult,
    GenerateRequest,
    ParsedInput,
    ResourceTypeOut,
    RoutingDecision,
)


def test_generate_request_defaults():
    req = GenerateRequest(topic="teaching fractions")
    assert req.year_level == "Year 5"
    assert req.strand == "Number"
    assert req.teaching_focus == "explicit_instruction"
    assert req.resource_type == "worked_example_study"
    assert req.additional_context == ""


def test_generate_request_custom():
    req = GenerateRequest(
        topic="area and perimeter",
        year_level="Year 7",
        strand="Measurement",
        teaching_focus="deep_learning_inquiry",
        resource_type="problem_solving_reasoning_task",
        additional_context="Focus on real-world contexts",
    )
    assert req.topic == "area and perimeter"
    assert req.year_level == "Year 7"


def test_generate_request_validation_empty_topic():
    with pytest.raises(ValidationError):
        GenerateRequest(topic="")


def test_parsed_input():
    pi = ParsedInput(
        topic="fractions",
        year_level="Year 5",
        strand="Number",
        intent="instruction",
        keywords=["fractions", "addition", "subtraction"],
    )
    assert len(pi.keywords) == 3


def test_cag_match():
    match = CAGMatch(
        code="AC9M5N06",
        text="solve problems involving fractions",
        year_level="MATMATY5",
        strand="Number",
        confidence="high",
        reason="Direct match on fractions topic",
    )
    assert match.confidence == "high"


def test_cag_result():
    result = CAGResult(
        matches=[
            CAGMatch(code="AC9M5N06", text="fractions", year_level="Y5", strand="NUM", confidence="high"),
            CAGMatch(code="AC9M5N07", text="decimals", year_level="Y5", strand="NUM", confidence="medium"),
        ]
    )
    assert len(result.matches) == 2


def test_routing_decision():
    rd = RoutingDecision(
        teaching_path="explicit_instruction",
        year_band="primary",
        pedagogy_notes="Use I Do / We Do / You Do",
    )
    assert rd.year_band == "primary"


def test_resource_type_out():
    rt = ResourceTypeOut(
        name="Worked Example Study",
        slug="worked_example_study",
        description="Step-by-step demonstrations",
        teaching_focus_slug="explicit_instruction",
    )
    assert rt.slug == "worked_example_study"
