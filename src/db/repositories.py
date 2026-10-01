"""Small persistence helpers; no domain logic belongs in this module."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from src.contracts.beauty_kit import BeautyKit, ProductCapability
from src.contracts.makeup import StandardRecipe
from src.contracts.matching import MatchingResult
from src.services.tutorial_parser import TutorialParserRun
from src.services.tutorial_explanation import TutorialExplanationRun

from .models import (
    BeautyKitRecord,
    MatchingRecord,
    ProductCapabilityRecord,
    ParserRunRecord,
    RecipeRecord,
    TutorialRecord,
    TutorialExplanationRunRecord,
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


def get_beauty_kit_by_id(session: Session, kit_id: str) -> BeautyKit | None:
    record = session.get(BeautyKitRecord, kit_id)
    return BeautyKit.model_validate_json(record.payload_json) if record else None


def save_product_capability(session: Session, capability: ProductCapability) -> None:
    session.merge(
        ProductCapabilityRecord(
            capability_id=capability.capability_id,
            payload_json=capability.model_dump_json(),
        )
    )
    session.commit()


def get_product_capability(
    session: Session, capability_id: str
) -> ProductCapability | None:
    record = session.get(ProductCapabilityRecord, capability_id)
    return ProductCapability.model_validate_json(record.payload_json) if record else None


def list_product_capabilities(session: Session) -> list[ProductCapability]:
    records = session.query(ProductCapabilityRecord).order_by(
        ProductCapabilityRecord.capability_id
    )
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


def save_tutorial_explanation_run(
    session: Session, run: TutorialExplanationRun
) -> None:
    session.merge(
        TutorialExplanationRunRecord(
            run_id=run.run_id,
            request_id=run.request_id,
            recipe_id=run.recipe_id,
            step_index=run.step_index,
            action_id=run.action_id,
            source_standard_action_json=_json_text(run.source_standard_action) or "{}",
            face_profile_id=run.face_profile_id,
            face_profile_version=run.face_profile_version,
            cv_personalized_action_json=_json_text(run.cv_personalized_action) or "{}",
            deterministic_facts_json=_json_text(run.deterministic_facts) or "{}",
            applied_rules_json=_json_text(run.applied_rules) or "[]",
            explanation_generator_version=run.explanation_generator_version,
            prompt_version=run.prompt_version,
            provider_name=run.provider_name,
            model_name=run.model_name,
            fallback_used=run.fallback_used,
            response_json=_json_text(run.response) or "{}",
        )
    )
    session.commit()


def get_tutorial_explanation_run(
    session: Session, run_id: str
) -> TutorialExplanationRunRecord | None:
    return session.get(TutorialExplanationRunRecord, run_id)


def _json_text(value: object | None) -> str | None:
    return json.dumps(value, ensure_ascii=False, default=str) if value is not None else None


def load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
