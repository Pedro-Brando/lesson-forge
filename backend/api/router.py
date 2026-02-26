"""FastAPI routes: SSE generation, debug, and reference endpoints."""

import asyncio
import json
import time
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from backend.api.schemas import (
    ResourceTypeOut,
    StrandOut,
    TeachingFocusOut,
    YearLevelOut,
)
from backend.db.models import (
    GenerationLog,
    ResourceType,
    Strand,
    TeachingFocus,
    YearLevel,
)
from backend.db.session import SessionLocal, get_db
from backend.workflow.lesson_workflow import create_lesson_workflow

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# SSE Generation endpoint
# ---------------------------------------------------------------------------


async def _run_generation(params: dict) -> AsyncIterator[str]:
    """Run the 6-step workflow and yield SSE events."""
    generation_id = str(uuid.uuid4())
    step_timings: dict = {}
    step_names = [
        "input_analyzer",
        "curriculum_matcher",
        "teaching_focus_router",
        "pedagogy_retriever",
        "template_resolver",
        "resource_generator",
    ]

    # Create generation log
    db = SessionLocal()
    try:
        log = GenerationLog(
            id=generation_id,
            request_payload=params,
            status="running",
        )
        db.add(log)
        db.commit()
    finally:
        db.close()

    yield _sse({"type": "generation_started", "generation_id": generation_id})

    # Shared state dict - steps modify this via run_context.session_state
    shared_state = {"params": params}
    workflow = create_lesson_workflow(shared_state)

    try:
        response_iter = workflow.arun(
            input=params.get("topic", ""),
            stream=True,
            stream_events=True,
        )

        current_step_index = 0
        overall_start = time.time()
        step_start = time.time()
        content_chunks = []

        async for event in response_iter:
            event_type = getattr(event, "event", None)

            # Handle step lifecycle events
            if event_type and "step_started" in str(event_type):
                step_start = time.time()
                step_name = step_names[min(current_step_index, len(step_names) - 1)]
                yield _sse({
                    "type": "step_started",
                    "step": step_name,
                    "index": current_step_index + 1,
                })

            elif event_type and "step_completed" in str(event_type):
                duration_ms = int((time.time() - step_start) * 1000)
                step_name = step_names[min(current_step_index, len(step_names) - 1)]
                step_timings[step_name] = duration_ms

                # Access shared state directly (mutated by steps via run_context)
                summary = _get_step_summary(step_name, shared_state)

                yield _sse({
                    "type": "step_completed",
                    "step": step_name,
                    "index": current_step_index + 1,
                    "duration_ms": duration_ms,
                    "summary": summary,
                })

                # Emit detailed events for specific steps
                if step_name == "curriculum_matcher" and "cag_matches" in shared_state:
                    yield _sse({
                        "type": "cag_matches",
                        "matches": shared_state["cag_matches"][:5],
                    })

                if step_name == "teaching_focus_router" and "routing_decision" in shared_state:
                    rd = shared_state["routing_decision"]
                    yield _sse({
                        "type": "routing_decision",
                        "teaching_path": rd.get("teaching_path", ""),
                        "year_band": rd.get("year_band", ""),
                    })

                if step_name == "pedagogy_retriever" and "rag_results" in shared_state:
                    yield _sse({
                        "type": "rag_results",
                        "num_chunks": len(shared_state.get("rag_results", [])),
                        "results": shared_state.get("rag_results", []),
                    })

                if step_name == "template_resolver" and "selected_template" in shared_state:
                    yield _sse({
                        "type": "template_selected",
                        "name": shared_state.get("selected_template", ""),
                        "variables_resolved": len(shared_state.get("template_variables", {})),
                    })

                current_step_index += 1

            # Handle router events
            elif event_type and "router" in str(event_type).lower():
                step_start = time.time()
                yield _sse({
                    "type": "step_started",
                    "step": "teaching_focus_router",
                    "index": 3,
                })

            # Handle streaming content from the resource generator
            elif hasattr(event, "content") and event.content:
                content_chunks.append(event.content)
                yield _sse({
                    "type": "content_chunk",
                    "content": event.content,
                })

        total_duration_ms = int((time.time() - overall_start) * 1000)

        # Update generation log from shared state
        db = SessionLocal()
        try:
            log = db.query(GenerationLog).filter_by(id=generation_id).first()
            if log:
                log.matched_descriptors = shared_state.get("cag_matches")
                log.routing_decision = shared_state.get("routing_decision")
                log.rag_results = shared_state.get("rag_results")
                log.selected_template = shared_state.get("selected_template")
                log.resolved_prompt = shared_state.get("resolved_prompt")
                log.generated_resource = shared_state.get("generated_resource", "".join(content_chunks))
                log.step_timings = step_timings
                log.status = "completed"
                db.commit()
        finally:
            db.close()

        yield _sse({
            "type": "generation_completed",
            "generation_id": generation_id,
            "total_duration_ms": total_duration_ms,
        })

    except Exception as e:
        db = SessionLocal()
        try:
            log = db.query(GenerationLog).filter_by(id=generation_id).first()
            if log:
                log.status = "error"
                log.generated_resource = str(e)
                db.commit()
        finally:
            db.close()

        yield _sse({
            "type": "error",
            "message": str(e),
            "generation_id": generation_id,
        })


