"""Step 1: Parse teacher's free-text request using an LLM agent."""

import json

from agno.run import RunContext
from agno.workflow.step import StepInput, StepOutput

from backend.config import settings
from backend.workflow.agents import get_input_analyzer


def input_analyzer_step(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """Parse the teacher's request into structured fields."""
    state = run_context.session_state
    params = state["params"]

    prompt = f"""Parse this teacher's resource request:

Topic: {params["topic"]}
Year Level: {params["year_level"]}
Strand: {params["strand"]}
Teaching Focus: {params["teaching_focus"]}
Resource Type: {params["resource_type"]}
Additional Context: {params.get("additional_context", "")}

Return a JSON object with:
- "topic": the core mathematical topic (cleaned up)
- "year_level": the year level as stated
- "strand": the mathematical strand
- "intent": one of "instruction", "practice", "assessment", "inquiry", "planning"
- "keywords": list of 3-5 key mathematical terms

Return ONLY valid JSON."""

    agent = get_input_analyzer()
    response = agent.run(prompt)
    content = response.content

    # Extract token usage metrics
    token_usage = None
    if response.metrics:
        token_usage = {
            "input_tokens": response.metrics.input_tokens or 0,
            "output_tokens": response.metrics.output_tokens or 0,
            "total_tokens": response.metrics.total_tokens or 0,
            "model": settings.OPENAI_MODEL_FAST,
        }

    # Parse the JSON response
    try:
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        parsed = {
            "topic": params["topic"],
            "year_level": params["year_level"],
            "strand": params["strand"],
            "intent": "instruction",
            "keywords": [params["topic"]],
        }

    state["parsed_input"] = parsed
    output = dict(parsed)
    if token_usage:
        output["_token_usage"] = token_usage
    return StepOutput(content=json.dumps(output))
