"""Main Agno Workflow definition for LessonForge.

6-step workflow with conditional routing:
1. InputAnalyzer - Parse teacher's request
2. CurriculumMatcher (CAG) - Match topic against all content descriptors
3. TeachingFocusRouter - Route by teaching focus + year level
4. PedagogyRetriever (RAG) - Retrieve from pgvector
5. TemplateResolver - Select and resolve prompt template
6. ResourceGenerator - Generate resource with streaming
"""

from typing import List

from agno.run import RunContext
from agno.workflow.router import Router
from agno.workflow.step import Step, StepInput
from agno.workflow.workflow import Workflow

from backend.workflow.steps.input_analyzer import input_analyzer_step
from backend.workflow.steps.curriculum_matcher import curriculum_matcher_step
from backend.workflow.steps.pedagogy_retriever import pedagogy_retriever_step
from backend.workflow.steps.resource_generator import resource_generator_step
from backend.workflow.steps.teaching_router import teaching_router_step
from backend.workflow.steps.template_resolver import template_resolver_step

# Define the 5 teaching focus processing steps for the Router
explicit_instruction_step = Step(
    name="explicit_instruction_enrichment",
    description="Enrich context for explicit instruction focus",
    executor=teaching_router_step,
)

inquiry_step = Step(
    name="inquiry_enrichment",
    description="Enrich context for deep learning & inquiry focus",
    executor=teaching_router_step,
)

fluency_step = Step(
    name="fluency_enrichment",
    description="Enrich context for fluency & practice focus",
    executor=teaching_router_step,
)

assessment_step = Step(
    name="assessment_enrichment",
    description="Enrich context for assessment & feedback focus",
    executor=teaching_router_step,
)

planning_step = Step(
    name="planning_enrichment",
    description="Enrich context for planning focus",
    executor=teaching_router_step,
)


def teaching_focus_selector(step_input: StepInput, run_context: RunContext) -> List[Step]:
    """Route to the appropriate teaching focus enrichment step."""
    state = run_context.session_state
    focus = state["params"]["teaching_focus"]

    route_map = {
        "explicit_instruction": explicit_instruction_step,
        "deep_learning_inquiry": inquiry_step,
        "fluency_practice": fluency_step,
        "assessment_feedback": assessment_step,
        "planning": planning_step,
    }

    selected = route_map.get(focus, explicit_instruction_step)
    return [selected]


def create_lesson_workflow(shared_state: dict) -> Workflow:
    """Create a new workflow instance with the given shared state dict.

    The shared_state dict is mutated by steps via run_context.session_state,
    and can be read directly by the calling code after each step completes.
    """
    return Workflow(
        name="LessonForge Resource Generator",
        description="Generate curriculum-aligned educational resources for Australian Mathematics",
        steps=[
            Step(
                name="input_analyzer",
                description="Parse teacher's request into structured fields",
                executor=input_analyzer_step,
            ),
            Step(
                name="curriculum_matcher",
                description="CAG: Match topic against all 240 content descriptors",
                executor=curriculum_matcher_step,
            ),
            Router(
                name="teaching_focus_router",
                description="Route by teaching focus (5 paths) with year band conditioning",
                selector=teaching_focus_selector,
                choices=[
                    explicit_instruction_step,
                    inquiry_step,
                    fluency_step,
                    assessment_step,
                    planning_step,
                ],
            ),
            Step(
                name="pedagogy_retriever",
                description="RAG: Retrieve relevant elaborations and pedagogy from pgvector",
                executor=pedagogy_retriever_step,
            ),
            Step(
                name="template_resolver",
                description="Select and resolve prompt template from database",
                executor=template_resolver_step,
            ),
            Step(
                name="resource_generator",
                description="Generate the final lesson resource with streaming",
                executor=resource_generator_step,
            ),
        ],
        session_state=shared_state,
    )
