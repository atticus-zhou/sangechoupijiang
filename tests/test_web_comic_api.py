import sqlite3
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.llm.providers import LLMResponse, LiteLLMProvider, ModelConfig
from src.comic_office.v2.pipeline import not_started_state
from src.web.app import (
    _comic_image_specs,
    _history_delivery_summary,
    _comic_v2_handoff_production_lineage,
    _comic_v2_handoff_quality_benchmark,
    app,
    config_manager,
)


class WebComicApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.created_workspaces = []

    def tearDown(self):
        if not self.created_workspaces:
            return
        conn = sqlite3.connect("user_data/config.db")
        for workspace_id in self.created_workspaces:
            conn.execute("DELETE FROM artifacts WHERE workspace_id=?", (workspace_id,))
            conn.execute("DELETE FROM workspaces WHERE workspace_id=?", (workspace_id,))
            conn.execute("DELETE FROM config_store WHERE key=?", (f"comic_cabinet_session:{workspace_id}",))
            conn.execute("DELETE FROM config_store WHERE key=?", (f"comic_v2_state:{workspace_id}",))
            conn.execute("DELETE FROM task_events WHERE task_id=?", (f"comic_v2_{workspace_id}",))
            conn.execute("DELETE FROM task_runs WHERE task_id=?", (f"comic_v2_{workspace_id}",))
        conn.commit()
        conn.close()
        for workspace_id in self.created_workspaces:
            shutil.rmtree(Path("output") / "workspaces" / workspace_id, ignore_errors=True)

    def test_handoff_lineage_summary_preserves_handoff_and_acceptance_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "handoff.json"
            manifest_path.write_text(json.dumps({
                "production_lineage": [
                    {
                        "stage": "visual_bible",
                        "stage_label": "风格圣经",
                        "department": "中书省 / 门下省",
                        "agent": "美术设定官 / 连续性审核官",
                        "status": "locked",
                        "human_checkpoint": "用户确认视觉母版",
                        "handoff_to": "资产拆解",
                        "acceptance_criteria": "视觉母版包含画风、时代、比例、色彩、服装和禁用元素。",
                        "output": "电影级国风厚涂动画 · 9:16",
                        "internal_notes": "仅内部使用的调试字段",
                    }
                ]
            }, ensure_ascii=False), encoding="utf-8")

            summary = _comic_v2_handoff_production_lineage(manifest_path)

        self.assertEqual(summary[0]["handoff_to"], "资产拆解")
        self.assertIn("视觉母版", summary[0]["acceptance_criteria"])
        self.assertNotIn("internal_notes", summary[0])

    def test_handoff_quality_benchmark_summary_is_human_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "handoff.json"
            manifest_path.write_text(json.dumps({
                "quality_benchmark": {
                    "benchmark_version": 1,
                    "status": "production_quality_verified",
                    "package_quality_score": 94,
                    "package_quality_ready": True,
                    "production_quality_verified": True,
                    "visual_evidence_level": "model_reviewed",
                    "summary": "真实模型质量已验证。",
                    "issue_count": 0,
                    "blocker_count": 0,
                    "dimensions": [
                        {"id": "story_grounding", "label": "故事贴合度", "status": "passed", "score": 100, "internal": "drop"}
                    ],
                    "limitations": [],
                    "recommended_recovery": {
                        "department": "工部 / 刑部",
                        "action": "regenerate_images",
                        "focus": "images",
                        "label": "重新生成并质检图片",
                        "reason_code": "visual.review_dimensions",
                        "description": "重新生成图片。",
                        "expected_stage": "image_generation",
                        "preserves": ["confirmed_story", "prompt_package"],
                        "clears": ["image_production"],
                        "operator_steps": ["退回到图片生成阶段", "重新生成失败图片"],
                        "internal": "drop",
                    },
                    "next_action": "进入下游生产。",
                    "raw_model_output": "drop",
                }
            }, ensure_ascii=False), encoding="utf-8")

            summary = _comic_v2_handoff_quality_benchmark(manifest_path)

        self.assertEqual(summary["package_quality_score"], 94)
        self.assertTrue(summary["production_quality_verified"])
        self.assertEqual(summary["dimensions"][0]["label"], "故事贴合度")
        self.assertEqual(summary["recommended_recovery"]["action"], "regenerate_images")
        self.assertEqual(summary["recommended_recovery"]["expected_stage"], "image_generation")
        self.assertIn("prompt_package", summary["recommended_recovery"]["preserves"])
        self.assertIn("image_production", summary["recommended_recovery"]["clears"])
        self.assertEqual(len(summary["recommended_recovery"]["operator_steps"]), 2)
        self.assertNotIn("internal", summary["recommended_recovery"])
        self.assertNotIn("raw_model_output", summary)
        self.assertNotIn("internal", summary["dimensions"][0])

    def test_history_quality_recovery_posts_stage_reset_with_action_body(self):
        summary = _history_delivery_summary({
            "workspace_id": "ws_quality_recovery",
            "office_id": "comic_production",
            "word_canvas_uri": "/word.docx",
            "handoff_manifest_uri": "/handoff.json",
            "artifacts": [],
            "comic_v2_trace": {
                "delivery_audit": {"handoff_ready": True, "asset_count": 2, "shot_count": 3},
                "visual_review": {"production_ready": True, "failure_count": 0},
                "quality_benchmark": {
                    "status": "needs_review",
                    "package_quality_ready": False,
                    "package_quality_score": 76,
                    "summary": "提示词高度雷同。",
                    "next_action": "重新生成提示词。",
                    "recommended_recovery": {
                        "department": "工部 / 兵部 / 刑部",
                        "action": "regenerate_prompts",
                        "focus": "prompts",
                        "label": "重新生成提示词和镜头卡",
                        "description": "保留故事和资产，退回提示词导演阶段。",
                        "expected_stage": "prompt_planning",
                        "preserves": ["confirmed_story", "asset_manifest"],
                        "clears": ["prompt_package", "image_production"],
                        "operator_steps": ["回到提示词规划", "重新生成导演型镜头提示词", "重新质检制片包"],
                    },
                },
            },
        })

        self.assertEqual(summary["status"], "needs_review")
        self.assertIn("制片包质量基准", summary["missing_items"])
        action = summary["recovery_actions"][0]
        self.assertEqual(action["path"], "/api/workspaces/ws_quality_recovery/comic/v2/quality/recover")
        self.assertEqual(action["body"], {"action": "regenerate_prompts"})
        self.assertEqual(action["focus"], "prompts")
        self.assertEqual(action["expected_stage"], "prompt_planning")
        self.assertIn("asset_manifest", action["preserves"])
        self.assertIn("image_production", action["clears"])
        self.assertEqual(action["operator_steps"][0], "回到提示词规划")

    def test_history_can_rebuild_an_early_v2_package_missing_quality_benchmark(self):
        summary = _history_delivery_summary({
            "workspace_id": "ws_missing_benchmark",
            "office_id": "comic_production",
            "word_canvas_uri": "/word.docx",
            "handoff_manifest_uri": "/handoff.json",
            "artifacts": [{"artifact_type": "comic_v2_word_canvas"}],
            "comic_v2_trace": {
                "delivery_audit": {"handoff_ready": True, "asset_count": 2, "shot_count": 3},
                "visual_review": {"production_ready": True, "failure_count": 0},
            },
        })

        self.assertEqual(summary["status"], "needs_review")
        self.assertIn("制片包质量基准", summary["missing_items"])
        self.assertEqual(len(summary["recovery_actions"]), 1)
        action = summary["recovery_actions"][0]
        self.assertEqual(action["label"], "补齐 V3 引用与质量清单")
        self.assertEqual(action["path"], "/api/workspaces/ws_missing_benchmark/comic/v2/quality/recover")
        self.assertEqual(action["body"], {"action": "rebuild_delivery"})

    def test_history_can_upgrade_fixture_images_to_real_model_evidence(self):
        summary = _history_delivery_summary({
            "workspace_id": "ws_fixture_images",
            "office_id": "comic_production",
            "word_canvas_uri": "/word.docx",
            "handoff_manifest_uri": "/handoff.json",
            "artifacts": [
                {"artifact_type": "comic_v2_word_canvas"},
                {"artifact_type": "comic_v2_prompt_package"},
                {"artifact_type": "comic_v2_generated_image"},
            ],
            "comic_v2_trace": {
                "asset_prompt_count": 3,
                "shot_prompt_count": 2,
                "delivery_audit": {"handoff_ready": True, "asset_count": 3, "shot_count": 2},
                "visual_review": {"production_ready": True, "failure_count": 0},
                "quality_benchmark": {
                    "status": "demo_structure_verified",
                    "package_quality_ready": True,
                    "production_quality_verified": False,
                },
                "image_production_evidence": {
                    "evidence_level": "fixture_only",
                    "supports_real_quality_claim": False,
                    "next_action": "用真实模型重新生成图片。",
                },
            },
        })

        self.assertEqual(summary["status"], "needs_review")
        self.assertIn("图片生产证据", summary["missing_items"])
        action = summary["recovery_actions"][0]
        self.assertEqual(action["body"], {"action": "regenerate_images"})
        self.assertEqual(action["focus"], "images")
        self.assertEqual(action["expected_stage"], "image_generation")
        self.assertIn("prompt_package", action["preserves"])
        self.assertIn("image_production", action["clears"])

    def test_quality_recovery_api_reopens_prompt_planning_without_losing_assets(self):
        workspace_id = f"ws_quality_recover_{uuid.uuid4().hex[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="质量恢复测试",
        )
        state = not_started_state(workspace_id)
        state.update({
            "status": "waiting_for_human",
            "stage": "ready_for_handoff",
            "story_id": "story_quality",
            "story_version": 1,
            "style_id": "style_quality",
            "style_version": 1,
            "contract": {"status": "visual_bible_approved"},
            "completed": 7,
            "total": 7,
            "assets_status": "approved",
            "shots_status": "ready",
            "document_status": "needs_review",
            "asset_manifest": {
                "manifest_id": "manifest_quality",
                "version": 2,
                "items": [{"asset_id": "character_1"}],
            },
            "prompt_package": {
                "package_id": "prompts_quality",
                "prompts": [{"object_id": "character_1"}],
            },
            "image_production": {
                "production_ready": True,
                "records": [{"image_id": "image_1"}],
            },
            "delivery": {
                "path": "C:/delivery/canvas.docx",
                "quality_benchmark": {
                    "status": "needs_review",
                    "package_quality_ready": False,
                    "recommended_recovery": {
                        "department": "工部 / 兵部 / 刑部",
                        "action": "regenerate_prompts",
                        "focus": "prompts",
                        "label": "重新生成提示词和镜头卡",
                        "reason_code": "prompt.cross_asset_uniqueness",
                    },
                },
            },
        })
        config_manager.set_kv(f"comic_v2_state:{workspace_id}", json.dumps(state, ensure_ascii=False))

        blocked = self.client.post(
            f"/api/workspaces/{workspace_id}/comic/v2/quality/recover",
            json={"action": "regenerate_images"},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertIn("与质量基准建议", blocked.json()["detail"]["reason"])
        unchanged = json.loads(config_manager.get_kv(f"comic_v2_state:{workspace_id}"))
        self.assertEqual(unchanged["stage"], "ready_for_handoff")
        self.assertTrue(unchanged["delivery"])

        response = self.client.post(
            f"/api/workspaces/{workspace_id}/comic/v2/quality/recover",
            json={"action": "regenerate_prompts"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["stage"], "prompt_planning")
        self.assertEqual(payload["assets_status"], "approved")
        self.assertEqual(payload["asset_manifest"]["manifest_id"], "manifest_quality")
        self.assertFalse(payload["prompt_package"])
        self.assertFalse(payload["image_production"])
        self.assertFalse(payload["delivery"])

    def test_quality_recovery_can_upgrade_demo_structure_images(self):
        workspace_id = f"ws_quality_upgrade_{uuid.uuid4().hex[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="真实图片证据升级测试",
        )
        state = not_started_state(workspace_id)
        state.update({
            "status": "waiting_for_human",
            "stage": "ready_for_handoff",
            "story_id": "story_upgrade",
            "story_version": 1,
            "style_id": "style_upgrade",
            "style_version": 1,
            "contract": {"status": "visual_bible_approved"},
            "completed": 7,
            "total": 7,
            "assets_status": "approved",
            "shots_status": "ready",
            "document_status": "ready",
            "asset_manifest": {
                "manifest_id": "manifest_upgrade",
                "version": 2,
                "items": [{"asset_id": "character_1"}],
            },
            "prompt_package": {
                "package_id": "prompts_upgrade",
                "prompts": [{"object_id": "character_1"}],
            },
            "image_production": {
                "production_ready": True,
                "records": [{"image_id": "fixture_image", "provider": "fixture"}],
            },
            "delivery": {
                "path": "C:/delivery/canvas.docx",
                "quality_benchmark": {
                    "status": "demo_structure_verified",
                    "package_quality_ready": True,
                    "production_quality_verified": False,
                },
            },
        })
        config_manager.set_kv(f"comic_v2_state:{workspace_id}", json.dumps(state, ensure_ascii=False))

        response = self.client.post(
            f"/api/workspaces/{workspace_id}/comic/v2/quality/recover",
            json={"action": "regenerate_images"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["stage"], "image_generation")
        self.assertTrue(payload["prompt_package"])
        self.assertFalse(payload["image_production"])
        self.assertFalse(payload["delivery"])
        self.assertTrue(payload["can_generate_images"])

    def test_history_marks_legacy_word_canvas_as_downloadable_but_unverifiable(self):
        task_id = f"hist_legacy_{uuid.uuid4().hex[:8]}"
        workspace_id = f"ws_legacy_{uuid.uuid4().hex[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="旧版制片包",
        )
        config_manager.save_task_record(
            task_id,
            "旧版制片包",
            "",
            "completed",
            {"final_report": "legacy package"},
        )
        config_manager.create_task_run(task_id, "旧版制片包", "")
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_word",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="word_canvas",
            title="旧版 Word 制片画布",
            uri=f"/api/workspaces/{workspace_id}/files/delivery/legacy.docx",
            content="legacy",
            metadata={"office_id": "comic_production"},
            created_by="libu",
        )
        try:
            response = self.client.get("/api/tasks/history?limit=30")
            self.assertEqual(response.status_code, 200)
            row = next(item for item in response.json()["history"] if item["task_id"] == task_id)
            summary = row["delivery_summary"]
            self.assertTrue(row["legacy_comic_package"])
            self.assertEqual(summary["status"], "partial")
            self.assertTrue(summary["legacy_package"])
            self.assertEqual(summary["package_quality_claim"], "legacy_unverifiable")
            self.assertFalse(summary["package_quality_ready"])
            self.assertIn("V3 引用与质量清单", summary["missing_items"])
            self.assertIn("旧版制片包", summary["next_action"])
            self.assertEqual(summary["recovery_actions"], [])
        finally:
            conn = sqlite3.connect("user_data/config.db")
            conn.execute("DELETE FROM task_history WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_runs WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_events WHERE task_id=?", (task_id,))
            conn.commit()
            conn.close()

    def test_task_detail_exposes_recovery_plan_for_failed_run(self):
        task_id = f"task_recover_{uuid.uuid4().hex[:8]}"
        workspace_id = f"ws_recover_{uuid.uuid4().hex[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="恢复计划测试",
        )
        config_manager.create_task_run(task_id, "生成基础资产图", "")
        config_manager.update_task_run(
            task_id,
            "failed",
            current_phase="image_generation",
            error="资产图片生产失败：视觉质检输出不完整",
            completed=True,
        )
        config_manager.append_task_event(
            task_id,
            "comic_v2_images_failed",
            "failed",
            "基础资产图生产或质检失败",
            {
                "workspace_id": workspace_id,
                "office_id": "comic_production",
                "department": "工部 / 刑部",
                "stage": "image_generation",
                "next_action": "检查模型配置后重新生成并质检基础资产图。",
                "retry_action": {
                    "label": "重新生成基础资产图",
                    "method": "POST",
                    "path": f"/api/workspaces/{workspace_id}/comic/v2/images/generate",
                },
            },
        )

        response = self.client.get(f"/api/tasks/{task_id}")

        self.assertEqual(response.status_code, 200)
        plan = response.json()["recovery_plan"]
        self.assertTrue(plan["recoverable"])
        self.assertEqual(plan["department"], "工部 / 刑部")
        self.assertEqual(plan["retry_action"]["method"], "POST")

    def test_task_detail_exposes_delivery_retry_action_for_word_canvas_failure(self):
        workspace_id = f"ws_delivery_recover_{uuid.uuid4().hex[:8]}"
        task_id = f"comic_v2_{workspace_id}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Word 恢复计划测试",
        )
        config_manager.create_task_run(task_id, "生成 Word 制片画布", "")
        config_manager.update_task_run(
            task_id,
            "failed",
            current_phase="document_generation",
            error="Word 制片画布生成失败：缺少资产图",
            completed=True,
        )
        config_manager.append_task_event(
            task_id,
            "comic_v2_delivery_failed",
            "failed",
            "Word 制片画布生成失败",
            {
                "workspace_id": workspace_id,
                "office_id": "comic_production",
                "department": "礼部 / 刑部",
                "stage": "document_generation",
                "next_action": "修复缺失资产后重新生成 Word 制片画布。",
            },
        )

        response = self.client.get(f"/api/tasks/{task_id}")

        self.assertEqual(response.status_code, 200)
        plan = response.json()["recovery_plan"]
        self.assertTrue(plan["recoverable"])
        self.assertEqual(plan["retry_action"]["path"], f"/api/workspaces/{workspace_id}/comic/v2/delivery/build")
        self.assertEqual(plan["retry_action"]["label"], "重新生成 Word 制片画布")

    def test_comic_cabinet_turn_creates_and_persists_session(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "一个女孩每天醒来都会进入不同漫画世界",
            "genre": "fantasy",
            "length": "5 episodes",
            "platform": "Douyin",
            "visual_style": "Korean webtoon",
            "extra": "希望有悬疑感",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        self.assertIn(body["status"], {"needs_more_discussion", "script_ready"})
        self.assertIn("session", body)
        self.assertIn("creative_brief", body)
        self.assertIn("script_preview", body)
        self.assertEqual(len(body["cabinet_roles"]), 0)

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "一个女孩每天醒来都会进入不同漫画世界",
            "genre": "fantasy",
            "length": "5 episodes",
            "platform": "Douyin",
            "visual_style": "Korean webtoon",
            "extra": "希望有悬疑感",
            "user_message": "主角是普通女大学生，每次穿越都会失去一点现实记忆，最后发现这些世界是她为了逃避妹妹去世创造的。",
            "session": body["session"],
        })
        self.assertEqual(response.status_code, 200)
        second = response.json()
        self.assertIn("女大学生", second["script_preview"]["user_answers"])

        saved = self.client.get(f"/api/comic/cabinet/{workspace_id}")
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["status"], "ok")
        self.assertIn("女大学生", saved.json()["session"]["script_preview"]["user_answers"])
        self.assertIn("assistant_message", saved.json())
        self.assertTrue(saved.json()["assistant_message"])

    def test_comic_production_cabinet_creates_isolated_workspace(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "office_id": "comic_production",
            "idea": "A fallen healer in a cultivation team becomes the key to the revenge story.",
            "genre": "fantasy costume drama",
            "length": "5 episodes",
            "platform": "vertical short drama",
            "visual_style": "cinematic comic",
            "extra": "Need a production-ready package.",
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        workspace = config_manager.get_workspace(workspace_id)
        self.assertEqual(workspace["office_id"], "comic_production")
        self.assertEqual(body["office_id"], "comic_production")
        saved = self.client.get(f"/api/comic/cabinet/{workspace_id}")
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["office_id"], "comic_production")

    def test_comic_cabinet_defaults_to_production_office(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "A city clerk discovers every elevator opens to a different ending.",
            "genre": "urban fantasy",
            "length": "3 episodes",
            "platform": "vertical short drama",
            "visual_style": "cinematic comic",
            "extra": "",
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        self.assertEqual(body["office_id"], "comic_production")
        self.assertEqual(config_manager.get_workspace(workspace_id)["office_id"], "comic_production")

    def test_comic_cabinet_requires_idea_with_actionable_error(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "",
            "genre": "fantasy",
            "length": "3 episodes",
            "platform": "vertical short drama",
            "visual_style": "cinematic comic",
            "extra": "",
        })

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["office_id"], "comic_production")
        self.assertEqual(detail["department"], "内阁")
        self.assertIn("灵感", detail["reason"])
        self.assertIn("故事", detail["impact"])
        self.assertIn("一句", detail["next_action"])

    def test_legacy_comic_brief_errors_are_actionable(self):
        brief = self.client.post("/api/comic/brief", json={
            "idea": "",
            "genre": "fantasy",
            "length": "3 episodes",
            "platform": "vertical short drama",
            "visual_style": "cinematic comic",
            "extra": "",
        })
        self.assertEqual(brief.status_code, 400)
        brief_detail = brief.json()["detail"]
        self.assertEqual(brief_detail["office_id"], "comic_production")
        self.assertEqual(brief_detail["stage"], "story_brief")
        self.assertTrue(brief_detail["reason"])
        self.assertTrue(brief_detail["impact"])
        self.assertTrue(brief_detail["next_action"])

        preview = self.client.post("/api/comic/script-preview", json={
            "idea": "A healer dies during a mission.",
            "genre": "fantasy",
            "length": "3 episodes",
            "platform": "vertical short drama",
            "visual_style": "cinematic comic",
            "extra": "",
            "creative_brief": {},
            "user_answers": "",
        })
        self.assertEqual(preview.status_code, 400)
        preview_detail = preview.json()["detail"]
        self.assertEqual(preview_detail["office_id"], "comic_production")
        self.assertEqual(preview_detail["stage"], "script_preview")
        self.assertTrue(preview_detail["reason"])
        self.assertTrue(preview_detail["impact"])
        self.assertTrue(preview_detail["next_action"])

    def test_comic_workspace_lookup_errors_are_actionable(self):
        unsupported = self.client.post("/api/comic/cabinet/turn", json={
            "office_id": "research",
            "idea": "A wrong office should be rejected clearly.",
            "genre": "fantasy",
            "length": "3 episodes",
            "platform": "vertical short drama",
            "visual_style": "cinematic comic",
            "extra": "",
        })
        self.assertEqual(unsupported.status_code, 400)
        unsupported_detail = unsupported.json()["detail"]
        self.assertEqual(unsupported_detail["office_id"], "comic_production")
        self.assertEqual(unsupported_detail["stage"], "office_routing")
        self.assertTrue(unsupported_detail["reason"])
        self.assertTrue(unsupported_detail["impact"])
        self.assertTrue(unsupported_detail["next_action"])

        missing = self.client.get("/api/comic/cabinet/ws_missing_comic_session")
        self.assertEqual(missing.status_code, 404)
        missing_detail = missing.json()["detail"]
        self.assertEqual(missing_detail["office_id"], "comic_production")
        self.assertEqual(missing_detail["stage"], "workspace_lookup")
        self.assertTrue(missing_detail["reason"])
        self.assertTrue(missing_detail["impact"])
        self.assertTrue(missing_detail["next_action"])

    def test_confirm_script_requires_cabinet_session_with_actionable_error(self):
        workspace_id = f"ws_comic_err_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="No session",
            brief="",
        )

        response = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "office_id": "comic_production",
            "session": {},
            "confirmation_notes": "",
        })

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["department"], "内阁")
        self.assertIn("内阁讨论", detail["reason"])
        self.assertIn("确认剧本", detail["impact"])
        self.assertIn("开始聊故事", detail["next_action"])

    def test_asset_review_decision_errors_are_actionable(self):
        workspace_id = f"ws_asset_err_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="No asset package",
            brief="",
        )

        invalid = self.client.post(
            f"/api/workspaces/{workspace_id}/comic/asset-review/decision",
            json={"status": "bad_status"},
        )
        self.assertEqual(invalid.status_code, 400)
        invalid_detail = invalid.json()["detail"]
        self.assertEqual(invalid_detail["department"], "门下省")
        self.assertIn("审核状态", invalid_detail["reason"])
        self.assertIn("approved", invalid_detail["next_action"])

        missing = self.client.post(
            f"/api/workspaces/{workspace_id}/comic/asset-review/decision",
            json={"status": "approved"},
        )
        self.assertEqual(missing.status_code, 404)
        missing_detail = missing.json()["detail"]
        self.assertEqual(missing_detail["department"], "门下省")
        self.assertIn("资产审核包", missing_detail["reason"])
        self.assertIn("资产拆解", missing_detail["next_action"])

    def test_comic_production_task_uses_its_own_office_scope(self):
        workspace_id = f"ws_prod_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Production isolation test",
            brief="A confirmed story should start in the production office.",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_confirmed_script",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="confirmed_script",
            title="Confirmed script",
            content="Confirmed script hash: prod_scope_test",
            metadata={"office_id": "comic_production", "script_hash": "prod_scope_test", "confirmed": True},
            created_by="shangshu",
        )

        class DummyTask:
            def add_done_callback(self, callback):
                return None

        def fake_create_task(coro):
            coro.close()
            return DummyTask()

        with patch("src.web.app._schedule_background_task", side_effect=fake_create_task):
            started = self.client.post("/api/tasks", json={
                "user_request": "Idea: production isolation",
                "office_id": "comic_production",
                "workspace_id": workspace_id,
            })

        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["office_id"], "comic_production")
        run = config_manager.get_task_run(started.json()["task_id"])
        self.assertIn("prod_scope_test", run["user_request"])
        conn = sqlite3.connect("user_data/config.db")
        conn.execute("DELETE FROM task_runs WHERE task_id=?", (started.json()["task_id"],))
        conn.execute("DELETE FROM task_events WHERE task_id=?", (started.json()["task_id"],))
        conn.commit()
        conn.close()

    def test_comic_production_task_blocks_after_asset_review_when_image_models_are_missing(self):
        workspace_id = f"ws_prod_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Production image model guard",
            brief="A confirmed story should not start without image models.",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_confirmed_script",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="confirmed_script",
            title="Confirmed script",
            content="Confirmed script hash: prod_guard_test",
            metadata={"office_id": "comic_production", "script_hash": "prod_guard_test", "confirmed": True},
            created_by="shangshu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_asset_review_package",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="asset_review_package",
            title="Asset review package",
            content="Assets approved for image generation.",
            metadata={"office_id": "comic_production", "script_hash": "prod_guard_test", "review_status": "approved", "requires_human_review": True},
            created_by="menxia",
        )
        original_config = config_manager.load_yaml()
        modified_config = config_manager.load_yaml()
        modified_config.setdefault("office_models", {})["comic_production"] = {
            "gongbu": {"provider": "dashscope", "model": "qwen-vl-max", "api_key": "vision-key"},
            "bingbu": {"provider": "deepseek", "model": "deepseek-chat", "api_key": "chat-key"},
        }
        config_manager.save_yaml(modified_config)
        try:
            started = self.client.post("/api/tasks", json={
                "user_request": "Idea: production guard",
                "office_id": "comic_production",
                "workspace_id": workspace_id,
            })
        finally:
            config_manager.save_yaml(original_config)

        self.assertEqual(started.status_code, 400)
        detail = started.json()["detail"]
        self.assertEqual(detail["office_id"], "comic_production")
        self.assertEqual(detail["stage"], "production_start")
        self.assertIn("doubao-seedream-5", detail["reason"])
        self.assertIn("qwen-vl-max", detail["reason"])
        self.assertIn("deepseek-chat", detail["reason"])
        self.assertTrue(detail["impact"])
        self.assertTrue(detail["next_action"])

    def test_asset_review_decision_is_bound_to_current_confirmed_script(self):
        workspace_id = f"ws_review_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Asset review decision",
            brief="Asset review should be explicit and script-bound.",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_confirmed_script",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="confirmed_script",
            title="Confirmed script",
            content="Confirmed script hash: current_hash",
            metadata={"office_id": "comic_production", "script_hash": "current_hash", "script_version": 2, "confirmed": True},
            created_by="shangshu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_asset_review_package",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="asset_review_package",
            title="Asset review package",
            content="人物、道具、场景拆解待审核。",
            metadata={"office_id": "comic_production", "script_hash": "current_hash", "review_status": "pending", "requires_human_review": True},
            created_by="menxia",
        )

        response = self.client.post(
            f"/api/workspaces/{workspace_id}/comic/asset-review/decision",
            json={"status": "approved", "reviewer_notes": "人物和场景拆解可以进入生产。"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "approved")
        artifact = config_manager.get_artifact(f"art_{workspace_id}_asset_review_package")
        metadata = artifact["metadata"]
        self.assertEqual(metadata["review_status"], "approved")
        self.assertEqual(metadata["script_hash"], "current_hash")
        self.assertEqual(metadata["script_version"], 2)
        self.assertEqual(metadata["reviewer_notes"], "人物和场景拆解可以进入生产。")
        self.assertTrue(metadata["reviewed_at"])

    def test_old_asset_review_approval_cannot_unlock_new_confirmed_script(self):
        workspace_id = f"ws_old_review_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Old review must not unlock",
            brief="Old approved asset review should not unlock a new script hash.",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_confirmed_script",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="confirmed_script",
            title="Confirmed script",
            content="Confirmed script hash: new_hash",
            metadata={"office_id": "comic_production", "script_hash": "new_hash", "script_version": 2, "confirmed": True},
            created_by="shangshu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_asset_review_package",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="asset_review_package",
            title="Old asset review package",
            content="Old assets approved.",
            metadata={"office_id": "comic_production", "script_hash": "old_hash", "review_status": "approved", "requires_human_review": True},
            created_by="menxia",
        )

        class DummyTask:
            def add_done_callback(self, callback):
                return None

        def fake_create_task(coro):
            coro.close()
            return DummyTask()

        with patch("src.web.app._schedule_background_task", side_effect=fake_create_task):
            started = self.client.post("/api/tasks", json={
                "user_request": "Idea: new story",
                "office_id": "comic_production",
                "workspace_id": workspace_id,
            })

        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["office_id"], "comic_production")

    def test_history_exposes_comic_word_canvas_download(self):
        task_id = f"hist_{str(uuid.uuid4())[:8]}"
        workspace_id = f"ws_hist_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic",
            title="历史下载测试",
            brief="测试历史页下载 Word 画布",
        )
        config_manager.save_task_record(
            task_id,
            "生成历史下载测试制片包",
            "",
            "completed",
            {"final_report": "完整制片包已经生成。"},
        )
        config_manager.create_task_run(task_id, "生成历史下载测试制片包", "")
        config_manager.append_task_event(
            task_id=task_id,
            event_type="task_created",
            status="queued",
            summary="Task accepted by Web API",
            payload={"office_id": "comic", "workspace_id": workspace_id},
        )
        config_manager.update_task_run(
            task_id,
            "completed",
            current_phase="completed",
            result={"final_report": "完整制片包已经生成。"},
            completed=True,
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_word",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="word_canvas",
            title="历史下载测试 - Word制片画布",
            uri=f"/api/workspaces/{workspace_id}/files/delivery/test.docx",
            content="# Word制片画布",
            metadata={"office_id": "comic"},
            created_by="gongbu",
        )
        try:
            response = self.client.get("/api/tasks/history?limit=20")
            self.assertEqual(response.status_code, 200)
            row = next(item for item in response.json()["history"] if item["task_id"] == task_id)
            self.assertEqual(row["workspace_id"], workspace_id)
            self.assertEqual(row["artifact_count"], 1)
            self.assertTrue(row["word_canvas_uri"].endswith("/test.docx"))
            self.assertEqual(row["workspace_export_uri"], f"/api/workspaces/{workspace_id}/export")
        finally:
            conn = sqlite3.connect("user_data/config.db")
            conn.execute("DELETE FROM task_history WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_runs WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_events WHERE task_id=?", (task_id,))
            conn.commit()
            conn.close()

    def test_history_exposes_comic_v2_word_canvas_download(self):
        task_id = f"hist_v2_{str(uuid.uuid4())[:8]}"
        workspace_id = f"ws_hist_v2_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="V2 Word History",
            brief="history download",
        )
        config_manager.save_task_record(
            task_id,
            "build V2 delivery",
            "",
            "completed",
            {"final_report": "V2 delivery ready"},
        )
        config_manager.create_task_run(task_id, "build V2 delivery", "")
        config_manager.append_task_event(
            task_id=task_id,
            event_type="comic_v2_delivery_ready",
            status="completed",
            summary="V2 delivery ready",
            payload={"office_id": "comic_production", "workspace_id": workspace_id},
        )
        config_manager.update_task_run(
            task_id,
            "completed",
            current_phase="completed",
            result={"final_report": "V2 delivery ready"},
            completed=True,
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_v2_word",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="comic_v2_word_canvas",
            title="V2 Word Canvas",
            uri=f"/api/workspaces/{workspace_id}/files/delivery/v2.docx",
            content="ready",
            metadata={
                "office_id": "comic_production",
                "story_id": "story_123",
                "story_version": 3,
                "style_id": "style_456",
                "style_version": 2,
                "manifest_version": 5,
                "download_uri": f"/api/workspaces/{workspace_id}/files/delivery/v2.docx",
                "audit": {"asset_count": 7, "shot_count": 9, "handoff_ready": True},
            },
            created_by="libu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_v2_handoff",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="comic_v2_handoff_manifest",
            title="V2 Handoff Manifest",
            uri=f"/api/workspaces/{workspace_id}/files/delivery/v2_handoff_manifest.json",
            content="ready",
            metadata={
                "office_id": "comic_production",
                "story_id": "story_123",
                "story_version": 3,
                "style_id": "style_456",
                "style_version": 2,
                "manifest_version": 5,
                "download_uri": f"/api/workspaces/{workspace_id}/files/delivery/v2_handoff_manifest.json",
                "word_canvas_uri": f"/api/workspaces/{workspace_id}/files/delivery/v2.docx",
                "production_lineage": [
                    {
                        "stage": "story_contract",
                        "stage_label": "故事合同",
                        "department": "内阁 / 中书省",
                        "agent": "主创对话官 / 中书省",
                        "status": "confirmed",
                        "human_checkpoint": "用户确认故事",
                    },
                    {
                        "stage": "delivery",
                        "stage_label": "Word 画布交付",
                        "department": "礼部 / 刑部",
                        "agent": "交付排版官 / 结构审计官",
                        "status": "handoff_ready",
                        "human_checkpoint": "交付前结构审计",
                    },
                ],
                "shots": [
                    {
                        "shot_id": "shot_001",
                        "story_beat": "主角推门进入月塔",
                        "first_frame_reference_image": {
                            "asset_id": "char_001",
                            "image_id": "img_char_001_three_view",
                            "image_kind": "three_view",
                            "file": "char_001_three_view.png",
                        },
                        "reference_asset_chain": [
                            {
                                "asset_id": "char_001",
                                "name": "林昭",
                                "asset_type": "character",
                                "first_frame_file": "char_001_three_view.png",
                            }
                        ],
                        "video_prompt_block": "首帧参考林昭，缓慢前推。",
                        "negative_prompt_block": "禁止脸型变化",
                        "execution_steps": ["绑定首帧参考图片", "粘贴视频提示词", "按验收标准检查"],
                    }
                ],
                "quality_benchmark": {
                    "benchmark_version": 1,
                    "status": "production_quality_verified",
                    "package_quality_score": 96,
                    "package_quality_ready": True,
                    "production_quality_verified": True,
                    "visual_evidence_level": "model_reviewed",
                    "image_quality_summary": {
                        "total_images": 1,
                        "usable_images": 1,
                        "waste_or_rework_images": 0,
                        "waste_or_rework_rate": 0,
                        "regenerate_image_count": 0,
                        "rerun_visual_review_count": 0,
                        "regenerate_prompt_count": 0,
                        "failed_image_ids": [],
                        "rework_instructions": [],
                    },
                    "summary": "制片包质量已验证。",
                    "issue_count": 0,
                    "blocker_count": 0,
                    "dimensions": [],
                    "limitations": [],
                    "next_action": "进入下游生产。",
                },
            },
            created_by="libu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_prompt_pkg",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="comic_v2_prompt_package",
            title="V2 Prompt Package",
            content=json.dumps({
                "prompts": [
                    {
                        "object_id": "character_001",
                        "image_kind": "three_view",
                        "production_role": "clean_character_identity_three_view",
                        "clean_background_required": True,
                        "usage_contract": [
                            "基础资产图只建立角色身份参考，不负责讲述剧情。",
                            "本图种 three_view 用于锁定角色脸型、发型、体型、服装主色和年龄感。",
                        ],
                        "reference_policy": "人物资产用于后续镜头身份一致性参考；镜头生成时继承脸型、发型、服装和年龄感。",
                        "generator_prompt": (
                            "资产ID character_001，资产名称 林昭，风格身份 ink wash fantasy，"
                            "林昭人物三视图，正面、侧面、背面并排，纯白或近白色干净背景，"
                            "锁定角色脸型、发型、体型、青灰长衫、二十岁左右年龄感，"
                            "作为后续镜头身份一致性参考，不加入剧情动作。"
                        ),
                        "negative_prompt": ["禁止剧情动作", "禁止剧情场景", "禁止文字水印"],
                    }
                ],
                "shots": [
                    {
                        "shot_id": "shot_001",
                        "first_frame_reference_image": {
                            "asset_id": "char_001",
                            "image_id": "img_char_001_three_view",
                            "image_kind": "three_view",
                            "file": "char_001_three_view.png",
                        },
                        "reference_asset_chain": [
                            {
                                "asset_id": "char_001",
                                "asset_type": "character",
                                "name": "林昭",
                                "first_frame_file": "char_001_three_view.png",
                            }
                        ],
                        "generator_prompt": (
                            "原文依据：林昭推门进入月塔，听见塔内传来旧铃声。"
                            "镜头形式：固定镜头一镜到底，中景平视，首帧参考 char_001_three_view.png。"
                            "参考资产：林昭 char_001，继承脸型、发型、青灰长衫和年龄感。"
                            "故事目的：让观众确认主角主动进入危险空间。"
                            "动作链：停步、抬眼、右手推门、身体前倾半步。"
                            "动作表演：警觉、压住呼吸、眼神先看门缝再看塔内。"
                            "摄影：缓慢前推，轻微手持呼吸感。"
                            "灯光：冷月光从门缝侧逆光切入，室内暗部保留细节。"
                            "台词：无台词。"
                            "声音：旧铃声、门轴低响、远处风声。"
                            "连续性要求：严格继承参考资产身份，保持林昭脸型、发型、服装主色和时代质感。"
                        ),
                        "negative_prompt": ["禁止资产身份漂移", "禁止动作顺序混乱", "禁止文字水印"],
                    }
                ],
            }, ensure_ascii=False),
            metadata={
                "office_id": "comic_production",
                "manifest_version": 5,
                "asset_prompt_count": 7,
                "shot_prompt_count": 9,
            },
            created_by="gongbu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_visual_review",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="comic_v2_visual_review",
            title="V2 Visual Review",
            content="{}",
            metadata={
                "office_id": "comic_production",
                "production_ready": True,
                "record_count": 7,
                "failure_count": 0,
            },
            created_by="xingbu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_image_1",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="comic_v2_generated_image",
            title="林昭 / three_view",
            uri=f"/api/workspaces/{workspace_id}/files/generated/{task_id}/char_001_three_view.png",
            content=json.dumps({"image_id": "img_char_001_three_view", "asset_id": "char_001"}, ensure_ascii=False),
            metadata={
                "office_id": "comic_production",
                "image_id": "img_char_001_three_view",
                "asset_id": "char_001",
                "image_kind": "three_view",
                "production_role": "clean_character_identity_three_view",
                "clean_background_required": True,
                "usage_contract": [
                    "基础资产图只建立角色身份参考，不负责讲述剧情。",
                    "本图种 three_view 用于锁定角色脸型、发型、体型、服装主色和年龄感。",
                ],
                "reference_policy": "人物资产用于后续镜头身份一致性参考；镜头生成时继承脸型、发型、服装和年龄感。",
                "status": "approved",
                "attempts": 2,
                "provider": "doubao",
                "model": "seedream",
                "prompt_hash": "hash-three-view",
                "is_identity_baseline": True,
                "reference_image_ids": [],
                "review": {
                    "status": "pass",
                    "handoff_ready": True,
                    "recovery_action": "regenerate_images",
                    "recovery_focus": "images",
                    "recovery_reason": "图片需要重新生成以稳定人物身份。",
                    "rework_label": "保留提示词重新生图",
                    "operator_steps": ["保留当前提示词", "重新生成这张图", "重新执行七维视觉质检"],
                },
                "path": f"output/workspaces/{workspace_id}/generated/{task_id}/char_001_three_view.png",
            },
            created_by="gongbu",
        )
        try:
            response = self.client.get("/api/tasks/history?limit=20")
            self.assertEqual(response.status_code, 200)
            row = next(item for item in response.json()["history"] if item["task_id"] == task_id)
            self.assertTrue(row["word_canvas_uri"].endswith("/v2.docx"))
            self.assertEqual(row["word_canvas_title"], "V2 Word Canvas")
            self.assertTrue(row["handoff_manifest_uri"].endswith("/v2_handoff_manifest.json"))
            self.assertEqual(row["handoff_manifest_title"], "V2 Handoff Manifest")
            self.assertEqual(row["comic_v2_trace_uri"], f"/api/tasks/{task_id}/comic-v2-trace.json")
            word_artifact = next(
                item for item in row["artifacts"]
                if item["artifact_type"] == "comic_v2_word_canvas"
            )
            self.assertEqual(word_artifact["download_kind"], "file")
            self.assertTrue(word_artifact["file_download_uri"].endswith("/v2.docx"))
            self.assertEqual(word_artifact["primary_download_uri"], word_artifact["file_download_uri"])
            self.assertTrue(word_artifact["archive_download_uri"].endswith(f"/art_{task_id}_v2_word/download"))
            handoff_artifact = next(
                item for item in row["artifacts"]
                if item["artifact_type"] == "comic_v2_handoff_manifest"
            )
            self.assertEqual(handoff_artifact["download_kind"], "file")
            self.assertTrue(handoff_artifact["file_download_uri"].endswith("/v2_handoff_manifest.json"))
            prompt_artifact = next(
                item for item in row["artifacts"]
                if item["artifact_type"] == "comic_v2_prompt_package"
            )
            self.assertEqual(prompt_artifact["download_kind"], "archive")
            self.assertEqual(prompt_artifact["file_download_uri"], "")
            self.assertEqual(prompt_artifact["primary_download_uri"], prompt_artifact["download_uri"])
            self.assertEqual(
                prompt_artifact["download_uri"],
                f"/api/tasks/{task_id}/artifacts/art_{task_id}_prompt_pkg/download",
            )
            trace = row["comic_v2_trace"]
            self.assertEqual(trace["story_id"], "story_123")
            self.assertEqual(trace["story_version"], 3)
            self.assertEqual(trace["style_version"], 2)
            self.assertEqual(trace["manifest_version"], 5)
            self.assertTrue(trace["handoff_manifest_uri"].endswith("/v2_handoff_manifest.json"))
            self.assertEqual(trace["asset_prompt_count"], 7)
            self.assertEqual(trace["shot_prompt_count"], 9)
            self.assertEqual(trace["prompt_quality_status"], "ready")
            self.assertEqual(trace["prompt_quality"]["status"], "ready")
            self.assertEqual(trace["prompt_quality"]["clean_asset_prompt_count"], 1)
            self.assertEqual(trace["prompt_quality"]["director_prompt_count"], 1)
            self.assertEqual(trace["image_asset_count"], 1)
            self.assertEqual(trace["image_production_evidence"]["evidence_level"], "model_reviewed")
            self.assertTrue(trace["image_production_evidence"]["supports_real_quality_claim"])
            self.assertEqual(trace["image_production_evidence"]["providers"], ["doubao"])
            self.assertEqual(trace["image_production_evidence"]["models"], ["seedream"])
            self.assertEqual(trace["image_production_evidence"]["review_passed_image_count"], 1)
            self.assertEqual(trace["image_production_evidence"]["usable_image_count"], 1)
            self.assertEqual(trace["image_production_evidence"]["waste_or_rework_image_count"], 0)
            self.assertEqual(trace["image_production_evidence"]["waste_or_rework_rate"], 0)
            self.assertEqual(trace["image_production_evidence"]["failed_image_ids"], [])
            self.assertEqual(trace["image_production_evidence"]["by_asset_type"]["character"]["total"], 1)
            self.assertEqual(trace["image_production_evidence"]["by_asset_type"]["character"]["passed"], 1)
            self.assertEqual(trace["image_production_evidence"]["by_asset_type"]["character"]["waste_or_rework"], 0)
            self.assertEqual(trace["image_assets"][0]["production_role"], "clean_character_identity_three_view")
            self.assertTrue(trace["image_assets"][0]["clean_background_required"])
            self.assertIn("不负责讲述剧情", "；".join(trace["image_assets"][0]["usage_contract"]))
            self.assertIn("人物资产用于后续镜头身份一致性参考", trace["image_assets"][0]["reference_policy"])
            self.assertEqual(trace["image_assets"][0]["attempts"], 2)
            self.assertEqual(trace["image_assets"][0]["review_status"], "pass")
            self.assertEqual(trace["image_assets"][0]["review_recovery_action"], "regenerate_images")
            self.assertEqual(trace["image_assets"][0]["review_recovery_focus"], "images")
            self.assertIn("人物身份", trace["image_assets"][0]["review_recovery_reason"])
            self.assertEqual(trace["image_assets"][0]["review_rework_label"], "保留提示词重新生图")
            self.assertIn("重新生成这张图", "；".join(trace["image_assets"][0]["review_operator_steps"]))
            self.assertEqual(trace["shots"][0]["shot_id"], "shot_001")
            self.assertEqual(trace["shots"][0]["first_frame_reference_image"]["file"], "char_001_three_view.png")
            self.assertEqual(trace["shots"][0]["reference_asset_chain"][0]["name"], "林昭")
            self.assertEqual(trace["quality_benchmark"]["package_quality_score"], 96)
            self.assertTrue(trace["quality_benchmark"]["production_quality_verified"])
            self.assertEqual(trace["claim_level"], "real_quality_verified")
            self.assertEqual(trace["downstream_handoff_decision"]["status"], "ready_for_downstream")
            self.assertTrue(trace["downstream_handoff_decision"]["handoff_allowed"])
            self.assertEqual(trace["downstream_handoff_decision"]["missing_before_handoff"], [])
            self.assertIn("handoff manifest", trace["downstream_handoff_decision"]["operator_next_step"])
            self.assertEqual(
                [item["id"] for item in trace["claim_upgrade_checklist"]],
                ["keep_evidence_bundle", "repeat_after_major_edit"],
            )
            self.assertIn("首帧参考林昭", trace["shots"][0]["video_prompt_block"])
            self.assertEqual(trace["visual_review"]["record_count"], 7)
            self.assertEqual(
                [item["stage"] for item in trace["production_lineage"]],
                ["story_contract", "delivery"],
            )
            self.assertEqual(trace["production_lineage"][0]["department"], "内阁 / 中书省")
            self.assertTrue(trace["delivery_audit"]["handoff_ready"])
            summary = row["delivery_summary"]
            self.assertEqual(summary["status"], "ready")
            self.assertEqual(summary["asset_count"], 7)
            self.assertEqual(summary["shot_count"], 9)
            self.assertEqual(summary["prompt_count"], 16)
            self.assertEqual(summary["prompt_quality_status"], "ready")
            self.assertEqual(summary["prompt_quality_issue_count"], 0)
            self.assertEqual(summary["visual_review_status"], "passed")
            self.assertEqual(summary["package_quality_score"], 96)
            self.assertEqual(summary["package_quality_claim"], "production_quality_verified")
            self.assertTrue(summary["production_quality_verified"])
            self.assertEqual(
                summary["downloadable_files"],
                ["完整归档包", "Word 制片画布", "引用清单", "提示词包", "图片资产", "追溯记录"],
            )
            self.assertEqual(summary["missing_items"], [])
            self.assertIn("可以交给下游", summary["next_action"])
            prompt_response = self.client.get(prompt_artifact["download_uri"])
            self.assertEqual(prompt_response.status_code, 200)
            self.assertEqual(prompt_response.json()["prompts"][0]["object_id"], "character_001")
            trace_response = self.client.get(row["comic_v2_trace_uri"])
            self.assertEqual(trace_response.status_code, 200)
            self.assertEqual(trace_response.json()["story_id"], "story_123")
            self.assertEqual(trace_response.json()["claim_level"], "real_quality_verified")
            self.assertEqual(trace_response.json()["downstream_handoff_decision"]["status"], "ready_for_downstream")
            self.assertEqual(trace_response.json()["prompt_quality_status"], "ready")
            self.assertEqual(trace_response.json()["shots"][0]["shot_id"], "shot_001")
        finally:
            conn = sqlite3.connect("user_data/config.db")
            conn.execute("DELETE FROM task_history WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_runs WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_events WHERE task_id=?", (task_id,))
            conn.commit()
            conn.close()

    def test_history_suggests_recovery_actions_for_incomplete_comic_v2_delivery(self):
        task_id = f"hist_v2_missing_{str(uuid.uuid4())[:8]}"
        workspace_id = f"ws_hist_v2_missing_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="V2 Missing Delivery",
            brief="history recovery",
        )
        config_manager.save_task_record(
            task_id,
            "build incomplete V2 delivery",
            "",
            "completed",
            {"final_report": "V2 delivery still needs repair"},
        )
        config_manager.create_task_run(task_id, "build incomplete V2 delivery", "")
        config_manager.append_task_event(
            task_id=task_id,
            event_type="comic_v2_delivery_failed",
            status="failed",
            summary="V2 delivery missing files",
            payload={"office_id": "comic_production", "workspace_id": workspace_id},
        )
        config_manager.update_task_run(
            task_id,
            "completed",
            current_phase="document_generation",
            result={"final_report": "V2 delivery still needs repair"},
            completed=True,
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_word_meta",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="comic_v2_word_canvas",
            title="V2 Word Canvas Metadata Only",
            content="missing uri",
            metadata={
                "office_id": "comic_production",
                "story_id": "story_missing",
                "story_version": 2,
                "style_id": "style_missing",
                "style_version": 1,
                "manifest_version": 4,
                "audit": {"asset_count": 6, "shot_count": 0, "handoff_ready": False},
            },
            created_by="libu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_prompt_pkg",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="comic_v2_prompt_package",
            title="V2 Prompt Package",
            content=json.dumps({
                "prompts": [
                    {
                        "object_id": "character_001",
                        "image_kind": "three_view",
                        "generator_prompt": "林昭在战场里挥剑，不要文字。",
                        "negative_prompt": ["不要变脸"],
                    }
                ],
                "shots": [
                    {
                        "shot_id": "shot_001",
                        "generator_prompt": "林昭冲出去。",
                        "negative_prompt": ["不要变脸"],
                    }
                ],
            }, ensure_ascii=False),
            metadata={
                "office_id": "comic_production",
                "manifest_version": 4,
                "asset_prompt_count": 6,
                "shot_prompt_count": 8,
            },
            created_by="gongbu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_visual_review",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="comic_v2_visual_review",
            title="V2 Visual Review",
            content="{}",
            metadata={
                "office_id": "comic_production",
                "production_ready": False,
                "record_count": 6,
                "failure_count": 2,
            },
            created_by="xingbu",
        )

        try:
            response = self.client.get("/api/tasks/history?limit=20")
            self.assertEqual(response.status_code, 200)
            row = next(item for item in response.json()["history"] if item["task_id"] == task_id)
            summary = row["delivery_summary"]
            self.assertEqual(summary["status"], "needs_review")
            self.assertIn("Word 制片画布", summary["missing_items"])
            self.assertIn("引用清单", summary["missing_items"])
            self.assertIn("提示词质量门禁", summary["missing_items"])
            self.assertIn("视觉质检问题", summary["missing_items"])
            self.assertEqual(summary["prompt_quality_status"], "needs_review")
            self.assertGreater(summary["prompt_quality_issue_count"], 0)
            actions = summary["recovery_actions"]
            action_by_focus = {action["focus"]: action for action in actions}
            delivery_action = action_by_focus["delivery"]
            self.assertEqual(delivery_action["label"], "重新生成 Word 制片画布")
            self.assertEqual(delivery_action["method"], "POST")
            self.assertEqual(delivery_action["path"], f"/api/workspaces/{workspace_id}/comic/v2/delivery/build")
            self.assertEqual(delivery_action["workspace_id"], workspace_id)
            self.assertEqual(delivery_action["office_id"], "comic_production")
            self.assertEqual(delivery_action["expected_stage"], "document_generation")
            self.assertIn("图片生产记录", delivery_action["preserves"])
            self.assertIn("当前交付物", delivery_action["clears"])
            self.assertGreaterEqual(len(delivery_action["operator_steps"]), 3)
            self.assertIn("Word", delivery_action["description"])

            image_action = action_by_focus["images"]
            self.assertEqual(image_action["label"], "重新生成并质检基础资产图")
            self.assertEqual(image_action["path"], f"/api/workspaces/{workspace_id}/comic/v2/images/generate")
            self.assertEqual(image_action["expected_stage"], "image_generation")
            self.assertIn("提示词包", image_action["preserves"])
            self.assertIn("图片生产记录", image_action["clears"])
            self.assertIn("重新生成基础资产图", " ".join(image_action["operator_steps"]))

            prompt_action = action_by_focus["prompts"]
            self.assertEqual(prompt_action["label"], "重新生成提示词")
            self.assertEqual(prompt_action["path"], f"/api/workspaces/{workspace_id}/comic/v2/prompts/plan")
            self.assertEqual(prompt_action["expected_stage"], "prompt_planning")
            self.assertIn("已批准资产拆解包", prompt_action["preserves"])
            self.assertIn("提示词包", prompt_action["clears"])
            self.assertIn("视觉母版", prompt_action["description"])
        finally:
            conn = sqlite3.connect("user_data/config.db")
            conn.execute("DELETE FROM task_history WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_runs WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_events WHERE task_id=?", (task_id,))
            conn.commit()
            conn.close()

    def test_delivery_download_errors_are_actionable(self):
        workspace_id = f"ws_delivery_err_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Missing delivery",
            brief="Delivery should explain missing files.",
        )

        response = self.client.get(f"/api/workspaces/{workspace_id}/files/delivery/missing.docx")

        self.assertEqual(response.status_code, 404)
        detail = response.json()["detail"]
        self.assertEqual(detail["office_id"], "comic_production")
        self.assertEqual(detail["stage"], "delivery_download")
        self.assertTrue(detail["reason"])
        self.assertTrue(detail["impact"])
        self.assertTrue(detail["next_action"])

    def test_generated_image_download_errors_are_actionable(self):
        workspace_id = f"ws_generated_err_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Missing generated image",
            brief="Generated image should explain missing files.",
        )

        response = self.client.get(f"/api/workspaces/{workspace_id}/files/generated/missing.png")

        self.assertEqual(response.status_code, 404)
        detail = response.json()["detail"]
        self.assertEqual(detail["office_id"], "comic_production")
        self.assertEqual(detail["stage"], "generated_file_download")
        self.assertTrue(detail["reason"])
        self.assertTrue(detail["impact"])
        self.assertTrue(detail["next_action"])

    def test_comic_production_start_errors_are_actionable(self):
        missing_workspace_id = f"ws_missing_{str(uuid.uuid4())[:8]}"

        no_workspace_selected = self.client.post("/api/tasks", json={
            "user_request": "start production",
            "office_id": "comic_production",
        })
        self.assertEqual(no_workspace_selected.status_code, 400)
        no_workspace_detail = no_workspace_selected.json()["detail"]
        self.assertEqual(no_workspace_detail["office_id"], "comic_production")
        self.assertEqual(no_workspace_detail["stage"], "production_start")
        self.assertTrue(no_workspace_detail["reason"])
        self.assertTrue(no_workspace_detail["impact"])
        self.assertTrue(no_workspace_detail["next_action"])

        missing_workspace = self.client.post("/api/tasks", json={
            "user_request": "start production",
            "office_id": "comic_production",
            "workspace_id": missing_workspace_id,
        })
        self.assertEqual(missing_workspace.status_code, 404)
        missing_workspace_detail = missing_workspace.json()["detail"]
        self.assertEqual(missing_workspace_detail["office_id"], "comic_production")
        self.assertEqual(missing_workspace_detail["stage"], "production_start")
        self.assertTrue(missing_workspace_detail["reason"])
        self.assertTrue(missing_workspace_detail["impact"])
        self.assertTrue(missing_workspace_detail["next_action"])

        workspace_id = f"ws_start_err_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="No confirmed story",
            brief="Production should require a confirmed story.",
        )
        no_script = self.client.post("/api/tasks", json={
            "user_request": "start production",
            "office_id": "comic_production",
            "workspace_id": workspace_id,
        })
        self.assertEqual(no_script.status_code, 400)
        no_script_detail = no_script.json()["detail"]
        self.assertEqual(no_script_detail["office_id"], "comic_production")
        self.assertEqual(no_script_detail["stage"], "production_start")
        self.assertTrue(no_script_detail["reason"])
        self.assertTrue(no_script_detail["impact"])
        self.assertTrue(no_script_detail["next_action"])

    def test_comic_image_regeneration_errors_are_actionable(self):
        missing = self.client.post(
            "/api/artifacts/art_missing_regenerate/regenerate-comic-image",
            json={"instruction": "make it cleaner"},
        )
        self.assertEqual(missing.status_code, 404)
        missing_detail = missing.json()["detail"]
        self.assertEqual(missing_detail["office_id"], "comic_production")
        self.assertEqual(missing_detail["stage"], "image_regeneration")
        self.assertTrue(missing_detail["reason"])
        self.assertTrue(missing_detail["impact"])
        self.assertTrue(missing_detail["next_action"])

        workspace_id = f"ws_regen_err_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Regeneration errors",
            brief="Regeneration should explain invalid artifacts.",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_report",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="report",
            title="Not an image",
            content="plain report",
            metadata={"office_id": "comic_production"},
            created_by="libu",
        )
        wrong_type = self.client.post(
            f"/api/artifacts/art_{workspace_id}_report/regenerate-comic-image",
            json={"instruction": "make it cleaner"},
        )
        self.assertEqual(wrong_type.status_code, 400)
        wrong_detail = wrong_type.json()["detail"]
        self.assertEqual(wrong_detail["office_id"], "comic_production")
        self.assertEqual(wrong_detail["stage"], "image_regeneration")
        self.assertTrue(wrong_detail["reason"])
        self.assertTrue(wrong_detail["impact"])
        self.assertTrue(wrong_detail["next_action"])


    def test_comic_image_specs_skip_shots_and_only_generate_base_assets(self):
        result = {
            "comic_package": {
                "script_binding": {"script_hash": "abc", "script_version": 1, "confirmed": True},
                "characters": [{"id": "char_01", "image_prompt": "人物站在山路上讲故事"}],
                "props": [{
                    "id": "prop_01",
                    "asset_specs": [
                        {"kind": "prop_turnaround", "label": "道具多角度", "prompt": "人物手持药瓶站在街道剧情现场"}
                    ],
                }],
                "scenes": [{
                    "id": "scene_01",
                    "image_prompt": "场景设定",
                    "asset_specs": [
                        {"kind": "scene_wide_establishing", "label": "场景广角建立图", "prompt": "广角空间参考"},
                        {"kind": "scene_top_down_layout", "label": "场景俯视布局图", "prompt": "俯视空间参考"},
                    ],
                }],
                "shots": [
                    {"id": f"shot_{index:03d}", "image_prompt": f"第{index}镜真实剧情画面", "binding": {}}
                    for index in range(1, 7)
                ],
            }
        }

        specs = _comic_image_specs(result, limit=12)
        storyboard_ids = [item["source_id"] for item in specs if item["kind"] == "storyboard"]
        spec_kinds = {item["kind"] for item in specs}

        self.assertEqual(storyboard_ids, [])
        self.assertIn("character", spec_kinds)
        self.assertIn("prop_turnaround", spec_kinds)
        self.assertIn("scene", spec_kinds)
        self.assertIn("scene_wide_establishing", spec_kinds)
        self.assertIn("scene_top_down_layout", spec_kinds)
        character_prompt = next(item["prompt"] for item in specs if item["kind"] == "character")
        prop_prompt = next(item["prompt"] for item in specs if item["kind"] == "prop_turnaround")
        self.assertIn("纯白或近白色干净背景", character_prompt)
        self.assertIn("禁止场景背景", character_prompt)
        self.assertIn("只生成单独角色参考", character_prompt)
        self.assertIn("纯白或近白色干净背景", prop_prompt)
        self.assertIn("禁止人物手持", prop_prompt)
        self.assertIn("只生成单独道具参考", prop_prompt)

    @patch("src.comic_office.workflow._model_config_usable", return_value=True)
    @patch("src.comic_office.workflow._cabinet_story_writer_llm", return_value={"assistant_message": "Mock LLM Message", "story": {}})
    @patch("src.comic_office.workflow.advance_comic_cabinet_session")
    @patch("src.web.app.config_manager.get_model_config")
    def test_comic_cabinet_turn_prefers_llm_role_reviews_when_models_are_available(self, mock_get_config, mock_advance, mock_writer, mock_usable):
        def fake_get_model_config(agent, office_id=""):
            return ModelConfig(provider="ollama", model=f"fake-{agent}")
        mock_get_config.side_effect = fake_get_model_config
        mock_advance.return_value = {
            "session": {"messages": [{"role": "assistant"}], "story_state": {"ready_to_produce": False}},
            "creative_brief": {},
            "script_preview": {},
            "assistant_message": "old",
            "cabinet_roles": [],
            "preview": "old"
        }

        async def fake_chat(self, messages, tools=None, tool_choice=None, response_format=None):
            return LLMResponse(
                content='{"assistant_message": "Mock LLM Message", "story": {}}',
                model="fake/provider",
                tokens_used=10,
            )

        with patch("src.web.app.config_manager.get_model_config", side_effect=fake_get_model_config):
            with patch.object(LiteLLMProvider, "chat", fake_chat):
                response = self.client.post("/api/comic/cabinet/turn", json={
                    "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
                    "genre": "suspense",
                    "length": "3 episodes",
                    "platform": "Douyin",
                    "visual_style": "dark suspense comic",
                    "extra": "第一集要有强钩子",
                })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)
        self.assertTrue(body["session"]["llm_cabinet"])
        self.assertEqual(body["assistant_message"], "Mock LLM Message")

    def test_confirm_script_endpoint_persists_confirmed_script_and_task_gate_requires_it(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
            "user_message": "主角是女侦探，反派在误导她，最后她发现自己名字也在信里，结尾要留悬念。",
            "session": body["session"],
        })
        self.assertEqual(response.status_code, 200)
        session = response.json()["session"]

        blocked = self.client.post("/api/tasks", json={
            "user_request": "Idea: 雨夜里失忆侦探捡到一封会改写身份的信",
            "office_id": "comic",
            "workspace_id": workspace_id,
        })
        self.assertEqual(blocked.status_code, 400)

        confirmed = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "session": session,
            "confirmation_notes": "确认这版，第一集钩子可以再狠一点。",
        })
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["status"], "confirmed")
        self.assertTrue(confirmed.json()["confirmed_script"]["script_hash"])
        self.assertEqual(confirmed.json()["confirmed_script"]["script_version"], 1)

        class DummyTask:
            def add_done_callback(self, callback):
                return None

        def fake_create_task(coro):
            coro.close()
            return DummyTask()

        with patch("src.web.app._schedule_background_task", side_effect=fake_create_task):
            started = self.client.post("/api/tasks", json={
                "user_request": "Idea: 雨夜里失忆侦探捡到一封会改写身份的信",
                "office_id": "comic",
                "workspace_id": workspace_id,
            })
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["workspace_id"], workspace_id)

    def test_confirm_and_start_comic_endpoint_freezes_script_and_enqueues_task(self):
        workspace_id = f"ws_test_{str(uuid.uuid4())[:8]}"
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic",
            title="雨夜里失忆侦探捡到一封会改写身份的信",
            brief="一键确认并开始生产测试",
        )
        self.created_workspaces.append(workspace_id)
        session = {
            "creative_brief": {
                "core_idea": "雨夜里失忆侦探捡到一封会改写身份的信",
                "genre": "suspense",
                "length": "3 episodes",
                "platform": "Douyin",
                "visual_style": "dark suspense comic",
                "story_promise": "主角追查身份被改写的秘密",
                "main_conflict": "主角被对手误导，必须在身份被彻底改写前找到真相",
            },
            "script_preview": {
                "title": "雨夜信",
                "logline": "失忆女侦探追查一封会改写身份的信，最后发现自己的名字也在信里。",
                "why_it_happens": "对手为了隐藏真相，利用信件误导主角。",
                "how_it_happens": "主角不断追查线索，与对手冲突升级。",
                "protagonist_arc": "主角从被动怀疑自己，到主动反击对手，结尾留下悬念。",
                "episode_outline": [
                    {"episode": 1, "title": "雨夜来信", "cause": "主角捡到信", "action": "主角追查", "turn": "发现自己被误导", "hook": "最后她发现自己的名字也在信里"}
                ],
                "key_turns": ["最后她发现自己的名字也在信里"],
                "story_draft": "雨夜里，失忆女侦探捡到一封信。她追查对手，却发现自己的名字也在信里。",
            },
            "user_notes": ["主角是女侦探，对手在误导她，最后她发现自己的名字也在信里，结尾要留悬念。"],
            "cabinet_roles": [],
        }

        class DummyTask:
            def add_done_callback(self, callback):
                return None

        def fake_create_task(coro):
            coro.close()
            return DummyTask()

        with patch("src.web.app._schedule_background_task", side_effect=fake_create_task):
            started = self.client.post("/api/comic/confirm-and-start", json={
                "workspace_id": workspace_id,
                "session": session,
                "confirmation_notes": "Confirm this story and start production.",
                "user_request": "This client text should be replaced by the confirmed server script.",
            })

        self.assertEqual(started.status_code, 200)
        body = started.json()
        self.assertEqual(body["status"], "started")
        self.assertEqual(body["workspace_id"], workspace_id)
        self.assertTrue(body["task_id"])
        self.assertTrue(body["confirmed_script"]["script_hash"])
        self.assertTrue(body["artifact_id"].startswith(f"art_{workspace_id}_confirmed_script"))

        artifacts = config_manager.list_artifacts(workspace_id=workspace_id)
        self.assertTrue(any(a["artifact_type"] == "confirmed_script" for a in artifacts))
        run = config_manager.get_task_run(body["task_id"])
        self.assertIn(body["confirmed_script"]["script_hash"], run["user_request"])
        self.assertNotIn("This client text should be replaced", run["user_request"])

    def test_confirm_script_uses_saved_workspace_session_instead_of_client_session(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
            "user_message": "主角是女侦探，对手在误导她，最后她发现自己的名字也在信里，结尾要留悬念。",
            "session": body["session"],
        })
        self.assertEqual(response.status_code, 200)

        tampered_session = {
            "creative_brief": {
                "core_idea": "客户端伪造项目",
                "genre": "suspense",
                "length": "3 episodes",
                "platform": "Douyin",
                "visual_style": "wrong style",
                "story_promise": "客户端伪造承诺",
                "main_conflict": "主角和对手的客户端伪造冲突",
            },
            "script_preview": {
                "title": "客户端伪造标题",
                "logline": "客户端伪造剧本",
                "why_it_happens": "主角被客户端伪造事件卷入",
                "how_it_happens": "对手推动客户端伪造",
                "protagonist_arc": "主角最后发现客户端伪造",
                "episode_outline": [{"episode": 1, "title": "客户端伪造", "cause": "客户端伪造", "action": "客户端伪造", "turn": "客户端伪造", "hook": "最后客户端伪造"}],
                "key_turns": ["最后客户端伪造"],
            },
            "user_notes": ["主角、对手、最后都被客户端伪造"],
            "cabinet_roles": [],
        }

        confirmed = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "session": tampered_session,
            "confirmation_notes": "确认真实后端会话",
        })

        self.assertEqual(confirmed.status_code, 200)
        confirmed_script = confirmed.json()["confirmed_script"]
        self.assertNotIn("客户端伪造", confirmed_script["title"])
        self.assertNotIn("客户端伪造", confirmed_script["logline"])

    def test_comic_task_replaces_client_confirmed_script_with_server_confirmed_script(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
            "user_message": "主角是女侦探，对手在误导她，最后她发现自己的名字也在信里，结尾要留悬念。",
            "session": body["session"],
        })
        self.assertEqual(response.status_code, 200)
        session = response.json()["session"]

        confirmed = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "session": session,
            "confirmation_notes": "确认真实版本",
        })
        self.assertEqual(confirmed.status_code, 200)
        server_hash = confirmed.json()["confirmed_script"]["script_hash"]

        class DummyTask:
            def add_done_callback(self, callback):
                return None

        def fake_create_task(coro):
            coro.close()
            return DummyTask()

        with patch("src.web.app._schedule_background_task", side_effect=fake_create_task):
            started = self.client.post("/api/tasks", json={
                "user_request": (
                    "Idea: 外部调用\n"
                    "Confirmed script:\nMALICIOUS SCRIPT SHOULD NOT SURVIVE\n"
                    "Script notes: Asset revision notes: 道具只有药箱、求救符、采购清单。"
                ),
                "office_id": "comic",
                "workspace_id": workspace_id,
            })

        self.assertEqual(started.status_code, 200)
        run = config_manager.get_task_run(started.json()["task_id"])
        self.assertIn(server_hash, run["user_request"])
        self.assertNotIn("MALICIOUS SCRIPT SHOULD NOT SURVIVE", run["user_request"])
        self.assertIn("Asset revision notes: 道具只有药箱、求救符、采购清单。", run["user_request"])

    def test_reconfirming_script_invalidates_assets_bound_to_old_script_hash(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
            "user_message": "主角是女侦探，反派在误导她，最后她发现自己名字也在信里，结尾要留悬念。",
            "session": body["session"],
        })
        self.assertEqual(response.status_code, 200)
        session = response.json()["session"]

        confirmed_v1 = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "session": session,
            "confirmation_notes": "先确认第一版。",
        })
        self.assertEqual(confirmed_v1.status_code, 200)
        old_hash = confirmed_v1.json()["confirmed_script"]["script_hash"]

        config_manager.create_artifact(
            artifact_id="art_old_character_sheet",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="character_sheet",
            title="旧版人物设定",
            content="旧脚本版本下的人物设定。",
            metadata={
                "office_id": "comic",
                "script_hash": old_hash,
                "script_version": 1,
                "script_confirmed": True,
            },
            created_by="gongbu",
        )

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
            "user_message": "补充新设定：幕后操控者其实是她曾经的搭档，第一集必须出现怀表这个新道具。",
            "session": session,
        })
        self.assertEqual(response.status_code, 200)
        updated_session = response.json()["session"]

        confirmed_v2 = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "session": updated_session,
            "confirmation_notes": "确认第二版，加入怀表设定。",
        })
        self.assertEqual(confirmed_v2.status_code, 200)
        new_hash = confirmed_v2.json()["confirmed_script"]["script_hash"]
        self.assertNotEqual(old_hash, new_hash)
        self.assertGreaterEqual(confirmed_v2.json()["invalidated_count"], 1)

        old_artifact = config_manager.get_artifact("art_old_character_sheet")
        self.assertTrue(old_artifact["metadata"]["invalidated"])
        self.assertEqual(old_artifact["metadata"]["invalidated_reason"], "confirmed_script_changed")
        self.assertEqual(old_artifact["metadata"]["current_script_hash"], new_hash)


if __name__ == "__main__":
    unittest.main()
