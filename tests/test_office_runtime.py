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
