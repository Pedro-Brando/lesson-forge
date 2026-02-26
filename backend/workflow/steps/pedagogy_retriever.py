"""Step 4: RAG - Retrieve relevant elaborations and pedagogy docs from pgvector."""

import json

from agno.run import RunContext
from agno.workflow.step import StepInput, StepOutput

from backend.knowledge.pedagogy_kb import get_knowledge_base


def pedagogy_retriever_step(step_input: StepInput, run_context: RunContext) -> StepOutput:
    """Query pgvector for relevant elaborations and pedagogy content."""
    state = run_context.session_state
    parsed = state["parsed_input"]
    routing = state["routing_decision"]
    cag_matches = state.get("cag_matches", [])

    # Build semantic query from matched descriptors + teaching focus + year level
    match_texts = [m.get("text", "") for m in cag_matches[:3]]
    query = (
        f"{parsed['topic']} {parsed.get('strand', '')} "
        f"{' '.join(match_texts)} "
        f"{routing['teaching_path']} {parsed.get('year_level', '')}"
    )

    try:
        kb = get_knowledge_base()
        results = kb.search(query, max_results=5)
    except Exception:
        results = []

    rag_results = []
    rag_context_parts = []
    for doc in results:
        result_entry = {
            "content": doc.content[:200] if hasattr(doc, "content") else str(doc)[:200],
            "name": getattr(doc, "name", "unknown"),
        }
        rag_results.append(result_entry)
        content = doc.content if hasattr(doc, "content") else str(doc)
        rag_context_parts.append(content)

    rag_context = "\n\n".join(rag_context_parts) if rag_context_parts else ""

    state["rag_results"] = rag_results
    state["rag_context"] = rag_context

    return StepOutput(
        content=json.dumps({"num_chunks": len(rag_results), "results": rag_results})
    )
