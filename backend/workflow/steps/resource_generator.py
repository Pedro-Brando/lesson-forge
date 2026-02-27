"""Step 6: Generate the lesson resource with streaming output."""

import json
from typing import AsyncIterator, Union

from agno.run import RunContext
from agno.run.workflow import WorkflowRunOutputEvent
from agno.workflow.step import StepInput, StepOutput

from backend.config import settings
from backend.workflow.agents import get_resource_generator


async def resource_generator_step(
    step_input: StepInput, run_context: RunContext
) -> AsyncIterator[Union[WorkflowRunOutputEvent, StepOutput]]:
    """Generate the final resource using GPT-4o with streaming."""
    state = run_context.session_state
    resolved_prompt = state.get("resolved_prompt", "Generate a mathematics resource.")

    agent = get_resource_generator()

    # Stream the agent response
    response_iter = agent.arun(resolved_prompt, stream=True, stream_events=True)
    full_content = []
    token_usage = None

    async for event in response_iter:
        yield event
        # Collect content for storage
        if hasattr(event, "content") and event.content:
            full_content.append(event.content)
        # Capture metrics from RunCompletedEvent (carries .metrics after streaming)
        if hasattr(event, "metrics") and event.metrics and not token_usage:
            m = event.metrics
            if m.input_tokens or m.output_tokens:
                token_usage = {
                    "input_tokens": m.input_tokens or 0,
                    "output_tokens": m.output_tokens or 0,
                    "total_tokens": m.total_tokens or 0,
                    "model": settings.OPENAI_MODEL_GENERATION,
                }

    # Fallback: try run output or session metrics
    if not token_usage:
        response = agent.get_last_run_output()
        if response and response.metrics:
            token_usage = {
                "input_tokens": response.metrics.input_tokens or 0,
                "output_tokens": response.metrics.output_tokens or 0,
                "total_tokens": response.metrics.total_tokens or 0,
                "model": settings.OPENAI_MODEL_GENERATION,
            }
    if not token_usage and hasattr(agent, "session") and agent.session:
        m = getattr(agent.session, "session_metrics", None)
        if m and (m.input_tokens or m.output_tokens):
            token_usage = {
                "input_tokens": m.input_tokens or 0,
                "output_tokens": m.output_tokens or 0,
                "total_tokens": m.total_tokens or 0,
                "model": settings.OPENAI_MODEL_GENERATION,
            }

    final_content = "".join(full_content)
    state["generated_resource"] = final_content
    yield StepOutput(content=final_content)
    # Emit token usage as a separate small event after the content
    if token_usage:
        yield StepOutput(content=json.dumps({"_generator_token_usage": token_usage}))
