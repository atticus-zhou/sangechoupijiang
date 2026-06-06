import sqlite3
import shutil
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.llm.providers import LLMResponse, LiteLLMProvider
from src.web.app import app


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


if __name__ == "__main__":
    unittest.main()
