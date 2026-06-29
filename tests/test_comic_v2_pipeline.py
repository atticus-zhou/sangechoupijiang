import json
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.comic_office.v2.pipeline import ComicProductionV2
from src.comic_office.v2.contracts import build_contract_bundle
from src.comic_office.v2.asset_manifest import build_asset_manifest
from src.comic_office.v2.delivery import DeliveryValidationError
from src.comic_office.v2.production import ImageProductionResult, ProductionError, PromptPackage
from src.comic_office.v2.prompt_director import PromptPlan, ShotCard
from src.comic_office.v2.word_canvas import CanvasBuildResult, DocumentAudit
from src.llm.providers import ModelConfig
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

    def test_prompt_and_image_packages_advance_to_document_generation(self):
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
        state = ComicProductionV2.attach_asset_manifest(state, manifest)
        state = ComicProductionV2.approve_asset_manifest(state)
        prompt = PromptPlan(
            object_id=manifest.items[0].asset_id,
            image_kind="three_view",
            purpose="identity_reference",
            generator_prompt="林昭三视图，靛青长袍，纯白干净背景",
            negative_prompt=("禁止文字",),
            style_id=state.style_id,
        )
        package = PromptPackage(
            package_id="prompts_test",
            story_id=state.story_id,
            story_version=state.story_version,
            style_id=state.style_id,
            style_version=state.style_version,
            manifest_id=manifest.manifest_id,
            manifest_version=manifest.version,
            prompts=(prompt,),
            shots=(),
        )

        generating = ComicProductionV2.attach_prompt_package(state, package)

        self.assertEqual(generating.stage, "image_generation")
        self.assertTrue(generating.can_generate_images)
        self.assertEqual(generating.prompt_package["package_id"], "prompts_test")

        result = ImageProductionResult(
            status="ready_for_delivery",
            production_ready=True,
            records=(),
            failures=(),
        )
        delivering = ComicProductionV2.attach_image_production(generating, result)
        self.assertEqual(delivering.stage, "document_generation")
        self.assertFalse(delivering.can_generate_images)

    def test_failed_visual_review_requires_reason_before_human_override(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id="ws_test")
        state = state.with_status(stage="visual_review", image_production={"production_ready": False})

        with self.assertRaises(ValueError):
            ComicProductionV2.override_visual_review(state, "")

        overridden = ComicProductionV2.override_visual_review(state, "人物风格偏差可接受，后续平台继续修正")
        self.assertEqual(overridden.stage, "document_generation")
        self.assertEqual(
            overridden.image_production["human_override"]["reason"],
            "人物风格偏差可接受，后续平台继续修正",
        )

    def test_document_audit_marks_pipeline_ready_for_handoff(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id="ws_test")
        state = state.with_status(stage="document_generation")
        audit = DocumentAudit(
            embedded_images=2,
            asset_count=1,
            shot_count=1,
            missing_image_asset_ids=(),
            structural_errors=(),
            max_table_columns=2,
            handoff_ready=True,
        )

        ready = ComicProductionV2.attach_delivery(state, "C:/delivery/canvas.docx", audit)

        self.assertEqual(ready.stage, "ready_for_handoff")
        self.assertEqual(ready.document_status, "ready")
        self.assertEqual(ready.delivery["path"], "C:/delivery/canvas.docx")

    def test_old_state_payload_can_be_loaded_before_prompt_and_image_fields_exist(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id="ws_test")
        payload = state.to_dict()
        payload.pop("prompt_package", None)
        payload.pop("image_production", None)

        restored = ComicProductionV2.from_dict(payload)

        self.assertEqual(restored.prompt_package, {})
        self.assertEqual(restored.image_production, {})


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

    def test_v2_workspace_and_state_errors_are_actionable(self):
        missing = self.client.get("/api/workspaces/ws_missing_v2_error/comic/v2/status")
        self.assertEqual(missing.status_code, 404)
        missing_detail = missing.json()["detail"]
        self.assertEqual(missing_detail["office_id"], "comic_production")
        self.assertEqual(missing_detail["stage"], "workspace_lookup")
        self.assertTrue(missing_detail["reason"])
        self.assertTrue(missing_detail["impact"])
        self.assertTrue(missing_detail["next_action"])

        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", "{broken-json")
        damaged = self.client.get(f"/api/workspaces/{self.workspace_id}/comic/v2/status")
        self.assertEqual(damaged.status_code, 500)
        damaged_detail = damaged.json()["detail"]
        self.assertEqual(damaged_detail["office_id"], "comic_production")
        self.assertEqual(damaged_detail["stage"], "state_load")
        self.assertTrue(damaged_detail["reason"])
        self.assertTrue(damaged_detail["impact"])
        self.assertTrue(damaged_detail["next_action"])

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

    def test_visual_bible_approval_wrong_stage_error_is_structured(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id=self.workspace_id)
        state = ComicProductionV2.approve_visual_bible(state)
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/visual-bible/approve",
            json={},
        )

        self.assertEqual(response.status_code, 409)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "中书省")
        self.assertIn("当前阶段", detail["reason"])
        self.assertIn("覆盖", detail["impact"])
        self.assertIn("当前阶段", detail["next_action"])

    def test_visual_bible_revision_without_state_error_is_structured(self):
        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/visual-bible/revise",
            json={"revision_request": "画风更冷"},
        )

        self.assertEqual(response.status_code, 409)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "中书省")
        self.assertIn("视觉母版", detail["reason"])
        self.assertIn("无法修改", detail["impact"])
        self.assertIn("确认故事", detail["next_action"])

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
        detail = response.json()["detail"]
        self.assertEqual(detail["office_id"], "comic_production")
        self.assertIn("完整故事", detail["reason"])
        self.assertIn("确认故事", detail["next_action"])

    def test_plan_confirmed_missing_story_error_is_structured(self):
        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/plan-confirmed",
            json={},
        )

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "内阁 / 中书省")
        self.assertIn("完整故事", detail["reason"])
        self.assertIn("视觉母版", detail["impact"])
        self.assertIn("确认故事", detail["next_action"])

    def test_v2_start_contract_validation_error_is_structured(self):
        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/start",
            json={"source_story": "", "planner_payload": {}},
        )

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "中书省")
        self.assertIn("正式制片合同", detail["reason"])
        self.assertIn("生产链", detail["impact"])
        self.assertIn("故事", detail["next_action"])

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

        status = self.client.get(f"/api/workspaces/{self.workspace_id}/comic/v2/status")
        review = status.json()["asset_review"]
        self.assertEqual(review["counts"], {"characters": 1, "props": 0, "scenes": 0})
        self.assertEqual(review["groups"]["characters"][0]["name"], "林昭")
        self.assertEqual(review["groups"]["characters"][0]["source_evidence"], "林昭发现月灯燃烧记忆")
        self.assertNotIn("prompt", json.dumps(review, ensure_ascii=False).lower())
        flow = status.json()["department_flow"]
        by_id = {item["department_id"]: item for item in flow}
        self.assertEqual(by_id["menxia"]["status"], "current")
        self.assertEqual(by_id["menxia"]["human_checkpoint"], "等待用户确认资产拆解")
        self.assertIn("版本", by_id["ribu"]["responsibility"])
        self.assertEqual(by_id["gongbu"]["status"], "waiting")
        self.assertIn("基础资产图", by_id["gongbu"]["responsibility"])

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

    def test_v2_wrong_stage_error_names_department_impact_and_next_action(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id=self.workspace_id)
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/assets/plan",
            json={},
        )

        self.assertEqual(response.status_code, 409)
        detail = response.json()["detail"]
        self.assertEqual(detail["office_id"], "comic_production")
        self.assertEqual(detail["department"], "尚书省")
        self.assertIn("当前阶段不能生成资产拆解包", detail["reason"])
        self.assertIn("资产拆解", detail["impact"])
        self.assertIn("确认视觉母版", detail["next_action"])

    def test_v2_prompt_image_and_delivery_stage_errors_are_actionable(self):
        state, manifest = self._state_with_approved_assets()
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        image_blocked = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/images/generate",
            json={},
        )
        self.assertEqual(image_blocked.status_code, 409)
        image_detail = image_blocked.json()["detail"]
        self.assertEqual(image_detail["department"], "工部")
        self.assertIn("当前阶段不能生成资产图片", image_detail["reason"])
        self.assertIn("提示词", image_detail["next_action"])

        delivery_blocked = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/delivery/build",
            json={},
        )
        self.assertEqual(delivery_blocked.status_code, 409)
        delivery_detail = delivery_blocked.json()["detail"]
        self.assertEqual(delivery_detail["department"], "礼部")
        self.assertIn("图片生产与质检尚未完成", delivery_detail["reason"])
        self.assertIn("提示词", delivery_detail["next_action"])

        unapproved = ComicProductionV2.approve_visual_bible(
            ComicProductionV2.start(STORY, planner_payload(), workspace_id=self.workspace_id)
        )
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(unapproved.to_dict(), ensure_ascii=False))
        prompt_blocked = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/prompts/plan",
            json={},
        )
        self.assertEqual(prompt_blocked.status_code, 409)
        prompt_detail = prompt_blocked.json()["detail"]
        self.assertEqual(prompt_detail["department"], "工部")
        self.assertIn("资产拆解包尚未确认", prompt_detail["reason"])
        self.assertIn("人物、道具和场景", prompt_detail["next_action"])

    def test_v2_human_review_action_errors_are_actionable(self):
        visual = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/visual-bible/approve",
            json={},
        )
        self.assertEqual(visual.status_code, 409)
        visual_detail = visual.json()["detail"]
        self.assertEqual(visual_detail["department"], "中书省")
        self.assertIn("请先生成视觉母版", visual_detail["reason"])
        self.assertIn("故事", visual_detail["next_action"])

        assets = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/assets/approve",
            json={},
        )
        self.assertEqual(assets.status_code, 409)
        assets_detail = assets.json()["detail"]
        self.assertEqual(assets_detail["department"], "门下省")
        self.assertIn("请先生成资产拆解包", assets_detail["reason"])
        self.assertIn("资产拆解", assets_detail["next_action"])

        visual_review = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/images/override",
            json={"reason": "人工确认可接受"},
        )
        self.assertEqual(visual_review.status_code, 409)
        review_detail = visual_review.json()["detail"]
        self.assertEqual(review_detail["department"], "刑部")
        self.assertIn("当前没有待人工处理的视觉质检", review_detail["reason"])
        self.assertIn("生成并质检基础资产图", review_detail["next_action"])

    def test_asset_revision_wrong_state_errors_are_structured(self):
        empty = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/assets/revise",
            json={"revision_request": "补道具"},
        )
        self.assertEqual(empty.status_code, 409)
        empty_detail = empty.json()["detail"]
        self.assertEqual(empty_detail["department"], "门下省")
        self.assertIn("资产拆解包", empty_detail["reason"])
        self.assertIn("无法退回", empty_detail["impact"])

        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id=self.workspace_id)
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))
        wrong_stage = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/assets/revise",
            json={"revision_request": "补道具"},
        )
        self.assertEqual(wrong_stage.status_code, 409)
        wrong_detail = wrong_stage.json()["detail"]
        self.assertEqual(wrong_detail["department"], "门下省")
        self.assertIn("当前没有可退回", wrong_detail["reason"])
        self.assertIn("资产审核", wrong_detail["next_action"])

    def test_asset_approval_wrong_stage_error_is_structured(self):
        state = ComicProductionV2.start(STORY, planner_payload(), workspace_id=self.workspace_id)
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/assets/approve",
            json={},
        )

        self.assertEqual(response.status_code, 409)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "门下省")
        self.assertIn("当前阶段", detail["reason"])
        self.assertIn("资产拆解", detail["impact"])
        self.assertIn("资产审核", detail["next_action"])

    def test_visual_review_override_error_is_structured(self):
        state, manifest = self._state_with_approved_assets()
        state = ComicProductionV2.attach_prompt_package(state, self._prompt_package(state, manifest))
        state = state.with_status(
            stage="visual_review",
            image_production=ImageProductionResult(
                status="ready_for_delivery",
                production_ready=True,
                records=(),
                failures=(),
            ).to_dict(),
        )
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/images/override",
            json={"reason": ""},
        )

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "刑部")
        self.assertIn("人工放行", detail["reason"])
        self.assertIn("风险", detail["impact"])
        self.assertIn("理由", detail["next_action"])

    @patch("src.web.app.direct_asset_prompts", new_callable=AsyncMock)
    @patch("src.web.app.config_manager.get_model_config")
    def test_v2_prompt_planning_runtime_error_names_gongbu(self, mock_get_model, mock_assets):
        state, manifest = self._state_with_approved_assets()
        mock_assets.side_effect = ProductionError("模型返回空提示词")
        mock_get_model.return_value = ModelConfig(provider="openai", model="fake", api_key="test")
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/prompts/plan",
            json={},
        )

        self.assertEqual(response.status_code, 502)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "工部 / 兵部")
        self.assertIn("提示词规划失败", detail["reason"])
        self.assertIn("图片", detail["impact"])
        self.assertIn("模型配置", detail["next_action"])

    @patch("src.web.app.produce_asset_images", new_callable=AsyncMock)
    @patch("src.web.app.config_manager.get_model_config")
    def test_v2_image_runtime_error_names_gongbu_and_xingbu(self, mock_get_model, mock_produce):
        state, manifest = self._state_with_approved_assets()
        state = ComicProductionV2.attach_prompt_package(state, self._prompt_package(state, manifest))
        mock_produce.side_effect = ProductionError("生图 API 超时")
        mock_get_model.return_value = ModelConfig(provider="doubao", model="doubao-seedream-5", api_key="test")
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/images/generate",
            json={},
        )

        self.assertEqual(response.status_code, 502)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "工部 / 刑部")
        self.assertIn("资产图片生产失败", detail["reason"])
        self.assertIn("Word", detail["impact"])
        self.assertIn("生图模型", detail["next_action"])

    @patch("src.web.app.build_delivery_from_v2")
    def test_v2_delivery_runtime_error_names_libu(self, mock_build):
        state, manifest = self._state_with_approved_assets()
        state = ComicProductionV2.attach_prompt_package(state, self._prompt_package(state, manifest))
        state = state.with_status(
            stage="document_generation",
            can_generate_images=False,
            image_production=ImageProductionResult(
                status="ready_for_delivery",
                production_ready=True,
                records=(),
                failures=(),
            ).to_dict(),
        )
        mock_build.side_effect = DeliveryValidationError("缺少镜头资产引用")
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/delivery/build",
            json={},
        )

        self.assertEqual(response.status_code, 502)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "礼部 / 刑部")
        self.assertIn("Word 制片画布生成失败", detail["reason"])
        self.assertIn("交付", detail["impact"])
        self.assertIn("结构审计", detail["next_action"])

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
        from src.comic_office.v2.asset_manifest import replace_asset_manifest

        second = replace_asset_manifest(
            first,
            "补充月塔",
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
        )
        mock_plan.return_value = second

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/assets/revise",
            json={"revision_request": "缺少故事高潮发生的月塔"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "asset_review")
        self.assertEqual(response.json()["asset_manifest"]["version"], 2)
        self.assertEqual(response.json()["asset_review"]["revision_note"], "补充月塔")
        self.assertEqual(response.json()["asset_review"]["counts"]["scenes"], 1)
        self.assertEqual(response.json()["asset_review"]["previous_manifest_hash"], first.manifest_hash)
        self.assertEqual(response.json()["asset_review"]["revision_summary"]["added"], [{"asset_type": "scene", "name": "月塔"}])

    @patch("src.web.app.config_manager.get_model_config")
    @patch("src.web.app.plan_asset_manifest", new_callable=AsyncMock)
    def test_asset_revision_missing_prop_request_requires_new_prop(self, mock_plan, mock_get_model):
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
        mock_get_model.return_value = ModelConfig(provider="openai", model="fake", api_key="test")
        from src.comic_office.v2.asset_planner import AssetPlanningError
        mock_plan.side_effect = AssetPlanningError("用户退回意见要求补充道具，但新版资产清单没有新增道具")

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/assets/revise",
            json={"revision_request": "缺少道具，请补充道具"},
        )

        self.assertEqual(response.status_code, 502)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "中书省 / 门下省")
        self.assertIn("补充道具", detail["reason"])
        self.assertIn("人物、道具、场景", detail["impact"])
        self.assertIn("退回意见", detail["next_action"])

    @patch("src.web.app.direct_shot_cards", new_callable=AsyncMock)
    @patch("src.web.app.direct_asset_prompts", new_callable=AsyncMock)
    @patch("src.web.app.config_manager.get_model_config")
    def test_prompt_plan_persists_package_and_opens_image_generation(self, mock_get_model, mock_assets, mock_shots):
        state, manifest = self._state_with_approved_assets()
        package = self._prompt_package(state, manifest)
        mock_assets.return_value = package
        mock_shots.return_value = package
        mock_get_model.return_value = ModelConfig(provider="openai", model="fake", api_key="test")
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/prompts/plan",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "image_generation")
        self.assertTrue(response.json()["can_generate_images"])
        self.assertEqual(response.json()["prompt_package"]["package_id"], package.package_id)

    @patch("src.web.app.produce_asset_images", new_callable=AsyncMock)
    @patch("src.web.app.config_manager.get_model_config")
    def test_image_generation_ready_result_opens_document_generation(self, mock_get_model, mock_produce):
        state, manifest = self._state_with_approved_assets()
        state = ComicProductionV2.attach_prompt_package(state, self._prompt_package(state, manifest))
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))
        mock_get_model.return_value = ModelConfig(provider="doubao", model="doubao-seedream-5", api_key="test")
        mock_produce.return_value = ImageProductionResult(
            status="ready_for_delivery",
            production_ready=True,
            records=(),
            failures=(),
        )

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/images/generate",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "document_generation")
        self.assertFalse(response.json()["can_generate_images"])

    @patch("src.web.app.produce_asset_images", new_callable=AsyncMock)
    @patch("src.web.app.config_manager.get_model_config")
    def test_image_generation_writes_visible_start_and_result_events(self, mock_get_model, mock_produce):
        state, manifest = self._state_with_approved_assets()
        state = ComicProductionV2.attach_prompt_package(state, self._prompt_package(state, manifest))
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))
        mock_get_model.return_value = ModelConfig(provider="doubao", model="doubao-seedream-5", api_key="test")
        mock_produce.return_value = ImageProductionResult(
            status="ready_for_delivery",
            production_ready=True,
            records=(),
            failures=(),
        )

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/images/generate",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        timeline = self.client.get(f"/api/workspaces/{self.workspace_id}/tasks").json()["tasks"]
        v2_task = next(item for item in timeline if item["task_id"] == f"comic_v2_{self.workspace_id}")
        event_types = [item["event_type"] for item in v2_task["events"]]
        self.assertIn("comic_v2_images_started", event_types)
        self.assertIn("comic_v2_images_reviewed", event_types)
        self.assertEqual(v2_task["status"], "completed")
        self.assertEqual(v2_task["current_phase"], "document_generation")

    def test_visual_review_override_endpoint_requires_explicit_reason(self):
        state, manifest = self._state_with_approved_assets()
        state = ComicProductionV2.attach_prompt_package(state, self._prompt_package(state, manifest))
        state = state.with_status(stage="visual_review", image_production={"production_ready": False})
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))

        blocked = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/images/override",
            json={"reason": ""},
        )
        self.assertIn(blocked.status_code, {400, 422})

        approved = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/images/override",
            json={"reason": "人物风格偏差可接受，后续平台继续修正"},
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["stage"], "document_generation")

    @patch("src.web.app.build_delivery_from_v2")
    def test_delivery_endpoint_persists_downloadable_word_canvas(self, mock_build):
        state, manifest = self._state_with_approved_assets()
        state = ComicProductionV2.attach_prompt_package(state, self._prompt_package(state, manifest))
        state = state.with_status(
            stage="document_generation",
            can_generate_images=False,
            image_production=ImageProductionResult(
                status="ready_for_delivery",
                production_ready=True,
                records=(),
                failures=(),
            ).to_dict(),
        )
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))
        output_dir = Path("output") / "workspaces" / self.workspace_id / "delivery"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "test_v2_canvas.docx"
        output_path.write_bytes(b"fake-docx")
        handoff_manifest_path = output_dir / "test_v2_canvas_handoff_manifest.json"
        handoff_manifest_path.write_text("{}", encoding="utf-8")
        mock_build.return_value = CanvasBuildResult(
            path=output_path,
            audit=DocumentAudit(
                embedded_images=0,
                asset_count=1,
                shot_count=1,
                missing_image_asset_ids=(),
                structural_errors=(),
                max_table_columns=2,
                handoff_ready=True,
            ),
            handoff_manifest_path=handoff_manifest_path,
        )

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/delivery/build",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["stage"], "ready_for_handoff")
        self.assertIn("/files/delivery/test_v2_canvas_handoff_manifest.json", payload["delivery"]["handoff_manifest_uri"])
        artifacts = config_manager.list_artifacts(workspace_id=self.workspace_id)
        delivery = next(item for item in artifacts if item["artifact_type"] == "comic_v2_word_canvas")
        self.assertIn("/files/delivery/test_v2_canvas.docx", delivery["uri"])
        handoff = next(item for item in artifacts if item["artifact_type"] == "comic_v2_handoff_manifest")
        self.assertIn("/files/delivery/test_v2_canvas_handoff_manifest.json", handoff["uri"])
        output_path.unlink(missing_ok=True)
        handoff_manifest_path.unlink(missing_ok=True)

    @patch("src.web.app.build_delivery_from_v2")
    def test_delivery_build_writes_visible_start_and_result_events(self, mock_build):
        state, manifest = self._state_with_approved_assets()
        state = ComicProductionV2.attach_prompt_package(state, self._prompt_package(state, manifest))
        state = state.with_status(
            stage="document_generation",
            can_generate_images=False,
            image_production=ImageProductionResult(
                status="ready_for_delivery",
                production_ready=True,
                records=(),
                failures=(),
            ).to_dict(),
        )
        config_manager.set_kv(f"comic_v2_state:{self.workspace_id}", json.dumps(state.to_dict(), ensure_ascii=False))
        output_dir = Path("output") / "workspaces" / self.workspace_id / "delivery"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "test_v2_canvas_events.docx"
        output_path.write_bytes(b"fake-docx")
        mock_build.return_value = CanvasBuildResult(
            path=output_path,
            audit=DocumentAudit(
                embedded_images=0,
                asset_count=1,
                shot_count=1,
                missing_image_asset_ids=(),
                structural_errors=(),
                max_table_columns=2,
                handoff_ready=True,
            ),
        )

        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/comic/v2/delivery/build",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        timeline = self.client.get(f"/api/workspaces/{self.workspace_id}/tasks").json()["tasks"]
        v2_task = next(item for item in timeline if item["task_id"] == f"comic_v2_{self.workspace_id}")
        event_types = [item["event_type"] for item in v2_task["events"]]
        self.assertIn("comic_v2_delivery_started", event_types)
        self.assertIn("comic_v2_delivery_ready", event_types)
        self.assertEqual(v2_task["status"], "completed")
        self.assertEqual(v2_task["current_phase"], "ready_for_handoff")
        output_path.unlink(missing_ok=True)

    def _state_with_approved_assets(self):
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
        return ComicProductionV2.approve_asset_manifest(state), manifest

    @staticmethod
    def _prompt_package(state, manifest):
        prompt = PromptPlan(
            object_id=manifest.items[0].asset_id,
            image_kind="three_view",
            purpose="identity_reference",
            generator_prompt="林昭三视图，靛青长袍，纯白干净背景",
            negative_prompt=("禁止文字",),
            style_id=state.style_id,
        )
        return PromptPackage(
            package_id="prompts_api",
            story_id=state.story_id,
            story_version=state.story_version,
            style_id=state.style_id,
            style_version=state.style_version,
            manifest_id=manifest.manifest_id,
            manifest_version=manifest.version,
            prompts=(prompt,),
            shots=(),
        )


if __name__ == "__main__":
    unittest.main()
