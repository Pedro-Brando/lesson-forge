from typing import Optional

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="What to teach")
    year_level: str = Field(default="Year 5")
    strand: str = Field(default="Number")
    teaching_focus: str = Field(default="explicit_instruction", description="Teaching focus slug")
    resource_type: str = Field(default="worked_example_study", description="Resource type slug")
    additional_context: str = Field(default="", description="Extra teacher notes")


class ParsedInput(BaseModel):
    topic: str
    year_level: str
    strand: str
    intent: str = ""
    keywords: list[str] = []


class CAGMatch(BaseModel):
    code: str
    text: str
    year_level: str
    strand: str
    confidence: str  # "high", "medium", "low"
    reason: str = ""


class CAGResult(BaseModel):
    matches: list[CAGMatch]


class RoutingDecision(BaseModel):
    teaching_path: str
    year_band: str
    pedagogy_notes: str = ""


class YearLevelOut(BaseModel):
    code: str
    title: str
    band: str

    model_config = {"from_attributes": True}


class StrandOut(BaseModel):
    code: str
    title: str

    model_config = {"from_attributes": True}


class TeachingFocusOut(BaseModel):
    name: str
    slug: str

    model_config = {"from_attributes": True}


class ResourceTypeOut(BaseModel):
    name: str
    slug: str
    description: Optional[str]
    teaching_focus_slug: str

    model_config = {"from_attributes": True}
