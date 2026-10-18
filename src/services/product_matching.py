"""Deterministic matching over verified product capability metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.contracts.beauty_kit import BeautyKit, BeautyKitProduct, ProductCapability
from src.contracts.makeup import MakeupActionUnit, ProductCapabilityRequirement, StandardRecipe
from src.contracts.matching import MatchingItem


WEIGHTS = {
    "color": 0.30,
    "finish": 0.25,
    "depth": 0.15,
    "pigmentation": 0.10,
    "texture": 0.10,
    "functional": 0.10,
}

LABELS = {
    "color": "颜色",
    "finish": "妆效质地",
    "depth": "深浅",
    "pigmentation": "显色度",
    "texture": "产品质地",
    "functional": "步骤功能",
}

ORDERS = {
    "depth": {"light": 0, "medium": 1, "deep": 2},
    "pigmentation": {"sheer": 0, "medium": 1, "high": 2},
}

HARD_FINISH_CONFLICTS = {
    ("shimmer", "matte"),
    ("glitter", "matte"),
    ("matte", "glitter"),
}


@dataclass(frozen=True)
class _Evaluation:
    product: BeautyKitProduct
    capability: ProductCapability
    score: float | None
    checks: list[dict[str, object]]
    hard_constraints: list[str]
    missing: list[str]
    difference: str
    impact: str


def _overlap(required: Iterable[str], offered: Iterable[str]) -> float:
    return 1.0 if set(required) & set(offered) else 0.0


def _ordered_similarity(kind: str, required: list[str], offered: list[str]) -> float:
    order = ORDERS[kind]
    pairs = [(order[a], order[b]) for a in required for b in offered if a in order and b in order]
    if not pairs:
        return 0.0
    distance = min(abs(a - b) for a, b in pairs)
    return 1.0 if distance == 0 else 0.5 if distance == 1 else 0.0


def _functional_score(
    requirement: ProductCapabilityRequirement,
    action: MakeupActionUnit,
    capability: ProductCapability,
) -> float:
    checks = [
        requirement.product_category == capability.product_category,
        action.area in capability.supported_areas,
        action.goal in capability.supported_goals,
        bool(set(requirement.functions) & set(capability.functions)),
    ]
    return sum(checks) / len(checks)


def _unverified_item(action: MakeupActionUnit, product: BeautyKitProduct | None = None) -> MatchingItem:
    missing = [LABELS[key] for key in WEIGHTS]
    return MatchingItem(
        step_index=action.step_index,
        status="unmatched",
        product_id=product.product_id if product else None,
        verification_status="insufficient_data",
        reason="产品能力属性尚未经过验证，无法生成可信匹配分数。",
        difference="缺少结构化且已验证的颜色、妆效、深浅、显色度、质地或功能数据。",
        impact="在能力数据补齐前，系统不会将该产品标记为可替代产品。",
        missing_capabilities=missing,
        required_capabilities=action.product_capability_requirement.model_dump()
        if action.product_capability_requirement
        else {},
        note="Insufficient verified capability data; no score was calculated.",
    )


def _evaluate(
    action: MakeupActionUnit,
    product: BeautyKitProduct,
    capability: ProductCapability,
) -> _Evaluation | None:
    requirement = action.product_capability_requirement
    if requirement is None or capability.verification_status != "verified":
        return None
    attributes = [
        capability.color_families,
        capability.finishes,
        capability.depths,
        capability.pigmentations,
        capability.textures,
        capability.functions,
    ]
    if any(not values for values in attributes):
        return None

    scores = {
        "color": _overlap(requirement.color_families, capability.color_families),
        "finish": _overlap(requirement.finishes, capability.finishes),
        "depth": _ordered_similarity("depth", requirement.depths, capability.depths),
        "pigmentation": _ordered_similarity(
            "pigmentation", requirement.pigmentations, capability.pigmentations
        ),
        "texture": _overlap(requirement.textures, capability.textures),
        "functional": _functional_score(requirement, action, capability),
    }
    raw_score = 100 * sum(scores[key] * WEIGHTS[key] for key in WEIGHTS)

    hard: list[str] = []
    if requirement.product_category != capability.product_category:
        hard.append(
            f"品类冲突：需要 {requirement.product_category}，当前为 {capability.product_category}"
        )
    finish_pairs = {
        (required, offered)
        for required in requirement.finishes
        for offered in capability.finishes
    }
    conflicts = sorted(finish_pairs & HARD_FINISH_CONFLICTS)
    if conflicts and not set(requirement.finishes) & set(capability.finishes):
        required, offered = conflicts[0]
        hard.append(f"妆效冲突：需要 {required}，当前为 {offered}")

    score = min(raw_score, 35.0) if hard else raw_score
    checks = [
        {
            "key": key,
            "label": LABELS[key],
            "matched": value == 1.0,
            "score": round(value * 100, 1),
            "weight": int(WEIGHTS[key] * 100),
            "verified": True,
        }
        for key, value in scores.items()
    ]
    missing = [LABELS[key] for key, value in scores.items() if value < 1.0]
    differences = [f"{LABELS[key]}匹配 {round(value * 100):.0f}%" for key, value in scores.items() if value < 1.0]
    if hard:
        impact = "存在不可替代的品类或妆效冲突，会改变本步骤预期效果。"
    elif missing:
        impact = "可作为候选，但差异可能影响显色、过渡或最终质感。"
    else:
        impact = "已验证能力覆盖本步骤要求，预期妆效差异较小。"
    return _Evaluation(
        product=product,
        capability=capability,
        score=round(score, 1),
        checks=checks,
        hard_constraints=hard,
        missing=missing,
        difference="；".join(differences) if differences else "已验证属性与步骤要求一致。",
        impact=impact,
    )


def match_recipe(
    recipe: StandardRecipe,
    beauty_kit: BeautyKit,
    capabilities: Iterable[ProductCapability],
) -> list[MatchingItem]:
    """Match every recipe action against the user's kit without inferring missing data."""

    by_id = {capability.capability_id: capability for capability in capabilities}
    items: list[MatchingItem] = []
    for action in recipe.action_units:
        if action.product_capability_requirement is None:
            items.append(_unverified_item(action))
            continue
        evaluations: list[_Evaluation] = []
        unverified_product: BeautyKitProduct | None = None
        for product in beauty_kit.products:
            for capability_id in product.capability_ids:
                capability = by_id.get(capability_id)
                if capability is None:
                    unverified_product = unverified_product or product
                    continue
                evaluation = _evaluate(action, product, capability)
                if evaluation is None:
                    unverified_product = unverified_product or product
                else:
                    evaluations.append(evaluation)
        if not evaluations:
            items.append(_unverified_item(action, unverified_product))
            continue

        best = max(evaluations, key=lambda value: value.score or 0.0)
        if best.hard_constraints or (best.score or 0) < 50:
            status = "unmatched"
            reason = "最接近的现有产品存在关键能力冲突，不能作为可靠替代。"
        elif (best.score or 0) < 80:
            status = "substitution_candidate"
            reason = "现有产品覆盖部分能力，可作为候选但需要留意差异。"
        else:
            status = "matched"
            reason = "该产品的已验证能力与本步骤要求高度一致。"
        items.append(
            MatchingItem(
                step_index=action.step_index,
                status=status,
                product_id=best.product.product_id,
                capability_id=best.capability.capability_id,
                score=best.score,
                verification_status="verified",
                reason=reason,
                difference=best.difference,
                impact=best.impact,
                missing_capabilities=best.missing,
                hard_constraints=best.hard_constraints,
                required_capabilities=action.product_capability_requirement.model_dump(),
                capability_checks=best.checks,
                note=reason,
            )
        )
    return items
