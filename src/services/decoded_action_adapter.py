"""Explicit decoded-action to CV-action mapping; no heuristic inference."""

from __future__ import annotations

from src.contracts.cv_actions import AdaptedCVAction, DecodedActionMappingConfig
from src.contracts.makeup import MakeupActionUnit


class DecodedActionMappingError(ValueError):
    pass


def adapt_decoded_action(
    action: MakeupActionUnit,
    config: DecodedActionMappingConfig,
) -> AdaptedCVAction:
    """Apply one exact approved mapping and preserve its source step."""

    matches = [
        mapping
        for mapping in config.mappings
        if mapping.source.area == action.area
        and mapping.source.goal == action.goal
        and mapping.source.product_requirement == action.product_requirement
    ]
    if len(matches) != 1:
        raise DecodedActionMappingError(
            f"Expected exactly one mapping for source step {action.step_index}; "
            f"found {len(matches)}."
        )
    mapping = matches[0]
    if mapping.status != "approved" or mapping.parameters is None:
        required = ", ".join(mapping.required_product_inputs) or "approved numeric parameters"
        raise DecodedActionMappingError(
            f"Mapping {mapping.mapping_id} requires product input: {required}."
        )
    return AdaptedCVAction(
        mapping_version=config.mapping_version,
        mapping_id=mapping.mapping_id,
        source_step_index=action.step_index,
        standard_makeup_action={
            "action_id": mapping.action_id,
            "parameters": mapping.parameters,
        },
    )
