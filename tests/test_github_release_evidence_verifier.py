import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from scripts.verify_github_release_evidence import (
    format_markdown,
    verify_github_release_contract,
    verify_github_release_evidence,
)


SUCCESS_RUN = {
    "workflow_runs": [
        {
            "name": "Release readiness",
            "run_number": 19,
            "display_title": "Expose public release readiness evidence",
            "head_sha": "dba21dd",
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/example/actions/runs/19",
            "created_at": "2026-08-01T10:28:09Z",
            "updated_at": "2026-08-01T10:29:44Z",
            "artifacts_url": "https://api.github.com/artifacts",
        }
    ]
}

SUCCESS_ARTIFACTS = {
    "artifacts": [
        {
            "name": "no-key-release-evidence",
            "size_in_bytes": 1844,
            "expired": False,
            "created_at": "2026-08-01T10:29:42Z",
            "archive_download_url": "https://api.github.com/artifacts/1/zip",
        }
    ]
}

HTML_FALLBACK_PAGE = """
<html>
  <body>
    <a href="/atticus-zhou/sangechoupijiang/actions/runs/22"
       aria-label="in_progress: Run 22 of Release readiness. Add office recovery registry">
      <span class="css-truncate-target">Add office recovery registry</span>
    </a>
    <span>6b1ca2a</span>
  </body>
</html>
"""

COMMIT_CHECKS_PAGE = """
<html>
  <head><title>Add public showcase text integrity gate · atticus-zhou/sangechoupijiang@4b5eb51 · GitHub</title></head>
  <body>
    <a href="/atticus-zhou/sangechoupijiang/actions/runs/30698472636">
      <span>Release readiness</span>
      <span>on: push</span>
    </a>
    <svg aria-label="This job succeeded"></svg>
    <a href="/atticus-zhou/sangechoupijiang/actions/runs/30698472636/job/91365228496">
      <span>No-key public release gate</span>
    </a>
  </body>
</html>
"""

RUN_WITH_ARTIFACT_PAGE = """
<html>
  <body>
    <h1>Document comic prompt strategy claim gate</h1>
    <div>Status Success</div>
    <div>Artifacts</div>
    <table>
      <tr><th>Name</th><th>Size</th><th>Digest</th></tr>
      <tr>
        <td>no-key-release-evidence</td>
        <td>2.39 KB</td>
        <td>sha256:87f3deee82fae126cdafb6ce0d3e43802531c04b9986b4c48aa1dd0e1698106f</td>
      </tr>
    </table>
  </body>
</html>
"""


