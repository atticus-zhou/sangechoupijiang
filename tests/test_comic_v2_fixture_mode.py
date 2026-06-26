import json
import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from src.web.app import app, config_manager


FIXTURE_PATH = Path("tests/fixtures/comic_v2_sample.json")


class ComicV2FixtureModeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.workspace_id = f"ws_v2_fixture_{str(uuid.uuid4())[:8]}"
        self.previous_fixture_mode = os.environ.get("COMIC_V2_FIXTURE_MODE")
        os.environ["COMIC_V2_FIXTURE_MODE"] = "1"
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        config_manager.create_workspace(
            workspace_id=self.workspace_id,
            office_id="comic_production",
            title=self.fixture["planner_payload"]["title"],
            brief="fixture mode full-chain verification",
        )
        confirmed = {
            "title": self.fixture["planner_payload"]["title"],
            "story_draft": self.fixture["source_story"],
            "script_hash": "fixture-script-hash",
            "script_version": 1,
        }
        config_manager.set_kv(
            f"comic_cabinet_session:{self.workspace_id}",
            json.dumps({"confirmed": True, "confirmed_script": confirmed}, ensure_ascii=False),
        )

    def tearDown(self):
        if self.previous_fixture_mode is None:
            os.environ.pop("COMIC_V2_FIXTURE_MODE", None)
        else:
            os.environ["COMIC_V2_FIXTURE_MODE"] = self.previous_fixture_mode
        conn = sqlite3.connect("user_data/config.db")
        conn.execute("DELETE FROM artifacts WHERE workspace_id=?", (self.workspace_id,))
        conn.execute("DELETE FROM workspaces WHERE workspace_id=?", (self.workspace_id,))
        conn.execute("DELETE FROM config_store WHERE key=?", (f"comic_v2_state:{self.workspace_id}",))
        conn.execute("DELETE FROM config_store WHERE key=?", (f"comic_cabinet_session:{self.workspace_id}",))
        conn.execute("DELETE FROM task_events WHERE task_id=?", (f"comic_v2_{self.workspace_id}",))
        conn.execute("DELETE FROM task_runs WHERE task_id=?", (f"comic_v2_{self.workspace_id}",))
        conn.commit()
        conn.close()
        shutil.rmtree(Path("output") / "workspaces" / self.workspace_id, ignore_errors=True)

    def test_fixture_mode_runs_full_v2_chain_without_external_api_keys(self):
        visited = []

        state = self._post("/plan-confirmed")
        visited.append(state["stage"])
        self.assertEqual(state["stage"], "visual_bible_review")

        state = self._post(
            "/visual-bible/revise",
            {"revision_request": "把月灯裂纹和银白冷光写得更明确，方便后续统一画风。"},
        )
        visited.append(state["stage"])
        self.assertEqual(state["style_version"], 2)

        state = self._post("/visual-bible/approve")
        visited.append(state["stage"])
        self.assertEqual(state["stage"], "asset_planning")

        state = self._post("/assets/plan")
        visited.append(state["stage"])
        self.assertEqual(state["stage"], "asset_review")
        first_asset_count = len(state["asset_manifest"]["items"])
        self.assertGreater(first_asset_count, 0)

        state = self._post(
            "/assets/revise",
            {"revision_request": "补齐中央月塔和裂纹月灯，不要只留下人物。"},
        )
        visited.append(state["stage"])
        self.assertGreater(state["asset_manifest"]["version"], 1)
        self.assertGreaterEqual(len(state["asset_manifest"]["items"]), first_asset_count)

        state = self._post("/assets/approve")
        visited.append(state["stage"])
        self.assertEqual(state["stage"], "prompt_planning")

        state = self._post("/prompts/plan")
        visited.append(state["stage"])
        self.assertEqual(state["stage"], "image_generation")
        self.assertGreater(len(state["prompt_package"]["prompts"]), 0)
        self.assertGreater(len(state["prompt_package"]["shots"]), 0)

        state = self._post("/images/generate")
        visited.append(state["stage"])
        self.assertEqual(state["stage"], "document_generation")
        self.assertGreater(len(state["image_production"]["records"]), 0)
        self.assertTrue(state["image_production"]["production_ready"])

        state = self._post("/delivery/build")
        visited.append(state["stage"])
        self.assertEqual(state["stage"], "ready_for_handoff")
        self.assertTrue(state["delivery"]["audit"]["handoff_ready"])
        self.assertGreater(state["delivery"]["audit"]["embedded_images"], 0)
        self.assertIn("visual_bible_review", visited)
        self.assertIn("asset_review", visited)
        self.assertIn("document_generation", visited)
        self.assertIn("ready_for_handoff", visited)

        download = self.client.get(state["delivery"]["uri"])
        self.assertEqual(download.status_code, 200)
        self.assertGreater(len(download.content), 1000)

    def _post(self, suffix, payload=None):
        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2{suffix}",
            json=payload or {},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()


if __name__ == "__main__":
    unittest.main()
