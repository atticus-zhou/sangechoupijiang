import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from src.config_manager import ConfigManager, config_manager
from src.office_runtime import build_office_runtime_status
from src.web.app import app


class OfficeRuntimeStatusTests(unittest.TestCase):
    def test_runtime_status_summarizes_workspace_artifacts_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)
            manager.create_workspace(
                workspace_id="ws-runtime",
                office_id="comic_production",
                title="Runtime comic",
            )
            manager.create_artifact(
                artifact_id="art-runtime-story",
                workspace_id="ws-runtime",
                task_id="task-runtime",
                artifact_type="story_contract",
                title="故事合同",
                metadata={"office_id": "comic_production"},
                created_by="zhongshu",
            )
            manager.create_artifact(
                artifact_id="art-runtime-prompts",
                workspace_id="ws-runtime",
                task_id="task-runtime",
                artifact_type="prompt_package",
                title="提示词包",
                uri="/api/workspaces/ws-runtime/files/delivery/prompt_package.json",
                metadata={"office_id": "comic_production"},
                created_by="libu",
            )
            manager.create_task_run("task-runtime", "produce package", "comic_production")
            manager.update_task_run(
                "task-runtime",
                "failed",
                current_phase="image_generation",
                error="image model rejected the prompt",
                completed=True,
            )
            manager.append_task_event(
                "task-runtime",
                "comic_v2_images_failed",
                "failed",
                "基础资产图生成失败",
                {
                    "workspace_id": "ws-runtime",
                    "office_id": "comic_production",
                    "stage": "image_generation",
                    "department": "工部 / 刑部",
                    "next_action": "修复生图或视觉模型后重新生成基础资产图。",
                },
            )

            status = build_office_runtime_status(manager, "ws-runtime")

        self.assertEqual(status["workspace_id"], "ws-runtime")
        self.assertEqual(status["office_id"], "comic_production")
        self.assertEqual(status["current_stage"]["id"], "image_generation")
        self.assertEqual(status["current_stage"]["status"], "failed")
        self.assertTrue(status["active_task"]["recovery_plan"]["recoverable"])
        self.assertEqual(
            status["active_task"]["recovery_plan"]["retry_action"]["path"],
            "/api/workspaces/ws-runtime/comic/v2/images/generate",
        )
        self.assertIn("story_contract", status["artifact_progress"]["present"])
        self.assertIn("word_canvas", status["artifact_progress"]["missing"])
        self.assertEqual(
            status["downloadable_artifacts"][0]["uri"],
            "/api/workspaces/ws-runtime/files/delivery/prompt_package.json",
        )
        self.assertEqual(status["downloadable_artifacts"][0]["title"], "提示词包")
        self.assertTrue(any(item["id"] == "asset_review" for item in status["human_checkpoints"]))
        self.assertTrue(any(item["stage"] == "document_generation" for item in status["recovery_actions"]))
        quality_action = next(item for item in status["recovery_actions"] if item["stage"] == "quality_review")
        self.assertIn("prompt_package", quality_action["preserves"])
        self.assertIn("word_canvas", quality_action["clears"])

    def test_runtime_status_explains_comic_delivery_acceptance_without_overclaiming(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)
            workspace_id = "ws-acceptance"
            manager.create_workspace(
                workspace_id=workspace_id,
                office_id="comic_production",
                title="Acceptance comic",
            )
            benchmark = {
                "package_quality_ready": True,
                "production_quality_verified": False,
                "package_quality_score": 86,
                "visual_evidence_level": "fixture_only",
                "prompt_quality_summary": {
                    "status": "ready",
                    "issue_count": 0,
                    "asset_prompt_count": 7,
                    "shot_prompt_count": 3,
                },
                "image_quality_summary": {
                    "total_images": 7,
                    "usable_images": 7,
                    "waste_or_rework_images": 0,
                },
            }
            manager.create_artifact(
                artifact_id="art-acceptance-word",
                workspace_id=workspace_id,
                task_id="task-acceptance",
                artifact_type="comic_v2_word_canvas",
                title="Word 制片画布",
                uri=f"/api/workspaces/{workspace_id}/files/delivery/canvas.docx",
                metadata={"office_id": "comic_production", "quality_benchmark": benchmark},
                created_by="libu",
            )
            manager.create_artifact(
                artifact_id="art-acceptance-manifest",
                workspace_id=workspace_id,
                task_id="task-acceptance",
                artifact_type="comic_v2_handoff_manifest",
                title="V2 制片引用清单",
                uri=f"/api/workspaces/{workspace_id}/files/delivery/handoff_manifest.json",
                metadata={"office_id": "comic_production", "quality_benchmark": benchmark},
                created_by="libu",
            )

            status = build_office_runtime_status(manager, workspace_id)

        acceptance = status["delivery_acceptance"]
        self.assertEqual(acceptance["status"], "structure_ready_needs_real_quality")
        self.assertFalse(acceptance["can_claim_real_quality"])
        self.assertFalse(acceptance["can_handoff_to_downstream"])
        self.assertIn("暂不能宣称真实画质已验证", acceptance["summary"])
        self.assertIn("刑部：缺少真实模型视觉复核证据", " ".join(acceptance["missing_evidence"]))
        self.assertEqual(acceptance["downloads"]["word_canvas_uri"], f"/api/workspaces/{workspace_id}/files/delivery/canvas.docx")
        self.assertEqual(acceptance["downloads"]["handoff_manifest_uri"], f"/api/workspaces/{workspace_id}/files/delivery/handoff_manifest.json")
        self.assertEqual(
            [item["id"] for item in acceptance["acceptance_items"]],
            [
                "word_canvas",
                "handoff_manifest",
                "prompt_quality",
                "image_quality",
                "package_quality",
                "real_quality_claim",
            ],
        )
        real_claim = next(item for item in acceptance["acceptance_items"] if item["id"] == "real_quality_claim")
        self.assertFalse(real_claim["passed"])

    def test_runtime_status_marks_comic_delivery_ready_only_with_real_quality_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)
            workspace_id = "ws-real-acceptance"
            manager.create_workspace(
                workspace_id=workspace_id,
                office_id="comic_production",
                title="Real acceptance comic",
            )
            benchmark = {
                "package_quality_ready": True,
                "production_quality_verified": True,
                "package_quality_score": 95,
                "visual_evidence_level": "model_reviewed",
                "prompt_quality_summary": {"status": "ready", "issue_count": 0},
                "image_quality_summary": {
                    "total_images": 8,
                    "usable_images": 8,
                    "waste_or_rework_images": 0,
                },
            }
            manager.create_artifact(
                artifact_id="art-real-acceptance-word",
                workspace_id=workspace_id,
                task_id="task-real-acceptance",
                artifact_type="comic_v2_word_canvas",
                title="Word 制片画布",
                uri=f"/api/workspaces/{workspace_id}/files/delivery/canvas.docx",
                metadata={"office_id": "comic_production", "quality_benchmark": benchmark},
                created_by="libu",
            )
            manager.create_artifact(
                artifact_id="art-real-acceptance-manifest",
                workspace_id=workspace_id,
                task_id="task-real-acceptance",
                artifact_type="comic_v2_handoff_manifest",
                title="V2 制片引用清单",
                uri=f"/api/workspaces/{workspace_id}/files/delivery/handoff_manifest.json",
                metadata={"office_id": "comic_production", "quality_benchmark": benchmark},
                created_by="libu",
            )

            status = build_office_runtime_status(manager, workspace_id)

        acceptance = status["delivery_acceptance"]
        self.assertEqual(acceptance["status"], "ready_for_downstream")
        self.assertTrue(acceptance["can_handoff_to_downstream"])
        self.assertTrue(acceptance["can_claim_real_quality"])
        self.assertEqual(acceptance["missing_evidence"], [])
        self.assertEqual(acceptance["quality_score"], 95)

    def test_runtime_status_counts_v2_artifacts_and_prioritizes_delivery_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)
            workspace_id = "ws-v2-aliases"
            manager.create_workspace(
                workspace_id=workspace_id,
                office_id="comic_production",
                title="V2 aliases comic",
            )
            manager.create_artifact(
                artifact_id="art-v2-contract",
                workspace_id=workspace_id,
                task_id="task-v2-aliases",
                artifact_type="comic_v2_contract",
                title="故事合同与视觉母版",
                metadata={"office_id": "comic_production"},
                created_by="zhongshu",
            )
            manager.create_artifact(
                artifact_id="art-v2-image",
                workspace_id=workspace_id,
                task_id="task-v2-aliases",
                artifact_type="comic_v2_generated_image",
                title="角色三视图",
                uri=f"/api/workspaces/{workspace_id}/files/generated/char.png",
                metadata={"office_id": "comic_production"},
                created_by="gongbu",
            )
            manager.create_artifact(
                artifact_id="art-v2-word",
                workspace_id=workspace_id,
                task_id="task-v2-aliases",
                artifact_type="comic_v2_word_canvas",
                title="Word 制片画布",
                uri=f"/api/workspaces/{workspace_id}/files/delivery/canvas.docx",
                metadata={"office_id": "comic_production"},
                created_by="libu",
            )

            status = build_office_runtime_status(manager, workspace_id)

        progress = status["artifact_progress"]
        self.assertIn("production_brief", progress["present"])
        self.assertIn("production_review", progress["present"])
        self.assertIn("script", progress["present"])
        self.assertIn("generated_image", progress["present"])
        self.assertIn("image_quality_report", progress["present"])
        self.assertIn("production_chain_state", progress["present"])
        self.assertIn("word_canvas", progress["present"])
        self.assertGreater(progress["present_count"], 0)
        self.assertEqual(status["downloadable_artifacts"][0]["artifact_type"], "comic_v2_word_canvas")

    def test_runtime_status_api_exposes_same_workspace_view(self):
        workspace_id = "ws_runtime_api"
        with sqlite3.connect(str(config_manager.db_path)) as conn:
            conn.execute("DELETE FROM artifacts WHERE workspace_id=?", (workspace_id,))
            conn.execute("DELETE FROM workspaces WHERE workspace_id=?", (workspace_id,))
            conn.execute("DELETE FROM task_events WHERE task_id=?", ("task-runtime-api",))
            conn.execute("DELETE FROM task_runs WHERE task_id=?", ("task-runtime-api",))
            conn.commit()

        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Runtime API comic",
        )
        config_manager.create_task_run("task-runtime-api", "build package", "comic_production")
        config_manager.create_artifact(
            artifact_id="art-runtime-api-word",
            workspace_id=workspace_id,
            task_id="task-runtime-api",
            artifact_type="word_canvas",
            title="Word 制片画布",
            uri=f"/api/workspaces/{workspace_id}/files/delivery/canvas.docx",
            metadata={"office_id": "comic_production"},
            created_by="gongbu",
        )
        config_manager.append_task_event(
            "task-runtime-api",
            "task_created",
            "queued",
            "accepted",
            {"workspace_id": workspace_id, "office_id": "comic_production"},
        )

        client = TestClient(app)
        response = client.get(f"/api/workspaces/{workspace_id}/runtime-status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workspace_id"], workspace_id)
        self.assertEqual(payload["office_id"], "comic_production")
        self.assertIn("artifact_progress", payload)
        self.assertEqual(payload["downloadable_artifacts"][0]["artifact_type"], "word_canvas")
        self.assertIn("/files/delivery/canvas.docx", payload["downloadable_artifacts"][0]["uri"])
        self.assertIn("recovery_actions", payload)
        self.assertIn("current_stage", payload)

        with sqlite3.connect(str(config_manager.db_path)) as conn:
            conn.execute("DELETE FROM artifacts WHERE workspace_id=?", (workspace_id,))
            conn.execute("DELETE FROM workspaces WHERE workspace_id=?", (workspace_id,))
            conn.execute("DELETE FROM task_events WHERE task_id=?", ("task-runtime-api",))
            conn.execute("DELETE FROM task_runs WHERE task_id=?", ("task-runtime-api",))
            conn.commit()


if __name__ == "__main__":
    unittest.main()
