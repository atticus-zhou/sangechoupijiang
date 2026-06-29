import sqlite3
import shutil
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.llm.providers import LLMResponse, LiteLLMProvider
from src.browser_capture import BrowserCaptureError
from src.web.app import app, config_manager


class WebResearchApiTests(unittest.TestCase):
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
        conn.commit()
        conn.close()
        for workspace_id in self.created_workspaces:
            shutil.rmtree(Path("output") / "workspaces" / workspace_id, ignore_errors=True)

    def test_workspace_export_contains_artifacts(self):
        response = self.client.post("/api/workspaces", json={
            "title": "导出测试",
            "brief": "验证研究办公室导出",
            "office_id": "research",
        })
        self.assertEqual(response.status_code, 200)
        workspace_id = response.json()["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post(f"/api/workspaces/{workspace_id}/artifacts", json={
            "artifact_type": "report",
            "title": "测试报告",
            "content": "报告正文",
        })
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/api/workspaces/{workspace_id}/export")
        self.assertEqual(response.status_code, 200)

        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            names = zf.namelist()

        self.assertIn("workspace.json", names)
        self.assertTrue(any(name.endswith(".md") for name in names))

    def test_screenshot_evidence_can_be_extracted(self):
        response = self.client.post("/api/workspaces", json={
            "title": "截图识别测试",
            "brief": "验证截图证据识别链路",
            "office_id": "research",
        })
        self.assertEqual(response.status_code, 200)
        workspace_id = response.json()["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post(
            f"/api/workspaces/{workspace_id}/evidence",
            files={"file": ("sample.png", b"\x89PNG\r\n\x1a\n" + b"0" * 80, "image/png")},
            data={"note": "榜单截图"},
        )
        self.assertEqual(response.status_code, 200)
        evidence_id = response.json()["artifact_id"]

        async def fake_vision(self, text, images=None, system="", tools=None):
            return LLMResponse(
                content='{"source_hint":"sample","detected_tables":[],"warnings":[]}',
                model="fake-vision",
                tokens_used=12,
            )

        with patch.object(LiteLLMProvider, "chat_with_vision", fake_vision):
            response = self.client.post(f"/api/artifacts/{evidence_id}/extract", json={"agent_id": "hubu"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        artifacts = self.client.get(f"/api/workspaces/{workspace_id}/artifacts").json()["artifacts"]
        artifact_types = [a["artifact_type"] for a in artifacts]
        self.assertIn("screenshot_extraction", artifact_types)
        self.assertIn("data_table", artifact_types)
        self.assertIn("competitor_table", artifact_types)

    def test_evidence_sync_creates_standard_artifacts_after_upload(self):
        response = self.client.post("/api/workspaces", json={
            "title": "证据整理测试",
            "brief": "验证证据上传后可整理",
            "office_id": "research",
        })
        self.assertEqual(response.status_code, 200)
        workspace_id = response.json()["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post(
            f"/api/workspaces/{workspace_id}/evidence",
            files={"file": ("sample.png", b"\x89PNG\r\n\x1a\n" + b"0" * 80, "image/png")},
            data={"note": "无人机榜单"},
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(f"/api/workspaces/{workspace_id}/evidence/sync", json={})
        self.assertEqual(response.status_code, 200)
        artifact_types = [a["artifact_type"] for a in response.json()["artifacts"]]
        self.assertIn("source_list", artifact_types)
        self.assertIn("screenshot_plan", artifact_types)

    def test_upload_evidence_rejects_unsupported_file_with_actionable_error(self):
        response = self.client.post("/api/workspaces", json={
            "title": "截图错误提示测试",
            "brief": "验证上传错误是否可操作",
            "office_id": "research",
        })
        self.assertEqual(response.status_code, 200)
        workspace_id = response.json()["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post(
            f"/api/workspaces/{workspace_id}/evidence",
            files={"file": ("sample.txt", b"not an image", "text/plain")},
            data={"note": "错误格式"},
        )

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["office_id"], "research")
        self.assertEqual(detail["department"], "户部 / 刑部")
        self.assertIn("截图格式", detail["reason"])
        self.assertIn("证据", detail["impact"])
        self.assertIn("png", detail["next_action"])

    def test_capture_url_browser_error_is_actionable(self):
        response = self.client.post("/api/workspaces", json={
            "title": "自动截图错误提示测试",
            "brief": "验证浏览器错误是否可操作",
            "office_id": "research",
        })
        self.assertEqual(response.status_code, 200)
        workspace_id = response.json()["workspace_id"]
        self.created_workspaces.append(workspace_id)

        with patch("src.web.app.capture_url", side_effect=BrowserCaptureError("浏览器调试端口没有启动成功")):
            response = self.client.post(
                f"/api/workspaces/{workspace_id}/capture-url",
                json={"url": "https://example.com", "title": "example"},
            )

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["office_id"], "research")
        self.assertEqual(detail["department"], "兵部")
        self.assertIn("自动截图失败", detail["reason"])
        self.assertIn("证据", detail["impact"])
        self.assertIn("登录窗口", detail["next_action"])

    def test_capture_feigua_requires_keyword_with_actionable_error(self):
        response = self.client.post("/api/workspaces", json={
            "title": "飞瓜关键词错误提示测试",
            "brief": "验证飞瓜关键词错误是否可操作",
            "office_id": "research",
        })
        self.assertEqual(response.status_code, 200)
        workspace_id = response.json()["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post(
            f"/api/workspaces/{workspace_id}/capture-feigua",
            json={"keyword": ""},
        )

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["office_id"], "research")
        self.assertEqual(detail["department"], "兵部")
        self.assertIn("研究对象", detail["reason"])
        self.assertIn("飞瓜", detail["impact"])
        self.assertIn("关键词", detail["next_action"])

    def test_browser_login_errors_are_actionable(self):
        with patch("src.web.app.open_login_page", side_effect=BrowserCaptureError("浏览器启动失败")):
            response = self.client.post("/api/browser/start-login", json={"url": "https://dy3.feigua.cn/"})

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["office_id"], "research")
        self.assertEqual(detail["department"], "兵部")
        self.assertIn("登录窗口", detail["reason"])
        self.assertIn("飞瓜", detail["impact"])
        self.assertIn("浏览器", detail["next_action"])

    def test_feigua_login_state_errors_are_actionable(self):
        with patch("src.web.app.feigua_login_state", side_effect=BrowserCaptureError("无法连接浏览器")):
            response = self.client.get("/api/browser/feigua-login-state")

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["office_id"], "research")
        self.assertEqual(detail["department"], "兵部")
        self.assertIn("登录状态", detail["reason"])
        self.assertIn("截图", detail["impact"])
        self.assertIn("登录窗口", detail["next_action"])


    def test_extract_evidence_errors_are_actionable(self):
        missing = self.client.post("/api/artifacts/art_missing_extract/extract", json={"agent_id": "hubu"})
        self.assertEqual(missing.status_code, 404)
        missing_detail = missing.json()["detail"]
        self.assertEqual(missing_detail["office_id"], "research")
        self.assertEqual(missing_detail["stage"], "evidence_extraction")
        self.assertTrue(missing_detail["reason"])
        self.assertTrue(missing_detail["impact"])
        self.assertTrue(missing_detail["next_action"])

        response = self.client.post("/api/workspaces", json={
            "title": "Wrong artifact extraction",
            "brief": "Extraction should reject non-screenshot artifacts clearly.",
            "office_id": "research",
        })
        self.assertEqual(response.status_code, 200)
        workspace_id = response.json()["workspace_id"]
        self.created_workspaces.append(workspace_id)
        response = self.client.post(f"/api/workspaces/{workspace_id}/artifacts", json={
            "artifact_type": "report",
            "title": "Not a screenshot",
            "content": "plain report",
        })
        self.assertEqual(response.status_code, 200)
        artifact_id = response.json()["artifact_id"]

        wrong_type = self.client.post(f"/api/artifacts/{artifact_id}/extract", json={"agent_id": "hubu"})
        self.assertEqual(wrong_type.status_code, 400)
        wrong_detail = wrong_type.json()["detail"]
        self.assertEqual(wrong_detail["office_id"], "research")
        self.assertEqual(wrong_detail["stage"], "evidence_extraction")
        self.assertTrue(wrong_detail["reason"])
        self.assertTrue(wrong_detail["impact"])
        self.assertTrue(wrong_detail["next_action"])

    def test_recover_task_artifacts_errors_are_actionable(self):
        missing = self.client.post("/api/tasks/task_missing_for_recovery/recover-artifacts")
        self.assertEqual(missing.status_code, 404)
        missing_detail = missing.json()["detail"]
        self.assertEqual(missing_detail["office_id"], "research")
        self.assertEqual(missing_detail["stage"], "artifact_recovery")
        self.assertTrue(missing_detail["reason"])
        self.assertTrue(missing_detail["impact"])
        self.assertTrue(missing_detail["next_action"])

    def test_missing_workspace_errors_are_actionable(self):
        workspace_id = "ws_missing_common_error"

        for path in (
            f"/api/workspaces/{workspace_id}",
            f"/api/workspaces/{workspace_id}/artifacts",
            f"/api/workspaces/{workspace_id}/tasks",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                detail = response.json()["detail"]
                self.assertEqual(detail["office_id"], "research")
                self.assertEqual(detail["stage"], "workspace_lookup")
                self.assertTrue(detail["reason"])
                self.assertTrue(detail["impact"])
                self.assertTrue(detail["next_action"])

        create_artifact = self.client.post(f"/api/workspaces/{workspace_id}/artifacts", json={
            "artifact_type": "report",
            "title": "Missing workspace artifact",
            "content": "should fail clearly",
        })
        self.assertEqual(create_artifact.status_code, 404)
        detail = create_artifact.json()["detail"]
        self.assertEqual(detail["office_id"], "research")
        self.assertEqual(detail["stage"], "workspace_lookup")
        self.assertTrue(detail["reason"])
        self.assertTrue(detail["impact"])
        self.assertTrue(detail["next_action"])


    def test_research_capture_workspace_errors_are_actionable(self):
        workspace_id = "ws_missing_capture_error"
        cases = (
            ("post", f"/api/workspaces/{workspace_id}/capture-url", {"url": "https://example.com", "title": "example"}),
            ("post", f"/api/workspaces/{workspace_id}/capture-feigua", {"keyword": "民用无人机"}),
            ("post", f"/api/workspaces/{workspace_id}/evidence/sync", {}),
            ("post", f"/api/workspaces/{workspace_id}/evidence/extract-all", {}),
        )
        for method, path, payload in cases:
            with self.subTest(path=path):
                response = self.client.post(path, json=payload)
                self.assertEqual(response.status_code, 404)
                detail = response.json()["detail"]
                self.assertEqual(detail["office_id"], "research")
                self.assertEqual(detail["stage"], "workspace_lookup")
                self.assertTrue(detail["reason"])
                self.assertTrue(detail["impact"])
                self.assertTrue(detail["next_action"])

    def test_config_and_file_lookup_errors_are_actionable(self):
        unknown_agent = self.client.post("/api/config/models/not_a_department/test")
        self.assertEqual(unknown_agent.status_code, 404)
        agent_detail = unknown_agent.json()["detail"]
        self.assertEqual(agent_detail["office_id"], "system")
        self.assertEqual(agent_detail["stage"], "model_test")
        self.assertTrue(agent_detail["reason"])
        self.assertTrue(agent_detail["impact"])
        self.assertTrue(agent_detail["next_action"])

        missing_file = self.client.get("/api/tasks/task_missing_file/download/missing.docx")
        self.assertEqual(missing_file.status_code, 404)
        file_detail = missing_file.json()["detail"]
        self.assertEqual(file_detail["office_id"], "research")
        self.assertEqual(file_detail["stage"], "task_file_download")
        self.assertTrue(file_detail["reason"])
        self.assertTrue(file_detail["impact"])
        self.assertTrue(file_detail["next_action"])

    def test_missing_task_detail_errors_are_actionable(self):
        task_id = "task_missing_detail_error"
        for path in (f"/api/tasks/{task_id}", f"/api/tasks/{task_id}/report"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                detail = response.json()["detail"]
                self.assertEqual(detail["office_id"], "research")
                self.assertEqual(detail["stage"], "task_lookup")
                self.assertTrue(detail["reason"])
                self.assertTrue(detail["impact"])
                self.assertTrue(detail["next_action"])

if __name__ == "__main__":
    unittest.main()
