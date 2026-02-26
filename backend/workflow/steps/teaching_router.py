"""Step 3: Route by teaching focus + year level conditions."""

from agno.run import RunContext
from agno.workflow.step import StepInput, StepOutput

from backend.db.session import SessionLocal
from backend.db.models import YearLevel


TEACHING_FOCUS_NOTES = {
    "explicit_instruction": (
        "Structure the resource using the I Do / We Do / You Do framework. "
        "Include clear teacher modelling, guided practice with prompting questions, "
        "and independent practice with success criteria. Use worked examples to reduce cognitive load."
    ),
    "deep_learning_inquiry": (
        "Design for inquiry and deep thinking. Include open-ended questions, "
        "thinking routines (See-Think-Wonder, Claim-Support-Question), "
        "and opportunities for mathematical reasoning and justification. "
        "Encourage productive struggle and multiple solution paths."
    ),
    "fluency_practice": (
        "Focus on building procedural fluency through scaffolded practice. "
        "Include varied question types progressing from foundational to extension. "
        "Target the Zone of Proximal Development with enabling and extending prompts. "
        "Ensure sufficient repetition for skill automaticity."
    ),
    "assessment_feedback": (
        "Design for formative assessment and feedback. Include clear success criteria, "
        "diagnostic questions targeting common misconceptions, and self-assessment opportunities. "
        "Provide a marking guide and suggested follow-up actions based on student responses."
    ),
    "planning": (
        "Create a planning resource that maps curriculum expectations clearly. "
        "Include curriculum alignment details, learning progressions, "
        "and connections across strands. Support teacher understanding of the 'big ideas' "
        "and how concepts develop across year levels."
    ),
}

YEAR_BAND_NOTES = {
    "early_years": (
        "EARLY YEARS FOCUS: Use simple, age-appropriate language. "
        "Include concrete materials (counters, blocks, ten frames). "
        "Incorporate play-based and hands-on activities. "
        "Use visual representations and familiar contexts."
    ),
    "primary": (
        "PRIMARY FOCUS: Balance concrete and abstract representations. "
        "Include real-world contexts relevant to primary students. "
        "Build on developing mathematical vocabulary. "
        "Support the transition from additive to multiplicative thinking."
    ),
    "secondary": (
        "SECONDARY FOCUS: Use formal mathematical notation and terminology. "
        "Include abstract reasoning and algebraic thinking. "
        "Connect to real-world applications (STEM, finance, data). "
        "Encourage generalisation and mathematical argumentation."
    ),
}


def teaching_router_step(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """Route processing based on teaching focus and year band."""
    state = run_context.session_state
    params = state["params"]
    parsed = state["parsed_input"]

    teaching_focus = params["teaching_focus"]
    year_level_title = parsed.get("year_level", params.get("year_level", "Year 5"))

    # Determine year band from DB
    db = SessionLocal()
    try:
        yl = db.query(YearLevel).filter(
            YearLevel.title == year_level_title
        ).first()
        if not yl:
            # Try matching by code
            code_map = {
                "Foundation Year": "MATMATFY",
                "Year 1": "MATMATY1", "Year 2": "MATMATY2",
                "Year 3": "MATMATY3", "Year 4": "MATMATY4",
                "Year 5": "MATMATY5", "Year 6": "MATMATY6",
                "Year 7": "MATMATY7", "Year 8": "MATMATY8",
                "Year 9": "MATMATY9", "Year 10": "MATMATY10",
            }
            code = code_map.get(year_level_title)
            if code:
                yl = db.query(YearLevel).filter_by(code=code).first()

        year_band = yl.band if yl else "primary"
        year_level_code = yl.code if yl else "MATMATY5"
    finally:
        db.close()

    # Get teaching focus and year band specific notes
    focus_notes = TEACHING_FOCUS_NOTES.get(teaching_focus, TEACHING_FOCUS_NOTES["explicit_instruction"])
    band_notes = YEAR_BAND_NOTES.get(year_band, YEAR_BAND_NOTES["primary"])

    routing_decision = {
        "teaching_path": teaching_focus,
        "year_band": year_band,
        "year_level_code": year_level_code,
        "pedagogy_notes": f"{focus_notes}\n\n{band_notes}",
    }

    state["routing_decision"] = routing_decision
    state["year_band"] = year_band
    state["year_level_code"] = year_level_code

    import json
    return StepOutput(content=json.dumps(routing_decision))
