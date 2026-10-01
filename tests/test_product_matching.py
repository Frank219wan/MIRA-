import json
import unittest
from pathlib import Path

from src.contracts.beauty_kit import BeautyKit, ProductCapability
from src.contracts.makeup import StandardRecipe
from src.services.product_matching import ProductMatchingService


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ProductMatchingTests(unittest.TestCase):
    def setUp(self):
        self.recipe = StandardRecipe.model_validate(fixture("standard_recipe_v1.json"))
        self.kit = BeautyKit.model_validate(fixture("beauty_kit_v1.json"))
        catalog = fixture("product_capabilities_demo_v1.json")
        self.capabilities = [
            ProductCapability.model_validate(item) for item in catalog["capabilities"]
        ]
        self.matcher = ProductMatchingService()

    def result(self):
        return self.matcher.match(
            self.recipe, self.kit, self.capabilities, matching_id="match-test-v1"
        )

    def test_required_matching_cases(self):
        items = {item.step_index: item for item in self.result().items}
        cases = fixture("product_matching_cases_v1.json")["cases"]
        for case in cases:
            item = items[case["step_index"]]
            self.assertEqual(item.decision, case["expected_decision"], case["case"])
            self.assertEqual(item.product_id, case["expected_product_id"], case["case"])
            self.assertEqual(item.match_score, case["expected_score"], case["case"])

        strong = items[2]
        self.assertEqual(strong.decision, "strong_match")
        self.assertEqual(strong.best_match.product_id, "demo-transition-taupe")
        self.assertEqual(strong.match_score, 100)

        low = items[3]
        self.assertEqual(low.decision, "low_match")
        self.assertEqual(low.match_score, 75)
        self.assertIn("goal", low.missing_capabilities)

        missing = items[1]
        self.assertEqual(missing.decision, "missing_capability")
        self.assertIsNone(missing.best_match)
        self.assertIn("product_requirement:eye primer", missing.missing_capabilities)

        conflict = items[4]
        self.assertEqual(conflict.decision, "functional_conflict")
        self.assertIsNone(conflict.best_match)
        self.assertEqual(conflict.match_score, 0)
        self.assertIn("finish", conflict.substitution_candidates[0].hard_constraint_failures)

    def test_hard_constraint_rejects_high_visual_similarity(self):
        conflict = self.result().items[3]
        candidate = next(
            item for item in conflict.substitution_candidates
            if item.product_id == "demo-matte-champagne"
        )
        self.assertLessEqual(candidate.match_score, 20)
        self.assertIn("finish", candidate.hard_constraint_failures)
        self.assertIsNone(conflict.product_id)
        self.assertGreater(conflict.provenance.pre_cap_score, conflict.match_score)
        self.assertEqual(conflict.provenance.hard_constraint_score_cap, 20)

    def test_scoring_is_deterministic(self):
        first = self.result().model_dump()
        second = self.result().model_dump()
        self.assertEqual(first, second)

    def test_matching_does_not_mutate_inputs(self):
        recipe_before = self.recipe.model_dump(mode="json")
        kit_before = self.kit.model_dump(mode="json")
        capabilities_before = [item.model_dump(mode="json") for item in self.capabilities]
        self.result()
        self.assertEqual(self.recipe.model_dump(mode="json"), recipe_before)
        self.assertEqual(self.kit.model_dump(mode="json"), kit_before)
        self.assertEqual(
            [item.model_dump(mode="json") for item in self.capabilities],
            capabilities_before,
        )

    def test_provenance_contains_constraints_and_score_components(self):
        item = self.result().items[1]
        self.assertEqual(item.provenance.source_step_index, 2)
        self.assertEqual(item.provenance.matcher_version, "1.0")
        self.assertEqual(
            sum(component.points_possible for component in item.provenance.score_components),
            100,
        )
        self.assertTrue(all(entry.passed for entry in item.provenance.hard_constraints))


if __name__ == "__main__":
    unittest.main()
