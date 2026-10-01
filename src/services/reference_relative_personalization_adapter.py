"""Normalize committed Main Demo outputs without rerunning CV personalization."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from src.contracts.cv_actions import (
    AdaptedCVAction,
    CVAdjustment,
    CVPersonalizedAction,
    CVStandardMakeupAction,
    PersonalizedActionWrapper,
)


REFERENCE_RELATIVE_ADAPTER_VERSION = "1.0"
SUPPORTED_ACTION_IDS = ("A04", "A02")


class ReferenceRelativePersonalizationAdapterError(ValueError):
    """Raised when a safe fixture cannot be mapped without interpretation."""


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReferenceRelativePersonalizationAdapterError(
            f"Unable to load {label}: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise ReferenceRelativePersonalizationAdapterError(
            f"{label} must contain a JSON object: {path}"
        )
    return value


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReferenceRelativePersonalizationAdapterError(
            f"Required object is missing or ambiguous: {label}"
        )
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReferenceRelativePersonalizationAdapterError(
            f"Required text is missing or ambiguous: {label}"
        )
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceRelativePersonalizationAdapterError(
            f"Required numeric field is missing or ambiguous: {label}"
        )
    if not math.isfinite(float(value)):
        raise ReferenceRelativePersonalizationAdapterError(
            f"Required numeric field is not finite: {label}"
        )
    return float(value)


class ReferenceRelativePersonalizationAdapter:
    """Map only committed A04/A02 reference-relative results to the frozen wrapper."""

    def __init__(
        self,
        *,
        source_fixture_path: str | Path,
        reference_fixture_path: str | Path,
    ) -> None:
        self.source_fixture_path = Path(source_fixture_path)
        self.reference_fixture_path = Path(reference_fixture_path)
        self.source = _load_object(self.source_fixture_path, "personalization fixture")
        self.reference = _load_object(self.reference_fixture_path, "reference fixture")
        self._validate_fixture_identity()

    def _validate_fixture_identity(self) -> None:
        mode = _text(self.source.get("mode"), "mode")
        if mode != "reference_relative":
            raise ReferenceRelativePersonalizationAdapterError(
                f"Unsupported source mode: {mode!r}"
            )
        source_reference = _text(self.source.get("reference_id"), "reference_id")
        reference_id = _text(self.reference.get("reference_id"), "reference.reference_id")
        if source_reference != reference_id:
            raise ReferenceRelativePersonalizationAdapterError(
                "Personalization fixture reference_id does not match reference fixture."
            )
        _text(self.source.get("sample_id"), "sample_id")
        top_rules = self.source.get("triggered_rules")
        decisions = self.source.get("feature_decisions")
        if not isinstance(top_rules, list) or not isinstance(decisions, list):
            raise ReferenceRelativePersonalizationAdapterError(
                "triggered_rules and feature_decisions must be arrays."
            )
        decision_rules = [
            item.get("triggered_rule")
            for item in decisions
            if isinstance(item, Mapping) and item.get("triggered_rule") is not None
        ]
        if top_rules != decision_rules:
            raise ReferenceRelativePersonalizationAdapterError(
                "triggered_rules must exactly match committed feature decisions."
            )

    def adapt(
        self,
        action_id: Literal["A04", "A02"],
        *,
        recipe_id: str,
        step_index: int,
        face_profile_version: Literal["0.3"] = "0.3",
    ) -> PersonalizedActionWrapper:
        if action_id not in SUPPORTED_ACTION_IDS:
            raise ReferenceRelativePersonalizationAdapterError(
                f"Unsupported Main Demo action: {action_id!r}"
            )
        original, personalized, adjustments = (
            self._adapt_a04() if action_id == "A04" else self._adapt_a02()
        )
        applied_rules = self._rules_for(action_id)
        adjustment_rules = [
            rule_id for adjustment in adjustments for rule_id in adjustment.rule_ids
        ]
        if set(adjustment_rules) != set(applied_rules):
            raise ReferenceRelativePersonalizationAdapterError(
                f"Adjustment rule provenance is incomplete for {action_id}."
            )

        cv_action = CVPersonalizedAction(
            action_id=action_id,
            original_parameters=original,
            personalized_parameters=personalized,
            applied_rules=applied_rules,
            adjustments=adjustments,
        )
        provenance = AdaptedCVAction(
            mapping_version="1.0",
            mapping_id=f"main-demo-reference-relative:{action_id}",
            source_step_index=step_index,
            standard_makeup_action=CVStandardMakeupAction(
                action_id=action_id,
                parameters=original,
            ),
            source_fixture_path=self.source_fixture_path.as_posix(),
            reference_fixture_path=self.reference_fixture_path.as_posix(),
            adapter_version=REFERENCE_RELATIVE_ADAPTER_VERSION,
            face_profile_id=_text(self.source.get("sample_id"), "sample_id"),
            source_mode="reference_relative",
            source_field_paths=self._source_field_paths(action_id),
        )
        return PersonalizedActionWrapper(
            recipe_id=recipe_id,
            step_index=step_index,
            face_profile_version=face_profile_version,
            personalized_action=cv_action,
            provenance=provenance,
        )

    @staticmethod
    def _source_field_paths(action_id: str) -> dict[str, str]:
        if action_id == "A04":
            return {
                "action_id": "$.A04 (object key)",
                "original_parameters.reference_direction_deg": "reference:$.reference_action.A04.direction_relative_to_eye_axis_deg",
                "original_parameters.reference_extension_ratio": "reference:$.reference_action.A04.reference_extension_ratio",
                "original_parameters.start_position_ratio": "reference:$.reference_action.A04.start_position_ratio",
                "personalized_parameters.personalized_direction_deg": "source:$.A04.personalized_direction",
                "personalized_parameters.personalized_extension_ratio": "source:$.A04.personalized_extension_ratio",
                "personalized_parameters.start_position_ratio": "source:$.A04.start_position_ratio",
                "adjustments.personalized_direction_deg": "source:$.A04.relative_direction_adjustment + $.feature_decisions[effect=A04.direction]",
                "adjustments.personalized_extension_ratio": "source:$.A04.relative_extension_factor + $.feature_decisions[effect=A04.extension]",
            }
        return {
            "action_id": "$.A02 (object key)",
            "original_parameters.reference_range_factor": "reference:$.reference_action.A02.range_factor",
            "original_parameters.reference_intensity_factor": "reference:$.reference_action.A02.intensity_factor",
            "personalized_parameters.personalized_range_factor": "source:$.A02.personalized_range_factor",
            "personalized_parameters.personalized_intensity_factor": "source:$.A02.personalized_intensity_factor",
            "adjustments.personalized_range_factor": "source:$.A02.raw_relative_range_factor + $.feature_decisions[effect=A02.range_and_intensity]",
            "adjustments.personalized_intensity_factor": "source:$.A02.raw_relative_intensity_factor + $.feature_decisions[effect=A02.range_and_intensity]",
        }
    def _reference_action(self, action_id: str) -> Mapping[str, Any]:
        actions = _object(self.reference.get("reference_action"), "reference_action")
        return _object(actions.get(action_id), f"reference_action.{action_id}")

    def _source_action(self, action_id: str) -> Mapping[str, Any]:
        return _object(self.source.get(action_id), action_id)

    @staticmethod
    def _require_same(left: float, right: float, label: str) -> None:
        if left != right:
            raise ReferenceRelativePersonalizationAdapterError(
                f"Committed reference values disagree: {label}"
            )

    def _decision(self, effect: str) -> Mapping[str, Any]:
        decisions = self.source.get("feature_decisions")
        if not isinstance(decisions, list):
            raise ReferenceRelativePersonalizationAdapterError(
                "feature_decisions must be an array."
            )
        matches = [
            _object(item, f"feature_decisions[{index}]")
            for index, item in enumerate(decisions)
            if isinstance(item, Mapping) and item.get("effect") == effect
        ]
        if len(matches) != 1:
            raise ReferenceRelativePersonalizationAdapterError(
                f"Expected exactly one feature decision for {effect}; found {len(matches)}."
            )
        return matches[0]

    def _rules_for(self, action_id: str) -> list[str]:
        top_rules = self.source.get("triggered_rules")
        if not isinstance(top_rules, list) or any(
            not isinstance(item, str) or not item for item in top_rules
        ):
            raise ReferenceRelativePersonalizationAdapterError(
                "triggered_rules must contain rule ID strings."
            )
        effects = (
            ("A04.direction", "A04.extension")
            if action_id == "A04"
            else ("A02.range_and_intensity",)
        )
        decision_rules: list[str] = []
        for effect in effects:
            rule = self._decision(effect).get("triggered_rule")
            if rule is not None:
                decision_rules.append(_text(rule, f"{effect}.triggered_rule"))
        if len(decision_rules) != len(set(decision_rules)):
            raise ReferenceRelativePersonalizationAdapterError(
                f"Duplicate triggered rule for {action_id}."
            )
        ordered = [rule for rule in top_rules if rule in decision_rules]
        if ordered != decision_rules:
            raise ReferenceRelativePersonalizationAdapterError(
                f"Per-action rules disagree with triggered_rules for {action_id}."
            )
        return ordered

    def _adjustment(
        self,
        *,
        decision: Mapping[str, Any],
        rule_id: str | None,
        parameter: str,
        operation: Literal["add", "multiply"],
        adjustment_value: float,
        original_value: float,
        personalized_value: float,
    ) -> CVAdjustment | None:
        if rule_id is None:
            return None
        if decision.get("inside_dead_zone") is not False:
            raise ReferenceRelativePersonalizationAdapterError(
                f"Triggered rule {rule_id} is marked inside the dead zone."
            )
        if decision.get("decision") != "APPLY_RELATIVE_ADJUSTMENT":
            raise ReferenceRelativePersonalizationAdapterError(
                f"Triggered rule {rule_id} lacks an explicit apply decision."
            )
        return CVAdjustment(
            rule_ids=[rule_id],
            feature_path=_text(decision.get("feature"), f"{rule_id}.feature"),
            feature_value=_number(decision.get("user_value"), f"{rule_id}.user_value"),
            parameter=parameter,
            operation=operation,
            adjustment_value=adjustment_value,
            original_value=original_value,
            personalized_value=personalized_value,
        )

    def _adapt_a04(
        self,
    ) -> tuple[dict[str, float], dict[str, float], list[CVAdjustment]]:
        reference = self._reference_action("A04")
        source = self._source_action("A04")
        reference_direction = _number(
            reference.get("direction_relative_to_eye_axis_deg"),
            "reference_action.A04.direction_relative_to_eye_axis_deg",
        )
        reference_extension = _number(
            reference.get("reference_extension_ratio"),
            "reference_action.A04.reference_extension_ratio",
        )
        start_position = _number(
            reference.get("start_position_ratio"),
            "reference_action.A04.start_position_ratio",
        )
        self._require_same(
            reference_direction,
            _number(source.get("reference_direction"), "A04.reference_direction"),
            "A04 direction",
        )
        self._require_same(
            reference_extension,
            _number(
                source.get("reference_extension_ratio"),
                "A04.reference_extension_ratio",
            ),
            "A04 extension",
        )
        self._require_same(
            start_position,
            _number(source.get("start_position_ratio"), "A04.start_position_ratio"),
            "A04 start position",
        )
        personalized_direction = _number(
            source.get("personalized_direction"), "A04.personalized_direction"
        )
        personalized_extension = _number(
            source.get("personalized_extension_ratio"),
            "A04.personalized_extension_ratio",
        )
        direction_decision = self._decision("A04.direction")
        extension_decision = self._decision("A04.extension")
        direction_rule = direction_decision.get("triggered_rule")
        extension_rule = extension_decision.get("triggered_rule")
        adjustments = [
            item
            for item in (
                self._adjustment(
                    decision=direction_decision,
                    rule_id=direction_rule,
                    parameter="personalized_direction_deg",
                    operation="add",
                    adjustment_value=_number(
                        source.get("relative_direction_adjustment"),
                        "A04.relative_direction_adjustment",
                    ),
                    original_value=reference_direction,
                    personalized_value=personalized_direction,
                ),
                self._adjustment(
                    decision=extension_decision,
                    rule_id=extension_rule,
                    parameter="personalized_extension_ratio",
                    operation="multiply",
                    adjustment_value=_number(
                        source.get("relative_extension_factor"),
                        "A04.relative_extension_factor",
                    ),
                    original_value=reference_extension,
                    personalized_value=personalized_extension,
                ),
            )
            if item is not None
        ]
        return (
            {
                "reference_direction_deg": reference_direction,
                "reference_extension_ratio": reference_extension,
                "start_position_ratio": start_position,
            },
            {
                "personalized_direction_deg": personalized_direction,
                "personalized_extension_ratio": personalized_extension,
                "start_position_ratio": start_position,
            },
            adjustments,
        )

    def _adapt_a02(
        self,
    ) -> tuple[dict[str, float], dict[str, float], list[CVAdjustment]]:
        reference = self._reference_action("A02")
        source = self._source_action("A02")
        reference_range = _number(
            reference.get("range_factor"), "reference_action.A02.range_factor"
        )
        reference_intensity = _number(
            reference.get("intensity_factor"),
            "reference_action.A02.intensity_factor",
        )
        self._require_same(
            reference_range,
            _number(source.get("reference_range_factor"), "A02.reference_range_factor"),
            "A02 range",
        )
        self._require_same(
            reference_intensity,
            _number(
                source.get("reference_intensity_factor"),
                "A02.reference_intensity_factor",
            ),
            "A02 intensity",
        )
        personalized_range = _number(
            source.get("personalized_range_factor"),
            "A02.personalized_range_factor",
        )
        personalized_intensity = _number(
            source.get("personalized_intensity_factor"),
            "A02.personalized_intensity_factor",
        )
        decision = self._decision("A02.range_and_intensity")
        rule = decision.get("triggered_rule")
        adjustments: list[CVAdjustment] = []
        if rule is not None:
            raw_range = _number(
                source.get("raw_relative_range_factor"),
                "A02.raw_relative_range_factor",
            )
            raw_intensity = _number(
                source.get("raw_relative_intensity_factor"),
                "A02.raw_relative_intensity_factor",
            )
            self._require_same(raw_range, personalized_range, "A02 applied range")
            self._require_same(
                raw_intensity, personalized_intensity, "A02 applied intensity"
            )
            for item in (
                self._adjustment(
                    decision=decision,
                    rule_id=rule,
                    parameter="personalized_range_factor",
                    operation="multiply",
                    adjustment_value=raw_range,
                    original_value=reference_range,
                    personalized_value=personalized_range,
                ),
                self._adjustment(
                    decision=decision,
                    rule_id=rule,
                    parameter="personalized_intensity_factor",
                    operation="multiply",
                    adjustment_value=raw_intensity,
                    original_value=reference_intensity,
                    personalized_value=personalized_intensity,
                ),
            ):
                if item is not None:
                    adjustments.append(item)
        return (
            {
                "reference_range_factor": reference_range,
                "reference_intensity_factor": reference_intensity,
            },
            {
                "personalized_range_factor": personalized_range,
                "personalized_intensity_factor": personalized_intensity,
            },
            adjustments,
        )
