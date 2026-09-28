import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.db.models import ParserRunRecord
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
        self.face_profile = fixture("face_profile_v0_1.json")

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

    def test_matching_returns_structural_placeholder(self):
        response = self.client.post(
            "/matching", json={"recipe": self.recipe, "beauty_kit": self.beauty_kit}
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["recipe_id"], self.recipe["recipe_id"])
        self.assertTrue(all(item["status"] == "unmatched" for item in result["items"]))

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


if __name__ == "__main__":
    unittest.main()
