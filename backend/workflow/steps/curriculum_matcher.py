"""Step 2: CAG - Match topic against all content descriptors."""

import json

from agno.run import RunContext
from agno.workflow.step import StepInput, StepOutput

from backend.config import settings
from backend.db.session import SessionLocal
from backend.services.cag_service import build_cag_prompt, load_all_descriptors, parse_cag_response
from backend.workflow.agents import get_cag_matcher


def curriculum_matcher_step(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """Load ALL 240 content descriptors into LLM context and match semantically."""
    state = run_context.session_state
    parsed = state["parsed_input"]

    db = SessionLocal()
    try:
        descriptors = load_all_descriptors(db)
        prompt = build_cag_prompt(
            topic=parsed["topic"],
            year_level=parsed["year_level"],
            strand=parsed["strand"],
            descriptors=descriptors,
        )

        agent = get_cag_matcher()
        response = agent.run(prompt)
        matches = parse_cag_response(response.content)

        # Extract token usage metrics
        token_usage = None
        if response.metrics:
            token_usage = {
                "input_tokens": response.metrics.input_tokens or 0,
                "output_tokens": response.metrics.output_tokens or 0,
                "total_tokens": response.metrics.total_tokens or 0,
                "model": settings.OPENAI_MODEL_FAST,
            }

        # Ensure we have at least one match
        if not matches:
            matches = [
                {
                    "code": descriptors[0]["code"],
                    "text": descriptors[0]["text"],
                    "year_level": descriptors[0]["year_level_code"],
                    "strand": descriptors[0]["strand_title"],
                    "confidence": "low",
                    "reason": "Fallback match - no strong matches found",
                }
            ]

        state["cag_matches"] = matches
        state["primary_descriptor_code"] = matches[0]["code"]
        output = {"matches": matches}
        if token_usage:
            output["_token_usage"] = token_usage
        return StepOutput(content=json.dumps(output))
    finally:
        db.close()
