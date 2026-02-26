"""PgVector knowledge base for pedagogy documents and elaborations."""

from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType

from backend.config import settings


def get_knowledge_base() -> Knowledge:
    vector_db = PgVector(
        table_name="pedagogy_vectors",
        db_url=settings.DATABASE_URL,
        search_type=SearchType.vector,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    )
    return Knowledge(
        name="Pedagogy Knowledge Base",
        description="Educational pedagogy documents and curriculum elaborations for mathematics teaching",
        vector_db=vector_db,
    )
