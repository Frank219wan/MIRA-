"""Small persistence helpers; no domain logic belongs in this module."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from src.contracts.beauty_kit import BeautyKit, ProductCapability
from src.contracts.makeup import StandardRecipe
from src.contracts.matching import MatchingResult
from src.services.tutorial_parser import TutorialParserRun

from .models import (
    BeautyKitRecord,
    MatchingRecord,
    ProductCapabilityRecord,
    ParserRunRecord,
    RecipeRecord,
    TutorialRecord,
)


def save_recipe(session: Session, recipe: StandardRecipe, media_kind: str) -> None:
    payload = recipe.model_dump_json()
    session.merge(
        RecipeRecord(
            recipe_id=recipe.recipe_id,
            source_media_path=recipe.source_media_path,
            payload_json=payload,
        )
    )
    session.merge(
        TutorialRecord(
            tutorial_id=recipe.recipe_id,
            media_path=recipe.source_media_path,
            media_kind=media_kind,
            recipe_id=recipe.recipe_id,
        )
    )
    session.commit()


def get_recipe(session: Session, recipe_id: str) -> StandardRecipe | None:
    record = session.get(RecipeRecord, recipe_id)
    return StandardRecipe.model_validate_json(record.payload_json) if record else None


def save_beauty_kit(session: Session, beauty_kit: BeautyKit) -> None:
    session.merge(
        BeautyKitRecord(
            kit_id=beauty_kit.kit_id, payload_json=beauty_kit.model_dump_json()
        )
    )
    session.commit()


def get_beauty_kit(session: Session) -> BeautyKit | None:
    record = session.query(BeautyKitRecord).order_by(BeautyKitRecord.kit_id).first()
    return BeautyKit.model_validate_json(record.payload_json) if record else None


def save_product_capability(session: Session, capability: ProductCapability) -> None:
    session.merge(
        ProductCapabilityRecord(
            capability_id=capability.capability_id,
            payload_json=capability.model_dump_json(),
        )
    )
    session.commit()


def get_product_capabilities(session: Session) -> list[ProductCapability]:
    records = session.query(ProductCapabilityRecord).order_by(ProductCapabilityRecord.capability_id).all()
    return [ProductCapability.model_validate_json(record.payload_json) for record in records]


def save_matching_result(session: Session, result: MatchingResult) -> None:
    session.merge(
        MatchingRecord(
            matching_id=result.matching_id,
            recipe_id=result.recipe_id,
            beauty_kit_id=result.beauty_kit_id,
            payload_json=result.model_dump_json(),
        )
    )
    session.commit()


def save_parser_run(session: Session, run: TutorialParserRun) -> None:
    """Persist developer diagnostics only when debug runs are enabled."""
    session.merge(
        ParserRunRecord(
            run_id=run.run_id,
            request_id=run.request_id,
            provider_name=run.provider_name,
            model_name=run.model_name,
            prompt_version=run.prompt_version,
            schema_version=run.schema_version,
            input_media_path=run.input_media_path,
            input_media_kind=run.input_media_kind,
            recipe_id=run.recipe_id,
            tutorial_title=run.tutorial_title,
            raw_output_json=_json_text(run.raw_provider_output),
            validated_recipe_json=_json_text(run.validated_recipe),
            validation_error=run.validation_error,
            error_traceback=run.error_traceback,
            duration_ms=run.duration_ms,
        )
    )
    session.commit()


def get_parser_run(session: Session, run_id: str) -> ParserRunRecord | None:
    return session.get(ParserRunRecord, run_id)


def _json_text(value: object | None) -> str | None:
    return json.dumps(value, ensure_ascii=False, default=str) if value is not None else None


def load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
