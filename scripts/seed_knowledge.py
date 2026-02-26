"""Seed the pgvector knowledge base with elaborations and pedagogy docs."""

import json
import sys
from pathlib import Path

from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType

from backend.config import settings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_knowledge_base() -> Knowledge:
    vector_db = PgVector(
        table_name="pedagogy_vectors",
        db_url=settings.DATABASE_URL,
        search_type=SearchType.vector,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    )
    return Knowledge(
        name="Pedagogy Knowledge Base",
        description="Educational pedagogy documents and curriculum elaborations",
        vector_db=vector_db,
    )


def seed_pedagogy_docs(kb: Knowledge):
    """Load markdown pedagogy documents into the knowledge base."""
    pedagogy_dir = DATA_DIR / "pedagogy"
    for md_file in sorted(pedagogy_dir.glob("*.md")):
        print(f"  Loading pedagogy doc: {md_file.name}")
        kb.insert(path=str(md_file))


def seed_elaborations(kb: Knowledge):
    """Load curriculum elaborations as text documents into the knowledge base.

    Groups elaborations by content descriptor to create meaningful chunks.
    """
    with open(DATA_DIR / "curriculum.json", encoding="utf-8") as f:
        data = json.load(f)

    content_items = data["content_items"]

    # Group elaborations by content descriptor into text chunks
    chunks = []
    for item in content_items:
        loc = item["location"]
        elabs = item.get("elaborations", [])
        if not elabs:
            continue

        elab_texts = "\n".join(f"- {e['text']}" for e in elabs)
        chunk_text = (
            f"Content Descriptor {item['code']} ({loc['level']} - {loc['strand']}): "
            f"{item['text']}\n\nElaborations:\n{elab_texts}"
        )
        chunks.append((item["code"], chunk_text))

    print(f"  Loading {len(chunks)} elaboration chunks into knowledge base...")

    # Write chunks to temporary files for Knowledge.insert() to process
    import tempfile
    import os

    tmp_dir = tempfile.mkdtemp(prefix="lessonforge_elabs_")
    try:
        for code, text in chunks:
            filepath = os.path.join(tmp_dir, f"{code}.txt")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)

        # Insert the directory of text files
        kb.insert(path=tmp_dir)
        print(f"  Inserted {len(chunks)} elaboration documents")
    finally:
        # Cleanup temp files
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    print("Seeding knowledge base...")
    kb = get_knowledge_base()

    try:
        seed_pedagogy_docs(kb)
        seed_elaborations(kb)
        print("Knowledge base seeded successfully.")
    except Exception as e:
        print(f"Knowledge seed failed: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