class GitHubReleaseEvidenceVerifierTests(unittest.TestCase):
    def test_verifier_passes_when_latest_run_succeeds_and_artifact_exists(self):
        def fake_fetch(url, timeout):
            if "actions/runs?" in url:
                return SUCCESS_RUN
            return SUCCESS_ARTIFACTS

        with patch("scripts.verify_github_release_evidence._fetch_json", side_effect=fake_fetch):
            payload = verify_github_release_evidence()

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["latest_run"]["conclusion"], "success")
        self.assertEqual(payload["artifact"]["name"], "no-key-release-evidence")
        self.assertFalse(payload["artifact"]["expired"])
        self.assertFalse(payload["errors"])

    def test_verifier_fails_when_latest_run_is_not_complete(self):
        def fake_fetch(url, timeout):
            if "actions/runs?" in url:
                run = dict(SUCCESS_RUN["workflow_runs"][0])
                run["status"] = "in_progress"
                run["conclusion"] = None
                return {"workflow_runs": [run]}
            return SUCCESS_ARTIFACTS

        with patch("scripts.verify_github_release_evidence._fetch_json", side_effect=fake_fetch):
            payload = verify_github_release_evidence()

        self.assertEqual(payload["status"], "failed")
        self.assertTrue(any("not completed" in item for item in payload["errors"]))
        self.assertTrue(any("not success" in item for item in payload["errors"]))

    def test_verifier_fails_when_artifact_is_missing(self):
        def fake_fetch(url, timeout):
            if "actions/runs?" in url:
                return SUCCESS_RUN
            return {"artifacts": []}

        with patch("scripts.verify_github_release_evidence._fetch_json", side_effect=fake_fetch):
            payload = verify_github_release_evidence()

        self.assertEqual(payload["status"], "failed")
        self.assertIn("required artifact 'no-key-release-evidence' was not found", payload["errors"])

    def test_json_cli_outputs_machine_readable_payload(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_github_release_evidence.py",
                "--repo",
                "bad-format",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("owner/name", payload["errors"][0])

    def test_verifier_uses_public_actions_page_when_api_is_rate_limited(self):
        with (
            patch(
                "scripts.verify_github_release_evidence._fetch_json",
                side_effect=RuntimeError("GitHub API returned HTTP 403: rate limit"),
            ),
            patch("scripts.verify_github_release_evidence._fetch_text", return_value=HTML_FALLBACK_PAGE),
        ):
            payload = verify_github_release_evidence()

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["verification_source"], "github_actions_html_fallback")
        self.assertEqual(payload["latest_run"]["run_number"], 22)
        self.assertEqual(payload["latest_run"]["run_id"], "22")
        self.assertIn("Add office recovery registry", payload["latest_run"]["display_title"])
        self.assertEqual(payload["latest_run"]["status"], "in_progress")
        self.assertIn("actions?query=branch%3Acodex%2Fcomic-quality-overhaul", payload["public_actions_url"])
        self.assertTrue(any("could not be verified from public GitHub pages" in item for item in payload["errors"]))

    def test_verifier_uses_commit_checks_page_when_api_is_rate_limited_and_head_sha_is_given(self):
        def fake_fetch_text(url, timeout):
            if "/commit/" in url:
                return COMMIT_CHECKS_PAGE
            return HTML_FALLBACK_PAGE

        with (
            patch(
                "scripts.verify_github_release_evidence._fetch_json",
                side_effect=RuntimeError("GitHub API returned HTTP 403: rate limit"),
            ),
            patch("scripts.verify_github_release_evidence._fetch_text", side_effect=fake_fetch_text),
        ):
            payload = verify_github_release_evidence(head_sha="4b5eb5170112ea6dfea66fc3d7f4ed60dc901f1a")

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["verification_source"], "github_commit_checks_html_fallback")
        self.assertEqual(payload["latest_run"]["run_id"], "30698472636")
        self.assertEqual(payload["latest_run"]["head_sha"], "4b5eb5170112ea6dfea66fc3d7f4ed60dc901f1a")
        self.assertEqual(payload["latest_run"]["status"], "completed")
        self.assertEqual(payload["latest_run"]["conclusion"], "success")
        self.assertIn("/commit/4b5eb5170112ea6dfea66fc3d7f4ed60dc901f1a/checks", payload["public_commit_checks_url"])
        self.assertEqual(payload["artifact"], {})
        self.assertTrue(any("could not be verified from public GitHub pages" in item for item in payload["errors"]))

    def test_html_fallback_passes_when_public_pages_show_success_and_artifact(self):
        def fake_fetch_text(url, timeout):
            if "/commit/" in url:
                return COMMIT_CHECKS_PAGE
            if "/actions/runs/30698472636" in url:
                return RUN_WITH_ARTIFACT_PAGE
            return HTML_FALLBACK_PAGE

        with (
            patch(
                "scripts.verify_github_release_evidence._fetch_json",
                side_effect=RuntimeError("GitHub API returned HTTP 403: rate limit"),
            ),
            patch("scripts.verify_github_release_evidence._fetch_text", side_effect=fake_fetch_text),
        ):
            payload = verify_github_release_evidence(head_sha="4b5eb5170112ea6dfea66fc3d7f4ed60dc901f1a")

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["verification_source"], "github_commit_checks_html_fallback")
        self.assertEqual(payload["latest_run"]["conclusion"], "success")
        self.assertEqual(payload["artifact"]["name"], "no-key-release-evidence")
        self.assertGreater(payload["artifact"]["size_in_bytes"], 0)
        self.assertFalse(payload["errors"])
        self.assertTrue(payload["warnings"])

    def test_verifier_reports_when_api_and_html_fallback_both_fail(self):
        with (
            patch(
                "scripts.verify_github_release_evidence._fetch_json",
                side_effect=RuntimeError("GitHub API returned HTTP 403: rate limit"),
            ),
            patch(
                "scripts.verify_github_release_evidence._fetch_text",
                side_effect=RuntimeError("GitHub Actions page request failed: blocked"),
            ),
        ):
            payload = verify_github_release_evidence()

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["verification_source"], "github_api_unavailable")
        self.assertTrue(any("GitHub API returned HTTP 403" in item for item in payload["errors"]))
        self.assertTrue(any("Actions page request failed" in item for item in payload["errors"]))

    def test_markdown_mentions_verification_source_and_public_actions_url(self):
        payload = {
            "status": "failed",
            "mode": "github_no_key_release_evidence",
            "verification_source": "github_actions_html_fallback",
            "repo": "atticus-zhou/sangechoupijiang",
            "branch": "codex/comic-quality-overhaul",
            "workflow_name": "Release readiness",
            "artifact_name": "no-key-release-evidence",
            "public_actions_url": "https://github.com/atticus-zhou/sangechoupijiang/actions?query=branch%3Acodex%2Fcomic-quality-overhaul",
            "public_commit_checks_url": "https://github.com/atticus-zhou/sangechoupijiang/commit/4b5eb51/checks",
            "latest_run": {"run_number": 22, "status": "in_progress", "conclusion": None},
            "artifact": {},
            "summary": "fallback",
            "errors": [],
        }

        markdown = format_markdown(payload)

        self.assertIn("Verification source: `github_actions_html_fallback`", markdown)
        self.assertIn("Public Actions URL: https://github.com/atticus-zhou/sangechoupijiang/actions", markdown)
        self.assertIn("Public Commit Checks URL: https://github.com/atticus-zhou/sangechoupijiang/commit/4b5eb51/checks", markdown)

    def test_contract_only_verifies_local_workflow_and_docs(self):
        payload = verify_github_release_contract()

        self.assertEqual(payload["status"], "passed", payload.get("failures"))
        self.assertEqual(payload["mode"], "github_no_key_release_contract")
        self.assertEqual(payload["artifact_name"], "no-key-release-evidence")
        self.assertEqual(
            {item["id"] for item in payload["checks"]},
            {
                "workflow_uploads_evidence",
                "readme_explains_github_evidence_boundary",
                "handoff_explains_github_evidence_boundary",
            },
        )

    def test_contract_only_cli_is_network_free_and_machine_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_github_release_evidence.py",
                "--contract-only",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["mode"], "github_no_key_release_contract")
        self.assertEqual(len(payload["checks"]), 3)


if __name__ == "__main__":
    unittest.main()
