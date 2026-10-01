import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.contracts.matching import MatchingResult
from src.contracts.my_tutorial import MyTutorialResponse
from src.db.models import ParserRunRecord, TutorialExplanationRunRecord
from src.tools.replay_parser_run import replay_parser_run


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class WeekOneAPITests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        database_url = f"sqlite:///{Path(self.tempdir.name) / 'week1.db'}"
        self.database_url = database_url
        self.client = TestClient(create_app(database_url=database_url, debug_runs=True))
        self.recipe = fixture("standard_recipe_v1.json")
        self.beauty_kit = fixture("beauty_kit_v1.json")
        self.face_profile = fixture("face_profile_v0_3.json")

    def tearDown(self):
        self.client.close()
        self.client.app.state.engine.dispose()
        self.tempdir.cleanup()

    def test_health(self):
        response = self.client.get("/health", headers={"X-Request-ID": "trace-health-1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["request_id"], "trace-health-1")
        self.assertEqual(response.headers["X-Request-ID"], "trace-health-1")

    def test_tutorial_parse_success_persists_recipe(self):
        payload = {
            "media_path": "data/input/main_eye_tutorial.mp4",
            "media_kind": "video",
            "recipe_id": self.recipe["recipe_id"],
            "title": self.recipe["title"],
        }
        response = self.client.post(
            "/tutorials/parse", json=payload, headers={"X-Request-ID": "trace-parse-1"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["action_units"]), 5)

        stored = self.client.get(f"/recipes/{self.recipe['recipe_id']}")
        self.assertEqual(stored.status_code, 200)
        self.assertEqual(stored.json()["recipe_id"], self.recipe["recipe_id"])

        with self.client.app.state.session_factory() as session:
            run = session.query(ParserRunRecord).filter_by(request_id="trace-parse-1").one()
        self.assertEqual(run.provider_name, "mock")
        self.assertEqual(run.prompt_version, "week1-v1")
        self.assertEqual(run.input_media_path, payload["media_path"])
        self.assertIsNotNone(run.raw_output_json)
        self.assertIsNotNone(run.validated_recipe_json)
        self.assertIsNone(run.validation_error)
        self.assertNotIn("media_bytes", run.__dict__)

        replayed = replay_parser_run(run.run_id, self.database_url)
        self.assertEqual(replayed.recipe_id, self.recipe["recipe_id"])

    def test_tutorial_parse_validation_failure_has_typed_error(self):
        response = self.client.post(
            "/tutorials/parse",
            json={"media_path": "demo.mp4", "media_kind": "bad"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "invalid_tutorial_input")

    def test_recipe_not_found_has_typed_error(self):
        response = self.client.get("/recipes/missing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "recipe_not_found")

    def test_beauty_kit_response_validates(self):
        response = self.client.get("/beauty-kit")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kit_id"], self.beauty_kit["kit_id"])

    def test_matching_returns_product_matching_v1_schema(self):
        response = self.client.post(
            "/matching", json={"recipe": self.recipe, "beauty_kit": self.beauty_kit}
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        MatchingResult.model_validate(result)
        self.assertEqual(result["recipe_id"], self.recipe["recipe_id"])
        decisions = {item["step_index"]: item["decision"] for item in result["items"]}
        self.assertEqual(decisions[1], "missing_capability")
        self.assertEqual(decisions[2], "strong_match")
        self.assertEqual(decisions[3], "low_match")
        self.assertEqual(decisions[4], "functional_conflict")
        self.assertIn("score_components", result["items"][1]["provenance"])

    def test_beauty_kit_product_crud(self):
        product = {
            "product_id": "user-liner",
            "name": "User Liner",
            "product_name": "User Liner",
            "brand": "User Brand",
            "category": "eyeliner",
            "shade_name": "Black",
            "color_attributes": {"hex": "#000000"},
            "finish": "matte",
            "depth": "deep",
            "reflectivity": "low",
            "capability_ids": [],
        }
        added = self.client.post("/beauty-kit/products", json=product)
        self.assertEqual(added.status_code, 201)
        self.assertIn("user-liner", {p["product_id"] for p in added.json()["products"]})

        product["shade_name"] = "Soft Black"
        updated = self.client.put("/beauty-kit/products/user-liner", json=product)
        self.assertEqual(updated.status_code, 200)
        saved = next(p for p in updated.json()["products"] if p["product_id"] == "user-liner")
        self.assertEqual(saved["shade_name"], "Soft Black")

        removed = self.client.delete("/beauty-kit/products/user-liner")
        self.assertEqual(removed.status_code, 200)
        self.assertNotIn("user-liner", {p["product_id"] for p in removed.json()["products"]})

    def test_cv_adaptation_accepts_cv_face_profile(self):
        response = self.client.post(
            "/cv-adaptation",
            json={"recipe": self.recipe, "face_profile": self.face_profile},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["face_profile"], self.face_profile)

    def test_cv_adaptation_rejects_unsupported_face_profile_version(self):
        unsupported_profile = dict(self.face_profile)
        unsupported_profile["version"] = "99.0"
        response = self.client.post(
            "/cv-adaptation",
            json={"recipe": self.recipe, "face_profile": unsupported_profile},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_face_profile_version")

    def test_explanations_returns_placeholder_contract(self):
        matching = fixture("matching_result_v1.json")
        adaptation = {
            "schema_version": "1.0",
            "recipe_id": self.recipe["recipe_id"],
            "face_profile": self.face_profile,
        }
        response = self.client.post(
            "/explanations",
            json={
                "recipe": self.recipe,
                "matching": matching,
                "adaptation": adaptation,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("placeholder", response.json()["explanation"])

    def my_tutorial_payload(self) -> dict:
        return {
            "tutorial_id": "tutorial-api-test",
            "recipe": self.recipe,
            "beauty_kit": self.beauty_kit,
            "face_profile": self.face_profile,
            "face_profile_id": "face-profile-api-synthetic-test",
            "target_effect": "cat_eye",
        }

    def test_my_tutorial_returns_v02_and_persists_provenance(self):
        payload = self.my_tutorial_payload()
        response = self.client.post(
            "/tutorials/my-tutorial",
            json=payload,
            headers={"X-Request-ID": "trace-my-tutorial-1"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        MyTutorialResponse.model_validate(body)
        self.assertEqual(body["schema_version"], "0.2")
        self.assertEqual(len(body["steps"]), 5)
        step = body["steps"][4]
        self.assertEqual(step["personalization_status"], "personalized")
        self.assertTrue(step["personalized_parameters"])
        self.assertEqual(step["provenance"]["request_id"], "trace-my-tutorial-1")
        self.assertIsNotNone(step["provenance"]["matching_id"])
        self.assertNotIn("ar_guidance", step)
        with self.client.app.state.session_factory() as session:
            run = session.query(TutorialExplanationRunRecord).one()
        self.assertEqual(run.request_id, "trace-my-tutorial-1")
        self.assertEqual(run.face_profile_version, "0.3")
        self.assertTrue(run.fallback_used)
        self.assertIn("direction_angle_deg", run.deterministic_facts_json)

    def test_my_tutorial_invalid_face_profile_has_controlled_error(self):
        payload = self.my_tutorial_payload()
        payload["face_profile"] = fixture("face_profile_v0_1.json")
        response = self.client.post("/tutorials/my-tutorial", json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "invalid_request_payload")


if __name__ == "__main__":
    unittest.main()
