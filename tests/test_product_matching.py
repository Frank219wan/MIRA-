from __future__ import annotations

import unittest

from src.contracts.beauty_kit import BeautyKit, BeautyKitProduct, ProductCapability
from src.contracts.makeup import MakeupActionUnit, ProductCapabilityRequirement, StandardRecipe
from src.services.product_matching import match_recipe


def requirement(**overrides) -> ProductCapabilityRequirement:
    values = {
        "product_category": "eye shadow palette",
        "color_families": ["neutral"],
        "finishes": ["matte"],
        "depths": ["medium"],
        "pigmentations": ["medium"],
        "textures": ["powder"],
        "functions": ["blend"],
    }
    values.update(overrides)
    return ProductCapabilityRequirement(**values)


def action(req: ProductCapabilityRequirement | None = None) -> MakeupActionUnit:
    return MakeupActionUnit(
        step_index=1,
        area="crease",
        goal="add depth",
        product_requirement="matte transition shadow",
        product_capability_requirement=req,
        tool="brush",
        motion="blend",
        intensity="medium",
        target_result="soft transition",
    )


def capability(**overrides) -> ProductCapability:
    values = {
        "capability_id": "cap-shadow",
        "product_category": "eye shadow palette",
        "supported_areas": ["crease"],
        "supported_goals": ["add depth"],
        "color_families": ["neutral"],
        "finishes": ["matte"],
        "depths": ["medium"],
        "pigmentations": ["medium"],
        "textures": ["powder"],
        "functions": ["blend"],
        "verification_status": "verified",
    }
    values.update(overrides)
    return ProductCapability(**values)


def run_match(unit: MakeupActionUnit, cap: ProductCapability):
    recipe = StandardRecipe(
        recipe_id="recipe-test",
        title="test",
        source_media_path="test.mp4",
        action_units=[unit],
    )
    kit = BeautyKit(
        kit_id="kit-test",
        name="test kit",
        products=[BeautyKitProduct(product_id="product-test", name="Test", capability_ids=[cap.capability_id])],
    )
    return match_recipe(recipe, kit, [cap])[0]


class ProductMatchingTests(unittest.TestCase):
    def test_verified_exact_match_scores_100(self):
        result = run_match(action(requirement()), capability())
        self.assertEqual(result.status, "matched")
        self.assertEqual(result.score, 100.0)
        self.assertEqual(result.verification_status, "verified")
        self.assertFalse(result.missing_capabilities)

    def test_shimmer_requirement_rejects_verified_matte_product(self):
        result = run_match(
            action(requirement(finishes=["shimmer"])),
            capability(finishes=["matte"]),
        )
        self.assertEqual(result.status, "unmatched")
        self.assertLessEqual(result.score, 35.0)
        self.assertTrue(any("妆效冲突" in item for item in result.hard_constraints))
        self.assertIn("妆效质地", result.missing_capabilities)

    def test_unverified_capability_has_no_score(self):
        result = run_match(action(requirement()), capability(verification_status="unverified"))
        self.assertEqual(result.status, "unmatched")
        self.assertIsNone(result.score)
        self.assertEqual(result.verification_status, "insufficient_data")

    def test_missing_structured_requirement_has_no_score(self):
        result = run_match(action(), capability())
        self.assertIsNone(result.score)
        self.assertEqual(result.verification_status, "insufficient_data")

    def test_weighted_score_uses_declared_weights(self):
        result = run_match(
            action(requirement(depths=["deep"])),
            capability(depths=["medium"]),
        )
        # Adjacent depth receives half of the 15% depth component.
        self.assertEqual(result.score, 92.5)
        depth = next(check for check in result.capability_checks if check["key"] == "depth")
        self.assertEqual(depth["weight"], 15)
        self.assertEqual(depth["score"], 50.0)


if __name__ == "__main__":
    unittest.main()
