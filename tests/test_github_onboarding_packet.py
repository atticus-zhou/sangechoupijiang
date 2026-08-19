import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path("scripts/export_github_onboarding_packet.py")


class GitHubOnboardingPacketTests(unittest.TestCase):
    def test_exports_no_key_onboarding_packet_and_archive(self):
        output_dir = Path("tmp/test-github-onboarding-packet")
        zip_path = Path("tmp/test-github-onboarding-packet.zip")
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--output",
                str(output_dir),
                "--zip",
                str(zip_path),
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertFalse(payload["requires_api_key"])
        self.assertFalse(payload["calls_real_models"])
        self.assertFalse(payload["writes_workspace"])
        self.assertTrue(output_dir.joinpath("OPEN_THIS_FIRST.md").is_file())
        self.assertTrue(output_dir.joinpath("packet-manifest.json").is_file())
        self.assertTrue(zip_path.is_file())
        self.assertGreater(payload["archive_bytes"], 1000)

        copied_targets = {item["target"] for item in payload["files"]}
        for target in [
            "README.md",
            "config.example.yaml",
            "docs/FIRST_RUN_DECISION_CARD.md",
            "docs/MODEL_CONFIGURATION.md",
            "docs/STATIC_SHOWCASE_DEPLOYMENT.md",
            "docs/PUBLIC_RELEASE_HANDOFF.md",
            "docs/REAL_PRODUCTION_CLAIMS.md",
        ]:
            self.assertIn(target, copied_targets)

        verification = {item["id"]: item for item in payload["verification"]}
        self.assertEqual(set(verification), {"first_run", "model_guidance", "public_docs", "secret_scan"})
        self.assertTrue(all(item["status"] == "passed" for item in verification.values()))
        self.assertIn("github_download=ready", verification["first_run"]["summary"])
        self.assertIn("tracked secrets", verification["secret_scan"]["summary"])

        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
        self.assertIn("OPEN_THIS_FIRST.md", names)
        self.assertIn("verification/first_run.json", names)
        self.assertIn("verification/secret_scan.txt", names)
        forbidden = ("config.yaml", ".env", "user_data", "output", "runtime_logs", ".vercel")
        for name in names:
            lowered_parts = {part.lower() for part in Path(name).parts}
            self.assertFalse(lowered_parts & set(forbidden), name)

    def test_markdown_mentions_archive_and_no_key_boundary(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--output",
                "tmp/test-github-onboarding-packet-md",
                "--zip",
                "tmp/test-github-onboarding-packet-md.zip",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("# GitHub Onboarding Packet", result.stdout)
        self.assertIn("Requires API key: `False`", result.stdout)
        self.assertIn("Calls real models: `False`", result.stdout)
        self.assertIn("Writes workspace: `False`", result.stdout)
        self.assertIn("Archive:", result.stdout)
        self.assertIn("first_run", result.stdout)
        self.assertIn("model_guidance", result.stdout)
        self.assertIn("secret_scan", result.stdout)


if __name__ == "__main__":
    unittest.main()
