"""Step 6: Generate the lesson resource with streaming output."""

from typing import AsyncIterator, Union

from agno.run import RunContext
from agno.run.workflow import WorkflowRunOutputEvent
from agno.workflow.step import StepInput, StepOutput

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

    async for event in response_iter:
        yield event
        # Collect content for storage
        if hasattr(event, "content") and event.content:
            full_content.append(event.content)

    # Get final response
    response = agent.get_last_run_output()
    final_content = response.content if response and response.content else "".join(full_content)

    state["generated_resource"] = final_content
    yield StepOutput(content=final_content)
