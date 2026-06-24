import sqlite3
import unittest
import uuid

from fastapi.testclient import TestClient

from src.comic_office.v2.pipeline import ComicProductionV2
from src.web.app import app, config_manager


STORY = "林昭发现月灯燃烧记忆。她进入月塔，最终熄灭月塔，让全城重新想起亲人。"


def planner_payload():
    return {
        "title": "借月人",
        "genre": "古风幻想",
        "theme": "记忆与光明的代价",
        "protagonist_goal": "熄灭月塔",
        "main_conflict": "月塔依靠记忆维持光明",
        "causal_chain": ["发现真相", "进入月塔", "熄灭月塔"],
        "ending": "林昭最终熄灭月塔",
        "episodes": [{"episode": 1, "summary": "发现真相并作出选择", "evidence_quote": "林昭发现月灯燃烧记忆"}],
        "visual": {
            "medium": "电影级国风厚涂动画",
            "era": "架空古代",
            "aspect_ratio": "9:16",
            "palette": ["靛青", "银白", "暗朱红"],
            "lighting": "冷月光与暖灯火对照",
            "camera_language": "克制稳定",
            "character_rules": ["脸型与服装主色固定"],
            "costume_rules": ["古代窄袖长袍"],
            "prop_rules": ["裂纹位置固定"],
            "architecture_rules": ["木石结构"],
            "visual_motifs": ["裂纹月灯"],
            "prohibited_elements": ["现代车辆", "可读文字"],
        },
    }


class ComicV2PipelineTests(unittest.TestCase):
    def test_v2_pipeline_starts_at_visual_bible_review(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id="ws_test")

        self.assertEqual(state.stage, "visual_bible_review")
        self.assertEqual(state.current_agent, "中书省")
        self.assertEqual(state.current_object, "故事合同与视觉母版")
        self.assertFalse(state.can_generate_images)
        self.assertIn("确认视觉母版", state.next_action)

    def test_story_change_invalidates_assets_and_shots(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id="ws_test")
        state = state.with_status(assets_status="approved", shots_status="approved", document_status="ready")

        changed = state.replace_story("林昭拒绝熄灭月塔，选择公开月税真相。")

        self.assertEqual(changed.stage, "story_confirmed")
        self.assertEqual(changed.assets_status, "stale")
        self.assertEqual(changed.shots_status, "stale")
        self.assertEqual(changed.document_status, "stale")
        self.assertFalse(changed.can_generate_images)
        self.assertNotEqual(changed.story_id, state.story_id)

    def test_state_round_trip_preserves_current_work(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id="ws_test")

        restored = ComicProductionV2.from_dict(state.to_dict())

        self.assertEqual(restored, state)
        self.assertEqual(restored.pipeline_version, 2)


class ComicV2PipelineApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.workspace_id = f"ws_v2_{str(uuid.uuid4())[:8]}"
        config_manager.create_workspace(
            workspace_id=self.workspace_id,
            office_id="comic_production",
            title="V2 pipeline test",
            brief="Test V2 status persistence",
        )

    def tearDown(self):
        conn = sqlite3.connect("user_data/config.db")
        conn.execute("DELETE FROM artifacts WHERE workspace_id=?", (self.workspace_id,))
        conn.execute("DELETE FROM workspaces WHERE workspace_id=?", (self.workspace_id,))
        conn.execute("DELETE FROM config_store WHERE key=?", (f"comic_v2_state:{self.workspace_id}",))
        conn.execute("DELETE FROM task_events WHERE task_id=?", (f"comic_v2_{self.workspace_id}",))
        conn.commit()
        conn.close()

    def test_api_starts_and_exposes_current_object_and_next_action(self):
        started = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/start",
            json={"source_story": STORY, "planner_payload": planner_payload()},
        )

        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["stage"], "visual_bible_review")

        response = self.client.get(f"/api/workspaces/{self.workspace_id}/comic/v2/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["pipeline_version"], 2)
        self.assertEqual(body["current_agent"], "中书省")
        self.assertEqual(body["current_object"], "故事合同与视觉母版")
        self.assertIn("next_action", body)
        self.assertIn("blocking_reason", body)

    def test_api_returns_honest_not_started_state(self):
        response = self.client.get(f"/api/workspaces/{self.workspace_id}/comic/v2/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "not_started")
        self.assertEqual(body["current_object"], "已确认故事")
        self.assertFalse(body["can_generate_images"])

    def test_non_production_office_cannot_start_v2(self):
        research_id = f"ws_research_{str(uuid.uuid4())[:8]}"
        config_manager.create_workspace(research_id, "research", "Research", "")
        try:
            response = self.client.post(
                f"/api/workspaces/{research_id}/comic/v2/start",
                json={"source_story": STORY, "planner_payload": planner_payload()},
            )
            self.assertEqual(response.status_code, 404)
        finally:
            conn = sqlite3.connect("user_data/config.db")
            conn.execute("DELETE FROM workspaces WHERE workspace_id=?", (research_id,))
            conn.commit()
            conn.close()


if __name__ == "__main__":
    unittest.main()
