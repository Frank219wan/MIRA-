"""My Tutorial v0.2 orchestration schema; this module contains no generation."""

from typing import Literal

from pydantic import Field

from .common import ContractModel
from .cv_actions import AdaptedCVAction, PersonalizedActionWrapper
from .makeup import MakeupActionUnit
from .matching import MatchingItem


class FaceProfileReference(ContractModel):
    profile_id: str = Field(min_length=1)
    version: Literal["0.3"] = "0.3"


class TutorialInstructionFields(ContractModel):
    where: str | None = None
    how: str | None = None
    why: str | None = None
    stop_when: str | None = None


class MyTutorialStep(ContractModel):
    step_index: int = Field(ge=1)
    standard_action: MakeupActionUnit
    cv_standard_action: AdaptedCVAction | None = None
    match_result: MatchingItem | None = None
    face_profile: FaceProfileReference | None = None
    cv_personalized_action: PersonalizedActionWrapper | None = None
    instructions: TutorialInstructionFields = Field(default_factory=TutorialInstructionFields)
    provenance: dict[str, str] = Field(default_factory=dict)
    fallback_status: Literal["none", "standard_action", "mapping_pending", "profile_unavailable"]
    ar_guidance_status: Literal["pending_cv_contract"] = "pending_cv_contract"


class MyTutorialResponse(ContractModel):
    schema_version: Literal["0.2"] = "0.2"
    tutorial_id: str = Field(min_length=1)
    recipe_id: str = Field(min_length=1)
    steps: list[MyTutorialStep]
