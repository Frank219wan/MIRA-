"""Versioned Week 1 data contracts shared across MIRA components."""

from .beauty_kit import BeautyKit, BeautyKitProduct, ProductCapability
from .cv_adaptation import CVAdaptation
from .cv_actions import (
    AdaptedCVAction, CVPersonalizedAction, CVStandardMakeupAction,
    DecodedActionMappingConfig, PersonalizedActionWrapper,
)
from .explanation import LLMExplanation
from .makeup import MakeupActionUnit, StandardRecipe
from .matching import (
    HardConstraintEvidence, MatchingItem, MatchingProvenance, MatchingResult,
    ScoreComponent, SubstitutionCandidate,
)
from .my_tutorial import MyTutorialResponse, MyTutorialStep
from .tutorial_explanation import ExplanationFacts, GeneratedTutorialText, ParameterChange

__all__ = [
    "AdaptedCVAction", "BeautyKit", "BeautyKitProduct", "CVAdaptation",
    "CVPersonalizedAction", "CVStandardMakeupAction", "DecodedActionMappingConfig",
    "ExplanationFacts", "GeneratedTutorialText", "LLMExplanation",
    "HardConstraintEvidence",
    "MyTutorialResponse", "MyTutorialStep", "ParameterChange",
    "MakeupActionUnit", "MatchingItem", "MatchingProvenance", "MatchingResult",
    "PersonalizedActionWrapper", "ProductCapability", "StandardRecipe",
    "ScoreComponent", "SubstitutionCandidate",
]
