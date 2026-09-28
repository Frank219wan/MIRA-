"""Deterministic continuous rules for Personalization Engine v0.

The rule layer maps validated Face Profile values to parameter adjustments.
It does not perform CV inference, classification, or aesthetic judgement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping


class MakeupRuleError(ValueError):
    """Raised when a rule cannot produce a finite adjustment."""


@dataclass(frozen=True)
class LinearCalibration:
    """Clamped linear mapping between two product calibration anchors."""

    feature_low: float
    feature_high: float
    output_at_low: float
    output_at_high: float

    def __post_init__(self) -> None:
        values = (
            self.feature_low,
            self.feature_high,
            self.output_at_low,
            self.output_at_high,
        )
        if not all(math.isfinite(value) for value in values):
            raise MakeupRuleError("Calibration values must be finite.")
        if self.feature_high <= self.feature_low:
            raise MakeupRuleError(
                "Calibration feature_high must be greater than feature_low."
            )

    def map(self, feature_value: float) -> float:
        if not math.isfinite(feature_value):
            raise MakeupRuleError("Rule feature value must be finite.")
        position = (feature_value - self.feature_low) / (
            self.feature_high - self.feature_low
        )
        position = min(1.0, max(0.0, position))
        result = self.output_at_low + position * (
            self.output_at_high - self.output_at_low
        )
        if not math.isfinite(result):
            raise MakeupRuleError("Rule adjustment must be finite.")
        return result


@dataclass(frozen=True)
class RuleCalibration:
    """Provisional product calibration for the active R01-R06 rules."""

    eyeliner_direction_correction_deg: LinearCalibration = LinearCalibration(
        feature_low=0.0,
        feature_high=15.0,
        output_at_low=6.0,
        output_at_high=0.0,
    )
    eyeliner_extension_multiplier: LinearCalibration = LinearCalibration(
        feature_low=0.17,
        feature_high=0.23,
        output_at_low=1.18,
        output_at_high=0.90,
    )
    lower_lid_range_multiplier: LinearCalibration = LinearCalibration(
        feature_low=0.12,
        feature_high=0.18,
        output_at_low=0.80,
        output_at_high=1.10,
    )
    lower_lid_intensity_multiplier: LinearCalibration = LinearCalibration(
        feature_low=0.12,
        feature_high=0.18,
        output_at_low=0.85,
        output_at_high=1.05,
    )


DEFAULT_RULE_CALIBRATION = RuleCalibration()


RULE_REGISTRY: Mapping[str, Mapping[str, Any]] = {
    "R01": {
        "status": "active",
        "feature": "eye_geometry.eye_tail_angle.mean",
        "target_action": "A04",
        "parameter": "direction_angle_deg",
    },
    "R02": {
        "status": "active",
        "feature": "eye_geometry.eye_tail_angle.mean",
        "target_action": "A04",
        "parameter": "direction_angle_deg",
    },
    "R03": {
        "status": "active",
        "feature": "eye_geometry.relative_eye_length.mean",
        "target_action": "A04",
        "parameter": "extension_factor",
    },
    "R04": {
        "status": "active",
        "feature": "eye_geometry.relative_eye_length.mean",
        "target_action": "A04",
        "parameter": "extension_factor",
    },
    "R05": {
        "status": "active",
        "feature": "eye_geometry.lower_lid_space_ratio.mean",
        "target_action": "A02",
        "parameter": "range_factor",
    },
    "R06": {
        "status": "active",
        "feature": "eye_geometry.lower_lid_space_ratio.mean",
        "target_action": "A02",
        "parameter": "intensity_factor",
    },
    "R07": {
        "status": "validation_only",
        "feature": "eye_geometry.inner_corner_angle.mean_deg",
    },
    "R08": {
        "status": "validation_only",
        "feature": "eye_geometry.inner_corner_angle.mean_deg",
    },
    "R09": {
        "status": "candidate",
        "feature": "eye_geometry.brow_eye_ratio.mean",
    },
    "R10": {
        "status": "candidate",
        "feature": "eye_geometry.brow_eye_ratio.mean",
    },
}


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MakeupRuleError(f"{label} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise MakeupRuleError(f"{label} must be finite.")
    return number


def _adjustment(
    *,
    rule_ids: tuple[str, ...],
    feature_path: str,
    feature_value: float,
    parameter: str,
    operation: str,
    adjustment_value: float,
    original_value: float,
    personalized_value: float,
) -> dict[str, Any]:
    values = (feature_value, adjustment_value, original_value, personalized_value)
    if not all(math.isfinite(value) for value in values):
        raise MakeupRuleError("Adjustment output must contain finite values.")
    return {
        "rule_ids": list(rule_ids),
        "feature_path": feature_path,
        "feature_value": round(feature_value, 6),
        "parameter": parameter,
        "operation": operation,
        "adjustment_value": round(adjustment_value, 6),
        "original_value": round(original_value, 6),
        "personalized_value": round(personalized_value, 6),
    }


def apply_eyeliner_direction(
    eye_tail_angle_mean: float,
    original_direction_angle_deg: float,
    calibration: RuleCalibration = DEFAULT_RULE_CALIBRATION,
) -> dict[str, Any]:
    """R01/R02: lower eye-tail angle yields more upward correction."""

    feature = _finite_number(eye_tail_angle_mean, "eye_tail_angle.mean")
    original = _finite_number(
        original_direction_angle_deg, "direction_angle_deg"
    )
    correction = calibration.eyeliner_direction_correction_deg.map(feature)
    personalized = original + correction
    return _adjustment(
        rule_ids=("R01", "R02"),
        feature_path="eye_geometry.eye_tail_angle.mean",
        feature_value=feature,
        parameter="direction_angle_deg",
        operation="add",
        adjustment_value=correction,
        original_value=original,
        personalized_value=personalized,
    )


def apply_eyeliner_extension(
    relative_eye_length_mean: float,
    original_extension_factor: float,
    calibration: RuleCalibration = DEFAULT_RULE_CALIBRATION,
) -> dict[str, Any]:
    """R03/R04: shorter relative eye length yields a larger extension."""

    feature = _finite_number(
        relative_eye_length_mean, "relative_eye_length.mean"
    )
    original = _finite_number(original_extension_factor, "extension_factor")
    multiplier = calibration.eyeliner_extension_multiplier.map(feature)
    personalized = original * multiplier
    return _adjustment(
        rule_ids=("R03", "R04"),
        feature_path="eye_geometry.relative_eye_length.mean",
        feature_value=feature,
        parameter="extension_factor",
        operation="multiply",
        adjustment_value=multiplier,
        original_value=original,
        personalized_value=personalized,
    )


def apply_lower_lid_range(
    lower_lid_space_ratio_mean: float,
    original_range_factor: float,
    calibration: RuleCalibration = DEFAULT_RULE_CALIBRATION,
) -> dict[str, Any]:
    """R05: smaller lower-lid space yields a smaller application range."""

    feature = _finite_number(
        lower_lid_space_ratio_mean, "lower_lid_space_ratio.mean"
    )
    original = _finite_number(original_range_factor, "range_factor")
    multiplier = calibration.lower_lid_range_multiplier.map(feature)
    personalized = original * multiplier
    return _adjustment(
        rule_ids=("R05",),
        feature_path="eye_geometry.lower_lid_space_ratio.mean",
        feature_value=feature,
        parameter="range_factor",
        operation="multiply",
        adjustment_value=multiplier,
        original_value=original,
        personalized_value=personalized,
    )


def apply_lower_lid_intensity(
    lower_lid_space_ratio_mean: float,
    original_intensity_factor: float,
    calibration: RuleCalibration = DEFAULT_RULE_CALIBRATION,
) -> dict[str, Any]:
    """R06: smaller lower-lid space yields a smaller intensity."""

    feature = _finite_number(
        lower_lid_space_ratio_mean, "lower_lid_space_ratio.mean"
    )
    original = _finite_number(original_intensity_factor, "intensity_factor")
    multiplier = calibration.lower_lid_intensity_multiplier.map(feature)
    personalized = original * multiplier
    return _adjustment(
        rule_ids=("R06",),
        feature_path="eye_geometry.lower_lid_space_ratio.mean",
        feature_value=feature,
        parameter="intensity_factor",
        operation="multiply",
        adjustment_value=multiplier,
        original_value=original,
        personalized_value=personalized,
    )
