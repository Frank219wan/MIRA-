"""Deterministic, explainable Product Matching v1.

Matching rules are backend-owned configuration.  This module never calls an LLM and
does not infer cosmetic properties that are absent from product metadata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.contracts.beauty_kit import BeautyKit, BeautyKitProduct, ProductCapability
from src.contracts.makeup import MakeupActionUnit, StandardRecipe
from src.contracts.matching import (
    HardConstraintEvidence,
    MatchingItem,
    MatchingProvenance,
    MatchingResult,
    ScoreComponent,
    SubstitutionCandidate,
)
from src.observability import log_event


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES_PATH = PROJECT_ROOT / "data" / "fixtures" / "product_matching_rules_v1.json"
MATCHER_VERSION = "1.0"


class ProductMatchingError(ValueError):
    """Raised when matching configuration or product metadata is invalid."""


@dataclass(frozen=True)
class CandidateEvaluation:
    product: BeautyKitProduct
    capabilities: tuple[ProductCapability, ...]
    hard_constraints: tuple[HardConstraintEvidence, ...]
    score_components: tuple[ScoreComponent, ...]
    raw_score: float
    score: float
    satisfied: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def hard_failures(self) -> tuple[str, ...]:
        return tuple(item.constraint for item in self.hard_constraints if not item.passed)

    @property
    def eligible(self) -> bool:
        return not self.hard_failures


def _normal(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


class ProductMatchingService:
    def __init__(self, rules_path: Path | str = DEFAULT_RULES_PATH) -> None:
        self.rules_path = Path(rules_path)
        try:
            self.config: dict[str, Any] = json.loads(self.rules_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProductMatchingError(f"Unable to load matching rules: {self.rules_path}") from exc
        self.rules_version = str(self.config.get("rules_version", ""))
        self.weights = self.config.get("scoring_weights", {})
        self.hard_constraint_score_cap = float(
            self.config.get("hard_constraint_score_cap", 0)
        )
        if (
            not self.rules_version
            or sum(self.weights.values()) != 100
            or not 0 <= self.hard_constraint_score_cap <= 100
        ):
            raise ProductMatchingError("Matching rules require a version and weights totaling 100")
        self.rules = {
            _normal(rule["product_requirement"]): rule
            for rule in self.config.get("requirements", [])
        }

    def match(
        self,
        recipe: StandardRecipe,
        beauty_kit: BeautyKit,
        capabilities: list[ProductCapability],
        *,
        request_id: str | None = None,
        matching_id: str | None = None,
    ) -> MatchingResult:
        capability_map = {item.capability_id: item for item in capabilities}
        items = [
            self._match_action(action, beauty_kit.products, capability_map, request_id)
            for action in recipe.action_units
        ]
        return MatchingResult(
            matching_id=matching_id or f"match-{uuid4()}",
            recipe_id=recipe.recipe_id,
            beauty_kit_id=beauty_kit.kit_id,
            items=items,
        )

    def _match_action(
        self,
        action: MakeupActionUnit,
        products: list[BeautyKitProduct],
        capability_map: dict[str, ProductCapability],
        request_id: str | None,
    ) -> MatchingItem:
        rule = self.rules.get(_normal(action.product_requirement), {})
        evaluations = [
            self._evaluate(action, product, capability_map, rule) for product in products
        ]
        for evaluation in evaluations:
            log_event(
                "product_match_candidate_evaluated",
                module="product_matching",
                request_id=request_id,
                step_index=action.step_index,
                action_requirements={
                    "product_requirement": action.product_requirement,
                    "area": action.area,
                    "goal": action.goal,
                },
                product_id=evaluation.product.product_id,
                candidate_capabilities=[item.capability_id for item in evaluation.capabilities],
                hard_constraint_failures=list(evaluation.hard_failures),
                score_components=[item.model_dump() for item in evaluation.score_components],
                pre_cap_score=evaluation.raw_score,
                match_score=evaluation.score,
            )

        eligible = sorted(
            (item for item in evaluations if item.eligible),
            key=lambda item: (-item.score, item.product.product_id),
        )
        if eligible:
            selected = eligible[0]
            decision = "strong_match" if selected.score >= 85 else "low_match"
            status = "matched" if decision == "strong_match" else "substitution_candidate"
            differences = list(selected.missing)
            difference = (
                "All configured product attributes match."
                if not differences
                else "Soft differences: " + ", ".join(differences) + "."
            )
            reason = (
                "Meets all hard constraints with strong capability coverage."
                if decision == "strong_match"
                else "Meets all hard constraints but differs on optional attributes."
            )
            impact = (
                "Expected to reproduce the required function."
                if decision == "strong_match"
                else "The required function is available, but the visible result may differ."
            )
            item = self._build_item(
                action, selected, evaluations, status=status, decision=decision,
                reason=reason, difference=difference, impact=impact,
            )
        else:
            conflict = self._best_finish_conflict(evaluations)
            if conflict is not None:
                item = self._build_item(
                    action, None, evaluations, status="unmatched",
                    decision="functional_conflict",
                    reason="Available products fail a required functional finish constraint.",
                    difference="Closest product has an incompatible finish.",
                    impact="Using it would not reproduce the required cosmetic function.",
                    functional_conflict=(
                        f"{conflict.product.product_id} fails required finish for "
                        f"{action.product_requirement}."
                    ),
                )
            else:
                item = self._build_item(
                    action, None, evaluations, status="unmatched",
                    decision="missing_capability",
                    reason="No Beauty Kit product satisfies the required capability.",
                    difference=f"Missing capability for {action.product_requirement}.",
                    impact="This recipe step cannot be reproduced with the current Beauty Kit.",
                )
        log_event(
            "product_match_decided",
            module="product_matching",
            request_id=request_id,
            step_index=action.step_index,
            decision=item.decision,
            best_product_id=item.product_id,
            match_score=item.match_score,
            hard_constraint_failures=(
                [entry.constraint for entry in item.provenance.hard_constraints if not entry.passed]
                if item.provenance else []
            ),
        )
        return item

    def _evaluate(
        self,
        action: MakeupActionUnit,
        product: BeautyKitProduct,
        capability_map: dict[str, ProductCapability],
        rule: dict[str, Any],
    ) -> CandidateEvaluation:
        capabilities = tuple(
            capability_map[capability_id]
            for capability_id in product.capability_ids
            if capability_id in capability_map
        )
        missing_metadata = [
            capability_id for capability_id in product.capability_ids
            if capability_id not in capability_map
        ]
        requirements = _unique([
            _normal(value)
            for capability in capabilities
            for value in capability.supported_product_requirements
        ])
        categories = _unique([
            _normal(product.category),
            *[_normal(capability.product_category) for capability in capabilities],
        ])
        areas = _unique([
            _normal(value) for capability in capabilities for value in capability.supported_areas
        ])
        goals = _unique([
            _normal(value) for capability in capabilities for value in capability.supported_goals
        ])
        expected_categories = [_normal(value) for value in rule.get("accepted_categories", [])]
        expected_finish = [_normal(value) for value in rule.get("required_finishes", [])]
        requirement = _normal(action.product_requirement)
        actual_finish = _normal(product.finish)

        hard_constraints = (
            HardConstraintEvidence(
                constraint="capability_metadata",
                expected=list(product.capability_ids),
                actual=[item.capability_id for item in capabilities],
                passed=bool(capabilities) and not missing_metadata,
            ),
            HardConstraintEvidence(
                constraint="product_requirement",
                expected=[requirement], actual=requirements,
                passed=requirement in requirements,
            ),
            HardConstraintEvidence(
                constraint="category",
                expected=expected_categories, actual=categories,
                passed=not expected_categories or bool(set(expected_categories) & set(categories)),
            ),
            HardConstraintEvidence(
                constraint="finish",
                expected=expected_finish,
                actual=[actual_finish] if actual_finish else [],
                passed=not expected_finish or actual_finish in expected_finish,
            ),
        )
        checks = {
            "product_requirement": requirement in requirements,
            "category": not expected_categories or bool(set(expected_categories) & set(categories)),
            "area": _normal(action.area) in areas,
            "goal": _normal(action.goal) in goals,
            "finish": not expected_finish or actual_finish in expected_finish,
            "depth": not rule.get("desired_depths") or _normal(product.depth) in {
                _normal(value) for value in rule.get("desired_depths", [])
            },
            "reflectivity": not rule.get("desired_reflectivity") or _normal(product.reflectivity) in {
                _normal(value) for value in rule.get("desired_reflectivity", [])
            },
        }
        evidence = {
            "product_requirement": f"required={requirement}; supported={requirements}",
            "category": f"expected={expected_categories}; actual={categories}",
            "area": f"required={_normal(action.area)}; supported={areas}",
            "goal": f"required={_normal(action.goal)}; supported={goals}",
            "finish": f"expected={expected_finish}; actual={actual_finish or 'unknown'}",
            "depth": f"desired={rule.get('desired_depths', [])}; actual={product.depth or 'unknown'}",
            "reflectivity": (
                f"desired={rule.get('desired_reflectivity', [])}; "
                f"actual={product.reflectivity or 'unknown'}"
            ),
        }
        components = tuple(
            ScoreComponent(
                component=name,
                points_awarded=float(points if checks[name] else 0),
                points_possible=float(points),
                evidence=evidence[name],
            )
            for name, points in self.weights.items()
        )
        satisfied = tuple(name for name, passed in checks.items() if passed)
        missing = tuple(name for name, passed in checks.items() if not passed)
        raw_score = sum(item.points_awarded for item in components)
        hard_constraint_failed = any(not item.passed for item in hard_constraints)
        final_score = (
            min(raw_score, self.hard_constraint_score_cap)
            if hard_constraint_failed else raw_score
        )
        return CandidateEvaluation(
            product=product,
            capabilities=capabilities,
            hard_constraints=hard_constraints,
            score_components=components,
            raw_score=round(raw_score, 2),
            score=round(final_score, 2),
            satisfied=satisfied,
            missing=missing,
        )

    @staticmethod
    def _best_finish_conflict(
        evaluations: list[CandidateEvaluation],
    ) -> CandidateEvaluation | None:
        conflicts = [
            item for item in evaluations
            if "finish" in item.hard_failures
            and "product_requirement" not in item.hard_failures
            and "category" not in item.hard_failures
        ]
        return min(conflicts, key=lambda item: (-item.score, item.product.product_id)) if conflicts else None

    def _build_item(
        self,
        action: MakeupActionUnit,
        selected: CandidateEvaluation | None,
        evaluations: list[CandidateEvaluation],
        *,
        status: str,
        decision: str,
        reason: str,
        difference: str,
        impact: str,
        functional_conflict: str | None = None,
    ) -> MatchingItem:
        evidence_source = selected or self._best_finish_conflict(evaluations)
        if evidence_source is None and evaluations:
            evidence_source = min(evaluations, key=lambda item: (-item.score, item.product.product_id))
        substitution_pool = (
            item for item in evaluations
            if (selected is None or item.product.product_id != selected.product.product_id)
            and "product_requirement" not in item.hard_failures
            and "category" not in item.hard_failures
        )
        substitutions = sorted(
            substitution_pool,
            key=lambda item: (-item.score, item.product.product_id),
        )[:3]
        supporting_capability = None
        if selected is not None:
            requirement = _normal(action.product_requirement)
            supporting_capability = next(
                (
                    item.capability_id for item in selected.capabilities
                    if requirement in {_normal(value) for value in item.supported_product_requirements}
                ),
                None,
            )
        missing = list(evidence_source.missing) if evidence_source else ["product_requirement"]
        if selected is None and decision == "missing_capability":
            missing = _unique([f"product_requirement:{action.product_requirement}", *missing])
        provenance = MatchingProvenance(
            matcher_version=MATCHER_VERSION,
            rules_version=self.rules_version,
            source_step_index=action.step_index,
            product_requirement=action.product_requirement,
            evaluated_product_ids=[item.product.product_id for item in evaluations],
            pre_cap_score=evidence_source.raw_score if evidence_source else 0,
            hard_constraint_score_cap=self.hard_constraint_score_cap,
            hard_constraints=list(evidence_source.hard_constraints) if evidence_source else [],
            score_components=list(evidence_source.score_components) if evidence_source else [],
        )
        return MatchingItem(
            step_index=action.step_index,
            status=status,
            product_id=selected.product.product_id if selected else None,
            capability_id=supporting_capability,
            note=reason,
            decision=decision,
            best_match=selected.product if selected else None,
            match_score=selected.score if selected else 0,
            reason=reason,
            difference=difference,
            impact=impact,
            satisfied_capabilities=list(selected.satisfied) if selected else [],
            missing_capabilities=missing,
            functional_conflict=functional_conflict,
            substitution_candidates=[
                SubstitutionCandidate(
                    product_id=item.product.product_id,
                    match_score=item.score,
                    hard_constraint_failures=list(item.hard_failures),
                    difference=(
                        "No configured differences."
                        if not item.missing else "Differs on " + ", ".join(item.missing) + "."
                    ),
                )
                for item in substitutions
            ],
            provenance=provenance,
        )
