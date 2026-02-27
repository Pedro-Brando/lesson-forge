"""FastAPI routes: SSE generation, debug, and reference endpoints."""

import asyncio
import json
import time
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from backend.config import settings

from backend.api.schemas import (
    GenerationSummaryOut,
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
        seen_step_data = set()  # Track which step data we've emitted
        # Collect debug data to persist in generation_logs
        debug_cag_matches = None
        debug_routing = None
        debug_rag = None
        debug_template = None
        debug_resolved_prompt = None
        debug_token_usage = {}  # Collect token data from step event payloads

        async for event in response_iter:
            event_type = str(getattr(event, "event", "") or "")
            content = getattr(event, "content", None)

            # Capture token metrics from RunCompletedEvent (carries .metrics after streaming)
            evt_metrics = getattr(event, "metrics", None)
            if evt_metrics and hasattr(evt_metrics, "input_tokens") and (evt_metrics.input_tokens or evt_metrics.output_tokens):
                # Determine which step this belongs to based on model details
                model_name = settings.OPENAI_MODEL_GENERATION  # default
                if hasattr(evt_metrics, "details") and evt_metrics.details and evt_metrics.details.get("model"):
                    model_info = evt_metrics.details["model"]
                    if model_info and hasattr(model_info[0], "id"):
                        model_name = model_info[0].id
                # If resource_generator not yet captured, this is likely from it
                if "resource_generator" not in debug_token_usage:
                    debug_token_usage["resource_generator"] = {
                        "input_tokens": evt_metrics.input_tokens or 0,
                        "output_tokens": evt_metrics.output_tokens or 0,
                        "total_tokens": evt_metrics.total_tokens or 0,
                        "model": model_name,
                    }

            # Handle step lifecycle events from the workflow
            if "step_started" in event_type or "step_start" in event_type:
                step_start = time.time()
                step_name = step_names[min(current_step_index, len(step_names) - 1)]
                yield _sse({
                    "type": "step_started",
                    "step": step_name,
                    "index": current_step_index + 1,
                })

            elif "step_completed" in event_type or "step_complete" in event_type:
                duration_ms = int((time.time() - step_start) * 1000)
                step_name = step_names[min(current_step_index, len(step_names) - 1)]
                step_timings[step_name] = duration_ms

                yield _sse({
                    "type": "step_completed",
                    "step": step_name,
                    "index": current_step_index + 1,
                    "duration_ms": duration_ms,
                })

                current_step_index += 1
                step_start = time.time()

            elif "router" in event_type.lower():
                step_start = time.time()

            elif content:
                content_str = str(content)
                stripped = content_str.strip()

                # Detect step-output JSON and emit debug events instead of content.
                # Content can arrive as str, dict, or Agno event objects — handle all.
                step_output_suppressed = False
                if stripped.startswith("{"):
                    # Parse JSON robustly regardless of content type
                    data = None
                    try:
                        if isinstance(content, dict):
                            data = content
                        else:
                            data = json.loads(stripped)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        data = None

                    if isinstance(data, dict):
                        step_output_suppressed = True

                        # Step 1 output: parsed_input
                        if "keywords" in data and "intent" in data and "parsed_input" not in seen_step_data:
                            seen_step_data.add("parsed_input")
                            if data.get("_token_usage"):
                                debug_token_usage["input_analyzer"] = data["_token_usage"]
                            step_timings["input_analyzer"] = int((time.time() - step_start) * 1000)
                            yield _sse({"type": "step_started", "step": "input_analyzer", "index": 1})
                            yield _sse({"type": "step_completed", "step": "input_analyzer", "index": 1,
                                        "duration_ms": step_timings["input_analyzer"],
                                        "summary": {"topic": data.get("topic", ""), "intent": data.get("intent", "")}})
                            step_start = time.time()

                        # Step 2 output: CAG matches
                        elif "matches" in data and "cag" not in seen_step_data:
                            seen_step_data.add("cag")
                            if data.get("_token_usage"):
                                debug_token_usage["curriculum_matcher"] = data["_token_usage"]
                            debug_cag_matches = data["matches"][:5]
                            step_timings["curriculum_matcher"] = int((time.time() - step_start) * 1000)
                            yield _sse({"type": "step_started", "step": "curriculum_matcher", "index": 2})
                            yield _sse({"type": "step_completed", "step": "curriculum_matcher", "index": 2,
                                        "duration_ms": step_timings["curriculum_matcher"],
                                        "summary": {"num_matches": len(data["matches"])}})
                            yield _sse({"type": "cag_matches", "matches": debug_cag_matches})
                            step_start = time.time()

                        # Step 3 output: routing decision
                        elif "teaching_path" in data and "routing" not in seen_step_data:
                            seen_step_data.add("routing")
                            debug_routing = {"teaching_path": data.get("teaching_path", ""), "year_band": data.get("year_band", "")}
                            step_timings["teaching_focus_router"] = int((time.time() - step_start) * 1000)
                            yield _sse({"type": "step_started", "step": "teaching_focus_router", "index": 3})
                            yield _sse({"type": "step_completed", "step": "teaching_focus_router", "index": 3,
                                        "duration_ms": step_timings["teaching_focus_router"],
                                        "summary": {"path": debug_routing["teaching_path"], "band": debug_routing["year_band"]}})
                            yield _sse({"type": "routing_decision", **debug_routing})
                            step_start = time.time()

                        # Step 4 output: RAG results
                        elif "num_chunks" in data and "rag" not in seen_step_data:
                            seen_step_data.add("rag")
                            debug_rag = {"num_chunks": data.get("num_chunks", 0), "results": data.get("results", [])}
                            step_timings["pedagogy_retriever"] = int((time.time() - step_start) * 1000)
                            yield _sse({"type": "step_started", "step": "pedagogy_retriever", "index": 4})
                            yield _sse({"type": "step_completed", "step": "pedagogy_retriever", "index": 4,
                                        "duration_ms": step_timings["pedagogy_retriever"],
                                        "summary": {"num_chunks": debug_rag["num_chunks"]}})
                            yield _sse({"type": "rag_results", **debug_rag})
                            step_start = time.time()

                        # Step 5 output: template selected
                        elif "variables_resolved" in data and "template" not in seen_step_data:
                            seen_step_data.add("template")
                            debug_template = data.get("name", "")
                            debug_resolved_prompt = data.get("resolved_prompt", "")
                            step_timings["template_resolver"] = int((time.time() - step_start) * 1000)
                            yield _sse({"type": "step_started", "step": "template_resolver", "index": 5})
                            yield _sse({"type": "step_completed", "step": "template_resolver", "index": 5,
                                        "duration_ms": step_timings["template_resolver"],
                                        "summary": {"template": debug_template}})
                            yield _sse({"type": "template_selected",
                                        "name": debug_template,
                                        "variables_resolved": data.get("variables_resolved", 0)})
                            # Emit resolved prompt for the prompt viewer
                            if debug_resolved_prompt:
                                yield _sse({
                                    "type": "resolved_prompt",
                                    "prompt": debug_resolved_prompt[:5000],
                                })
                            # Next content will be from the generator
                            yield _sse({"type": "step_started", "step": "resource_generator", "index": 6})
                            step_start = time.time()

                        # Generator token usage (emitted as separate StepOutput after content)
                        elif "_generator_token_usage" in data:
                            debug_token_usage["resource_generator"] = data["_generator_token_usage"]

                    # Fallback: suppress step-output patterns even if JSON parsing failed
                    # (handles Agno objects whose str() contains step data)
                    if not step_output_suppressed:
                        _markers = ["num_chunks", "teaching_path", "variables_resolved",
                                    '"matches"', '"keywords"', '"intent"',
                                    "_generator_token_usage"]
                        if any(m in content_str for m in _markers):
                            step_output_suppressed = True

                if step_output_suppressed:
                    continue

                # Stream actual content tokens from the generator.
                # Skip large chunks (>200 chars) which are duplicate final StepOutputs.
                if len(content_str) <= 200:
                    content_chunks.append(content_str)
                    yield _sse({
                        "type": "content_chunk",
                        "content": content_str,
                    })

        total_duration_ms = int((time.time() - overall_start) * 1000)

        # Capture resource_generator timing (from last step_start to now)
        if "resource_generator" not in step_timings and content_chunks:
            step_timings["resource_generator"] = int((time.time() - step_start) * 1000)

        # Build token summary from event-collected data
        token_summary = None
        token_data = debug_token_usage
        if token_data:
            total_in = sum(s.get("input_tokens", 0) for s in token_data.values())
            total_out = sum(s.get("output_tokens", 0) for s in token_data.values())
            token_summary = {
                "steps": token_data,
                "total_input": total_in,
                "total_output": total_out,
                "total": total_in + total_out,
            }
            yield _sse({"type": "token_usage", **token_summary})

        # Update generation log with collected data + debug trace
        db = SessionLocal()
        try:
            log = db.query(GenerationLog).filter_by(id=generation_id).first()
            if log:
                log.generated_resource = "".join(content_chunks)
                log.step_timings = step_timings
                log.token_usage = token_summary
                log.matched_descriptors = debug_cag_matches
                log.routing_decision = debug_routing
                log.rag_results = debug_rag
                log.selected_template = debug_template
                log.resolved_prompt = debug_resolved_prompt
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
        "token_usage": log.token_usage,
        "created_at": str(log.created_at) if log.created_at else None,
    }


