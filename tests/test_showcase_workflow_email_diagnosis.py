import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts.diagnose_showcase_workflow_email import (
    diagnose_showcase_workflow_email,
    format_markdown,
)


OLD_SHA = "8a09357082c3db32f4657195cd5d4a527b76d4f6"
LOCAL_SHA = "009c69ad07404c51ca328aa1a68820a050c26df3"


def run_payload(runs):
    return {"workflow_runs": runs}


WORKFLOWS_PAYLOAD = {
    "workflows": [
        {
            "id": 353131303,
            "name": "Public showcase pages",
            "path": ".github/workflows/pages-showcase.yml",
            "state": "active",
        }
    ]
}


OLD_FAILED_RUN = {
    "id": 34351432855,
    "name": "Public showcase pages",
    "head_sha": OLD_SHA,
    "event": "push",
    "status": "completed",
    "conclusion": "failure",
    "created_at": "2026-09-09T12:30:39Z",
    "updated_at": "2026-09-09T12:31:45Z",
    "html_url": "https://github.com/atticus-zhou/sangechoupijiang/actions/runs/34351432855",
    "display_title": "Render research evidence responsibilities in showcase",
}

SUCCESS_RELEASE_RUN = {
    "id": 35166714859,
    "name": "Release readiness",
    "head_sha": LOCAL_SHA,
    "event": "push",
    "status": "completed",
    "conclusion": "success",
    "created_at": "2026-09-17T00:28:41Z",
    "updated_at": "2026-09-17T00:31:15Z",
    "html_url": "https://github.com/atticus-zhou/sangechoupijiang/actions/runs/35166714859",
    "display_title": "Audit office extension protocol docs",
}

CURRENT_FAILED_RUN = {
    **OLD_FAILED_RUN,
    "id": 999,
    "head_sha": LOCAL_SHA,
    "event": "workflow_dispatch",
    "html_url": "https://github.com/atticus-zhou/sangechoupijiang/actions/runs/999",
}


class ShowcaseWorkflowEmailDiagnosisTests(unittest.TestCase):
    def test_old_failed_email_is_not_current_product_failure(self):
        def fake_fetch(url, timeout):
            if url.endswith("/actions/workflows"):
                return WORKFLOWS_PAYLOAD
            self.assertIn("actions/workflows/353131303/runs", url)
            return run_payload([OLD_FAILED_RUN, SUCCESS_RELEASE_RUN])

        with (
            patch("scripts.diagnose_showcase_workflow_email._fetch_json", side_effect=fake_fetch),
            patch("scripts.diagnose_showcase_workflow_email._local_head_sha", return_value=LOCAL_SHA),
            patch("scripts.diagnose_showcase_workflow_email._expand_local_head_sha", return_value=OLD_SHA),
        ):
            payload = diagnose_showcase_workflow_email(head_sha=OLD_SHA)

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["diagnosis"], "old_failed_run_email")
        self.assertTrue(payload["workflow_contract"]["manual_only"])
        self.assertEqual(payload["matched_email_run"]["head_sha_short"], "8a09357")
        self.assertTrue(any("旧提交" in item for item in payload["next_actions"]))
        self.assertTrue(any("npm run check:online" in item for item in payload["next_actions"]))

    def test_manual_only_without_current_failure_is_safe_to_explain(self):
        with (
            patch(
                "scripts.diagnose_showcase_workflow_email._fetch_json",
                side_effect=[WORKFLOWS_PAYLOAD, run_payload([OLD_FAILED_RUN])],
            ),
            patch("scripts.diagnose_showcase_workflow_email._local_head_sha", return_value=LOCAL_SHA),
        ):
            payload = diagnose_showcase_workflow_email()

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["diagnosis"], "current_contract_safe")
        self.assertTrue(any("只有手动触发" in item for item in payload["next_actions"]))

    def test_current_manual_run_failure_requires_attention(self):
        with (
            patch(
                "scripts.diagnose_showcase_workflow_email._fetch_json",
                side_effect=[WORKFLOWS_PAYLOAD, run_payload([CURRENT_FAILED_RUN])],
            ),
            patch("scripts.diagnose_showcase_workflow_email._local_head_sha", return_value=LOCAL_SHA),
        ):
            payload = diagnose_showcase_workflow_email()

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnosis"], "current_manual_run_failed")
        self.assertIn("999", payload["next_actions"][0])

    def test_push_trigger_contract_is_reported_as_repeat_email_risk(self):
        with (
            patch("scripts.diagnose_showcase_workflow_email._read_workflow_contract") as contract,
            patch(
                "scripts.diagnose_showcase_workflow_email._fetch_json",
                side_effect=[WORKFLOWS_PAYLOAD, run_payload([])],
            ),
            patch("scripts.diagnose_showcase_workflow_email._local_head_sha", return_value=LOCAL_SHA),
        ):
            contract.return_value = {
                "workflow_file": ".github/workflows/pages-showcase.yml",
                "exists": True,
                "has_workflow_dispatch": True,
                "has_push_trigger": True,
                "manual_only": False,
            }
            payload = diagnose_showcase_workflow_email()

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["diagnosis"], "workflow_still_push_triggered")
        self.assertTrue(any("workflow_dispatch" in item for item in payload["next_actions"]))

    def test_markdown_mentions_the_matched_email_run(self):
        payload = {
            "status": "passed",
            "mode": "github_public_showcase_workflow_email_diagnosis",
            "repo": "atticus-zhou/sangechoupijiang",
            "branch": "main",
            "workflow_name": "Public showcase pages",
            "diagnosis": "old_failed_run_email",
            "summary": "old run",
            "workflow_contract": {
                "workflow_file": ".github/workflows/pages-showcase.yml",
                "exists": True,
                "has_workflow_dispatch": True,
                "has_push_trigger": False,
                "manual_only": True,
            },
            "local_head_sha_short": "009c69a",
            "email_head_sha_short": "8a09357",
            "latest_run": OLD_FAILED_RUN | {"head_sha_short": "8a09357"},
            "matched_email_run": OLD_FAILED_RUN | {"head_sha_short": "8a09357"},
            "errors": [],
            "warnings": [],
            "next_actions": ["不要因此回滚产品代码。"],
        }

        text = format_markdown(payload)

        self.assertIn("Public Showcase Workflow Email Diagnosis", text)
        self.assertIn("Matched Email Run", text)
        self.assertIn("8a09357", text)
        self.assertIn("不要因此回滚产品代码", text)

    def test_json_cli_outputs_machine_readable_contract_payload(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/diagnose_showcase_workflow_email.py",
                "--contract-only",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["mode"], "github_public_showcase_workflow_email_diagnosis")
        self.assertEqual(payload["workflow_name"], "Public showcase pages")
        self.assertTrue(payload["workflow_contract"]["manual_only"])


if __name__ == "__main__":
    unittest.main()
