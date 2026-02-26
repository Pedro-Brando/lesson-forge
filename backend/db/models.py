import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class YearLevel(Base):
    __tablename__ = "year_levels"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    title = Column(String(50), nullable=False)
    sort_order = Column(Integer, nullable=False)
    level_description = Column(Text)
    band = Column(String(20), nullable=False)

    content_descriptors = relationship("ContentDescriptor", back_populates="year_level")
    achievement_standards = relationship("AchievementStandard", back_populates="year_level")


class Strand(Base):
    __tablename__ = "strands"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    title = Column(String(50), unique=True, nullable=False)

    content_descriptors = relationship("ContentDescriptor", back_populates="strand")


class ContentDescriptor(Base):
    __tablename__ = "content_descriptors"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    text = Column(Text, nullable=False)
    year_level_code = Column(String(20), ForeignKey("year_levels.code"), nullable=False)
    strand_title = Column(String(50), ForeignKey("strands.title"), nullable=False)

    year_level = relationship("YearLevel", back_populates="content_descriptors")
    strand = relationship("Strand", back_populates="content_descriptors")
    elaborations = relationship("Elaboration", back_populates="content_descriptor")


class Elaboration(Base):
    __tablename__ = "elaborations"

    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True, nullable=False)
    text = Column(Text, nullable=False)
    content_descriptor_code = Column(
        String(20), ForeignKey("content_descriptors.code"), nullable=False
    )

    content_descriptor = relationship("ContentDescriptor", back_populates="elaborations")


class AchievementStandard(Base):
    __tablename__ = "achievement_standards"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    text = Column(Text, nullable=False)
    year_level_code = Column(String(20), ForeignKey("year_levels.code"), nullable=False)

    year_level = relationship("YearLevel", back_populates="achievement_standards")


class TeachingFocus(Base):
    __tablename__ = "teaching_focuses"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    slug = Column(String(50), unique=True, nullable=False)

    resource_types = relationship("ResourceType", back_populates="teaching_focus")


class ResourceType(Base):
    __tablename__ = "resource_types"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    teaching_focus_slug = Column(
        String(50), ForeignKey("teaching_focuses.slug"), nullable=False
    )

    teaching_focus = relationship("TeachingFocus", back_populates="resource_types")


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    resource_type_slug = Column(String(100), ForeignKey("resource_types.slug"), nullable=True)
    teaching_focus_slug = Column(String(50), ForeignKey("teaching_focuses.slug"), nullable=True)
    year_band = Column(String(20), nullable=True)
    template_body = Column(Text, nullable=False)
    priority = Column(Integer, default=0)


class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_payload = Column(JSONB)
    matched_descriptors = Column(JSONB)
    routing_decision = Column(JSONB)
    rag_results = Column(JSONB)
    selected_template = Column(String(200))
    resolved_prompt = Column(Text)
    generated_resource = Column(Text)
    step_timings = Column(JSONB)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, server_default=func.now())
