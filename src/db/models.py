"""Deliberately small JSON-payload tables for Week 1 local persistence."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RecipeRecord(Base):
    __tablename__ = "recipes"

    recipe_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_media_path: Mapped[str] = mapped_column(String(512))
    payload_json: Mapped[str] = mapped_column(Text)


class TutorialRecord(Base):
    __tablename__ = "tutorials"

    tutorial_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    media_path: Mapped[str] = mapped_column(String(512))
    media_kind: Mapped[str] = mapped_column(String(32))
    recipe_id: Mapped[str] = mapped_column(String(128))


class BeautyKitRecord(Base):
    __tablename__ = "beauty_kits"

    kit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)


class ProductCapabilityRecord(Base):
    __tablename__ = "product_capabilities"

    capability_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)


class MatchingRecord(Base):
    __tablename__ = "matching_results"

    matching_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    recipe_id: Mapped[str] = mapped_column(String(128))
    beauty_kit_id: Mapped[str] = mapped_column(String(128))
    payload_json: Mapped[str] = mapped_column(Text)


class ParserRunRecord(Base):
    """Development-only parser diagnostics; contains references, never media bytes."""

    __tablename__ = "parser_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_name: Mapped[str] = mapped_column(String(128))
    model_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_media_path: Mapped[str] = mapped_column(String(512))
    input_media_kind: Mapped[str] = mapped_column(String(32))
    recipe_id: Mapped[str] = mapped_column(String(128))
    tutorial_title: Mapped[str] = mapped_column(String(512))
    raw_output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_recipe_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)


class TutorialExplanationRunRecord(Base):
    """Development trace for wording generation; CV values remain verbatim JSON."""

    __tablename__ = "tutorial_explanation_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recipe_id: Mapped[str] = mapped_column(String(128))
    step_index: Mapped[int] = mapped_column()
    action_id: Mapped[str] = mapped_column(String(32))
    source_standard_action_json: Mapped[str] = mapped_column(Text)
    face_profile_id: Mapped[str] = mapped_column(String(128))
    face_profile_version: Mapped[str] = mapped_column(String(32))
    cv_personalized_action_json: Mapped[str] = mapped_column(Text)
    deterministic_facts_json: Mapped[str] = mapped_column(Text)
    applied_rules_json: Mapped[str] = mapped_column(Text)
    explanation_generator_version: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(64))
    provider_name: Mapped[str] = mapped_column(String(128))
    model_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    fallback_used: Mapped[bool] = mapped_column()
    response_json: Mapped[str] = mapped_column(Text)
