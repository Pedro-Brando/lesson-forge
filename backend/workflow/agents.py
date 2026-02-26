"""Agno Agent definitions for the lesson workflow."""

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from backend.config import settings


def get_input_analyzer() -> Agent:
    return Agent(
        name="Input Analyzer",
        model=OpenAIChat(id=settings.OPENAI_MODEL_FAST),
        instructions=[
            "You are an educational request parser for the Australian Mathematics Curriculum.",
            "Parse the teacher's request and extract: topic, year_level, strand, intent, and keywords.",
            "Intent should be one of: instruction, practice, assessment, inquiry, planning.",
            "Keywords should be 3-5 key mathematical terms from the request.",
        ],
        markdown=False,
    )


def get_cag_matcher() -> Agent:
    return Agent(
        name="Curriculum Matcher",
        model=OpenAIChat(id=settings.OPENAI_MODEL_FAST),
        instructions=[
            "You are a curriculum matching expert.",
            "Given a teacher's topic and ALL content descriptors, find the best matches.",
            "Return valid JSON only.",
        ],
        markdown=False,
    )


def get_resource_generator() -> Agent:
    return Agent(
        name="Resource Generator",
        model=OpenAIChat(id=settings.OPENAI_MODEL_GENERATION),
        instructions=[
            "You are an expert Australian Mathematics educator.",
            "Generate high-quality, classroom-ready educational resources.",
            "Use Australian English spelling and terminology.",
            "Format output in clean Markdown with clear headings and structure.",
            "Include practical, specific content - not generic placeholders.",
        ],
        markdown=True,
    )
