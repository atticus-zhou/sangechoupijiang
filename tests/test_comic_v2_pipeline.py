import json
import sqlite3
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.comic_office.v2.pipeline import ComicProductionV2
from src.comic_office.v2.contracts import build_contract_bundle
from src.comic_office.v2.asset_manifest import build_asset_manifest
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

    def test_visual_bible_approval_opens_asset_planning(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id="ws_test")

        approved = ComicProductionV2.approve_visual_bible(state)

        self.assertEqual(approved.stage, "asset_planning")
        self.assertEqual(approved.current_agent, "尚书省")
        self.assertEqual(approved.contract["status"], "visual_bible_approved")
        self.assertFalse(approved.can_generate_images)

    def test_visual_bible_revision_invalidates_downstream_state(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id="ws_test")
        state = state.with_status(assets_status="approved", shots_status="approved", document_status="ready")
        revised_payload = planner_payload()
        revised_payload["visual"] = {**revised_payload["visual"], "lighting": "黎明冷雾中的银蓝顶光"}
        revised_bundle = build_contract_bundle(STORY, revised_payload, style_version=2)

        revised = ComicProductionV2.replace_visual_bible(state, revised_bundle)

        self.assertEqual(revised.stage, "visual_bible_review")
        self.assertEqual(revised.style_version, 2)
        self.assertEqual(revised.assets_status, "stale")
        self.assertEqual(revised.shots_status, "stale")
        self.assertEqual(revised.document_status, "stale")

    def test_asset_manifest_waits_for_human_review_before_prompt_planning(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id="ws_test")
        state = ComicProductionV2.approve_visual_bible(state)
        manifest = build_asset_manifest(build_contract_bundle(STORY, planner_payload()), [{
            "asset_type": "character",
            "name": "林昭",
            "evidence_quote": "林昭发现月灯燃烧记忆",
            "scene_ids": ["scene_01"],
            "story_purpose": "主角",
            "visual_locks": ["靛青长袍"],
            "allowed_changes": ["表情"],
        }])

        waiting = ComicProductionV2.attach_asset_manifest(state, manifest)

        self.assertEqual(waiting.stage, "asset_review")
        self.assertEqual(waiting.assets_status, "awaiting_user_review")
        self.assertEqual(waiting.asset_manifest["version"], 1)
        self.assertFalse(waiting.can_generate_images)

        approved = ComicProductionV2.approve_asset_manifest(waiting)
        self.assertEqual(approved.stage, "prompt_planning")
        self.assertEqual(approved.assets_status, "approved")

    def test_old_state_payload_can_be_loaded_before_asset_manifest_exists(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id="ws_test")
        payload = state.to_dict()
        payload.pop("asset_manifest", None)

        restored = ComicProductionV2.from_dict(payload)

        self.assertEqual(restored.asset_manifest, {})


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
        conn.execute("DELETE FROM config_store WHERE key=?", (f"comic_cabinet_session:{self.workspace_id}",))
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

    @patch("src.web.app.config_manager.get_model_config")
    @patch("src.web.app.plan_contract", new_callable=AsyncMock)
    def test_plan_confirmed_uses_server_owned_story_and_office_model(self, mock_plan, mock_get_model):
        bundle = build_contract_bundle(STORY, planner_payload())
        mock_plan.return_value = bundle
        confirmed = {
            "title": "借月人",
            "story_draft": STORY,
            "script_hash": "server-hash",
            "script_version": 1,
        }
        config_manager.set_kv(
            f"comic_cabinet_session:{self.workspace_id}",
            json.dumps({"confirmed": True, "confirmed_script": confirmed}, ensure_ascii=False),
        )

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/plan-confirmed",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "visual_bible_review")
        self.assertEqual(mock_plan.await_args.args[0], STORY)
        mock_get_model.assert_called_once_with("zhongshu", office_id="comic_production")

    def test_plan_confirmed_blocks_without_server_confirmed_story(self):
        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/plan-confirmed",
            json={},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("确认", response.json()["detail"])

    def test_visual_bible_approval_persists_next_stage(self):
        started = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/start",
            json={"source_story": STORY, "planner_payload": planner_payload()},
        )
        self.assertEqual(started.status_code, 200)

        approved = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/visual-bible/approve",
            json={},
        )

        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["stage"], "asset_planning")
        reloaded = self.client.get(f"/api/workspaces/{self.workspace_id}/comic/v2/status")
        self.assertEqual(reloaded.json()["contract"]["status"], "visual_bible_approved")

    @patch("src.web.app.config_manager.get_model_config")
    @patch("src.web.app.revise_visual_bible", new_callable=AsyncMock)
    def test_visual_bible_revision_persists_a_new_style_version(self, mock_revise, mock_get_model):
        started = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/start",
            json={"source_story": STORY, "planner_payload": planner_payload()},
        )
        self.assertEqual(started.status_code, 200)
        revised_payload = planner_payload()
        revised_payload["visual"] = {**revised_payload["visual"], "lighting": "黎明银蓝冷雾"}
        mock_revise.return_value = build_contract_bundle(STORY, revised_payload, style_version=2)

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/visual-bible/revise",
            json={"revision_request": "改成黎明银蓝冷雾"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["style_version"], 2)
        self.assertEqual(response.json()["stage"], "visual_bible_review")
        mock_get_model.assert_called_once_with("zhongshu", office_id="comic_production")

    @patch("src.web.app.config_manager.get_model_config")
    @patch("src.web.app.plan_asset_manifest", new_callable=AsyncMock)
    def test_asset_plan_runs_after_visual_approval_and_waits_for_human(self, mock_plan, mock_get_model):
        started = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/start",
            json={"source_story": STORY, "planner_payload": planner_payload()},
        )
        self.assertEqual(started.status_code, 200)
        approved = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/visual-bible/approve",
            json={},
        )
        self.assertEqual(approved.status_code, 200)
        manifest = build_asset_manifest(build_contract_bundle(STORY, planner_payload()), [{
            "asset_type": "character",
            "name": "林昭",
            "evidence_quote": "林昭发现月灯燃烧记忆",
            "scene_ids": ["scene_01"],
            "story_purpose": "主角",
            "visual_locks": ["靛青长袍"],
            "allowed_changes": ["表情"],
        }])
        mock_plan.return_value = manifest

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/assets/plan",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "asset_review")
        self.assertEqual(response.json()["asset_manifest"]["version"], 1)
        self.assertEqual(
            mock_get_model.call_args_list,
            [
                unittest.mock.call("zhongshu", office_id="comic_production"),
                unittest.mock.call("menxia", office_id="comic_production"),
            ],
        )

    def test_asset_approval_opens_prompt_planning(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id=self.workspace_id)
        state = ComicProductionV2.approve_visual_bible(state)
        manifest = build_asset_manifest(build_contract_bundle(STORY, planner_payload()), [{
            "asset_type": "character",
            "name": "林昭",
            "evidence_quote": "林昭发现月灯燃烧记忆",
            "scene_ids": ["scene_01"],
            "story_purpose": "主角",
            "visual_locks": ["靛青长袍"],
            "allowed_changes": ["表情"],
        }])
        state = ComicProductionV2.attach_asset_manifest(state, manifest)
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/assets/approve",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "prompt_planning")
        self.assertEqual(response.json()["assets_status"], "approved")

    @patch("src.web.app.config_manager.get_model_config")
    @patch("src.web.app.plan_asset_manifest", new_callable=AsyncMock)
    def test_asset_revision_replaces_manifest_and_returns_to_review(self, mock_plan, mock_get_model):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id=self.workspace_id)
        state = ComicProductionV2.approve_visual_bible(state)
        first = build_asset_manifest(build_contract_bundle(STORY, planner_payload()), [{
            "asset_type": "character",
            "name": "林昭",
            "evidence_quote": "林昭发现月灯燃烧记忆",
            "scene_ids": ["scene_01"],
            "story_purpose": "主角",
            "visual_locks": ["靛青长袍"],
            "allowed_changes": ["表情"],
        }])
        state = ComicProductionV2.attach_asset_manifest(state, first)
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))
        second = build_asset_manifest(
            build_contract_bundle(STORY, planner_payload()),
            [
                {
                    "asset_type": "character",
                    "name": "林昭",
                    "evidence_quote": "林昭发现月灯燃烧记忆",
                    "scene_ids": ["scene_01"],
                    "story_purpose": "主角",
                    "visual_locks": ["靛青长袍"],
                    "allowed_changes": ["表情"],
                },
                {
                    "asset_type": "scene",
                    "name": "月塔",
                    "evidence_quote": "月塔",
                    "scene_ids": ["scene_02"],
                    "story_purpose": "故事高潮空间",
                    "visual_locks": ["古代木石结构"],
                    "allowed_changes": ["光线"],
                },
            ],
            version=2,
            revision_note="补充月塔",
        )
        mock_plan.return_value = second

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/assets/revise",
            json={"revision_request": "缺少故事高潮发生的月塔"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "asset_review")
        self.assertEqual(response.json()["asset_manifest"]["version"], 2)


if __name__ == "__main__":
    unittest.main()
