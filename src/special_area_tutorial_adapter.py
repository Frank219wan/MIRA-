"""Adapt user-provided Special Area preferences into base-makeup guidance."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .special_area_profile import SCHEMA_VERSION, validate_special_area_profile


DECISION_SOURCE = "user_preference"
GUIDANCE_BY_PREFERENCE = {
    "KEEP": "在标记区域减少高遮盖底妆叠加，只在边缘轻轻衔接周围底妆，保留该区域原有可见度。",
    "BLEND": "在标记区域只做轻度均匀和边缘过渡，不追求完全遮盖，重点降低它与周围肤色的视觉反差。",
    "COVER": "先在标记区域进行局部遮盖，少量多次叠加产品，并重点处理边缘过渡，避免整块区域底妆过厚。",
    "HIGHLIGHT": "保留标记区域的可见度，避免使用高遮盖产品覆盖，并让周围底妆与整体妆容自然衔接。",
}


def adapt_special_area_tutorial(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Create one guidance block per area, based only on user preference."""

    validated = validate_special_area_profile(profile)
    guidance_blocks = []
    for area in validated["areas"]:
        preference = area["preference"]
        guidance_blocks.append(
            {
                "area_id": area["area_id"],
                "location": area["location"],
                "user_label": area["user_label"],
                "preference": preference,
                "decision_source": DECISION_SOURCE,
                "guidance_zh": GUIDANCE_BY_PREFERENCE[preference],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "image_sample_id": validated["image_sample_id"],
        "tutorial_type": "complexion_base_makeup",
        "guidance_blocks": guidance_blocks,
    }
