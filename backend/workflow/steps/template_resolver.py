"""Step 5: Select and resolve prompt template from DB."""

import json

from agno.run import RunContext
from agno.workflow.step import StepInput, StepOutput

from backend.db.session import SessionLocal
from backend.services.template_service import resolve_template, select_template


def template_resolver_step(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """Select the best template and resolve all variable placeholders from DB."""
    state = run_context.session_state
    params = state["params"]
    routing = state["routing_decision"]

    db = SessionLocal()
    try:
        template = select_template(
            db=db,
            resource_type_slug=params["resource_type"],
            teaching_focus_slug=params["teaching_focus"],
            year_band=routing["year_band"],
        )

        if not template:
            state["resolved_prompt"] = f"Generate a {params['resource_type']} resource about {params['topic']}"
            state["selected_template"] = "none"
            state["template_variables"] = {}
            return StepOutput(content=json.dumps({"name": "none", "error": "No template found"}))

        resolved_prompt, variables = resolve_template(
            db=db,
            template=template,
            matched_descriptor_code=state.get("primary_descriptor_code", ""),
            year_level_code=state.get("year_level_code", "MATMATY5"),
            resource_type_slug=params["resource_type"],
            teaching_focus_slug=params["teaching_focus"],
            rag_context=state.get("rag_context", ""),
            additional_context=params.get("additional_context", ""),
        )

        # Prepend routing pedagogy notes
        pedagogy_notes = routing.get("pedagogy_notes", "")
        if pedagogy_notes:
            resolved_prompt = f"**Pedagogical Guidance:**\n{pedagogy_notes}\n\n{resolved_prompt}"

        state["resolved_prompt"] = resolved_prompt
        state["selected_template"] = template.name
        state["template_variables"] = {k: v[:100] for k, v in variables.items()}

        return StepOutput(
            content=json.dumps({
                "name": template.name,
                "priority": template.priority,
                "variables_resolved": len(variables),
                "resolved_prompt": resolved_prompt[:5000],
            })
        )
    finally:
        db.close()