def _get_step_summary(step_name: str, state: dict) -> dict:
    """Extract a brief summary for a completed step."""
    if step_name == "input_analyzer":
        parsed = state.get("parsed_input", {})
        return {"topic": parsed.get("topic", ""), "intent": parsed.get("intent", "")}
    if step_name == "curriculum_matcher":
        matches = state.get("cag_matches", [])
        return {"num_matches": len(matches)}
    if step_name in ("teaching_focus_router", "explicit_instruction_enrichment",
                      "inquiry_enrichment", "fluency_enrichment",
                      "assessment_enrichment", "planning_enrichment"):
        rd = state.get("routing_decision", {})
        return {"path": rd.get("teaching_path", ""), "band": rd.get("year_band", "")}
    if step_name == "pedagogy_retriever":
        return {"num_chunks": len(state.get("rag_results", []))}
    if step_name == "template_resolver":
        return {"template": state.get("selected_template", "")}
    return {}


def _sse(data: dict) -> str:
    return json.dumps(data)


@router.post("/generate")
async def generate_resource(
    topic: str = Form(...),
    year_level: str = Form("Year 5"),
    strand: str = Form("Number"),
    teaching_focus: str = Form("explicit_instruction"),
    resource_type: str = Form("worked_example_study"),
    additional_context: str = Form(""),
):
    """Generate an educational resource via SSE streaming."""
    params = {
        "topic": topic,
        "year_level": year_level,
        "strand": strand,
        "teaching_focus": teaching_focus,
        "resource_type": resource_type,
        "additional_context": additional_context,
    }

    return EventSourceResponse(
        _run_generation(params),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Debug endpoint
# ---------------------------------------------------------------------------


@router.get("/debug/{generation_id}")
def get_debug(generation_id: str, db: Session = Depends(get_db)):
    """Return full generation log for debugging."""
    log = db.query(GenerationLog).filter_by(id=generation_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Generation not found")
    return {
        "id": str(log.id),
        "status": log.status,
        "request_payload": log.request_payload,
        "matched_descriptors": log.matched_descriptors,
        "routing_decision": log.routing_decision,
        "rag_results": log.rag_results,
        "selected_template": log.selected_template,
        "resolved_prompt": log.resolved_prompt,
        "generated_resource": log.generated_resource,
        "step_timings": log.step_timings,
        "created_at": str(log.created_at) if log.created_at else None,
    }


# ---------------------------------------------------------------------------
# Reference data endpoints
# ---------------------------------------------------------------------------


@router.get("/reference/year-levels", response_model=list[YearLevelOut])
def list_year_levels(db: Session = Depends(get_db)):
    return db.query(YearLevel).order_by(YearLevel.sort_order).all()


@router.get("/reference/strands", response_model=list[StrandOut])
def list_strands(db: Session = Depends(get_db)):
    return db.query(Strand).order_by(Strand.title).all()


@router.get("/reference/teaching-focuses", response_model=list[TeachingFocusOut])
def list_teaching_focuses(db: Session = Depends(get_db)):
    return db.query(TeachingFocus).order_by(TeachingFocus.name).all()


@router.get("/reference/resource-types", response_model=list[ResourceTypeOut])
def list_resource_types(
    teaching_focus: str = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(ResourceType)
    if teaching_focus:
        q = q.filter_by(teaching_focus_slug=teaching_focus)
    return q.order_by(ResourceType.name).all()