# ---------------------------------------------------------------------------
# Generation history endpoints
# ---------------------------------------------------------------------------


@router.delete("/generations/{generation_id}")
def delete_generation(generation_id: str, db: Session = Depends(get_db)):
    """Delete a single generation log."""
    log = db.query(GenerationLog).filter_by(id=generation_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Generation not found")
    db.delete(log)
    db.commit()
    return {"ok": True}


@router.delete("/generations")
def delete_all_generations(db: Session = Depends(get_db)):
    """Delete all generation logs."""
    count = db.query(GenerationLog).delete()
    db.commit()
    return {"ok": True, "deleted": count}


@router.get("/generations", response_model=list[GenerationSummaryOut])
def list_generations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return recent generations for the history view."""
    logs = (
        db.query(GenerationLog)
        .order_by(GenerationLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    results = []
    for log in logs:
        payload = log.request_payload or {}
        results.append(
            GenerationSummaryOut(
                id=str(log.id),
                status=log.status or "unknown",
                topic=payload.get("topic"),
                year_level=payload.get("year_level"),
                strand=payload.get("strand"),
                teaching_focus=payload.get("teaching_focus"),
                resource_type=payload.get("resource_type"),
                step_timings=log.step_timings,
                token_usage=log.token_usage,
                created_at=log.created_at,
            )
        )
    return results


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
