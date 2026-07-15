import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.verify_comic_real_production_claim import build_claim_report
from scripts.verify_comic_v2_delivery import verify_delivery
from src.comic_office.v2.production_benchmark import audit_handoff_manifest
from src.comic_office.v2.visual_review import REVIEW_DIMENSIONS


FIXTURE = Path("tests/fixtures/comic_v2_sample.json")


def _real_verified_manifest(root: Path) -> Path:
    result = verify_delivery(FIXTURE, root)
    path = Path(result["handoff_manifest_path"])
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for image in manifest["images"]:
        image["provider"] = "doubao"
        image["model"] = "seedream"
        image["review"] = {
            "status": "pass",
            "handoff_ready": True,
            "fixture": False,
            "scores": {dimension: 94 for dimension in REVIEW_DIMENSIONS},
        }
    manifest["quality_benchmark"] = audit_handoff_manifest(manifest)
    real_path = root / "real_verified_handoff_manifest.json"
    real_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return real_path


class ComicRealProductionClaimTests(unittest.TestCase):
    def test_fixture_report_is_demo_only_and_forbids_real_quality_claim(self):
        report = build_claim_report()

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["claim_level"], "demo_structure_only")
        self.assertTrue(report["can_publicly_show"])
        self.assertFalse(report["can_claim_real_quality"])
        self.assertEqual(report["downstream_status"], "structure_demo_only")
        forbidden = "\n".join(report["forbidden_public_claims"])
        self.assertIn("不能宣称真实模型画质已验证", forbidden)
        self.assertFalse(report["calls_real_models"])
        checklist = {item["id"]: item for item in report["claim_upgrade_checklist"]}
        self.assertEqual(checklist["run_real_models"]["status"], "missing")
        self.assertEqual(checklist["visual_review"]["status"], "missing")
        self.assertIn("真实模型", checklist["run_real_models"]["why_it_matters"])

    def test_real_verified_manifest_allows_real_quality_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _real_verified_manifest(Path(tmp))
            report = build_claim_report(manifest_path)

        self.assertEqual(report["claim_level"], "real_quality_verified")
        self.assertTrue(report["can_claim_real_quality"])
        self.assertEqual(report["downstream_status"], "ready_for_downstream")
        self.assertEqual(report["evidence"]["visual_evidence_level"], "model_reviewed")
        checklist = {item["id"]: item for item in report["claim_upgrade_checklist"]}
        self.assertEqual(checklist["keep_evidence_bundle"]["status"], "complete")
        self.assertEqual(checklist["repeat_after_major_edit"]["status"], "required_when_changed")

    def test_cli_markdown_is_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_comic_real_production_claim.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("AI Comic Real Production Claim", completed.stdout)
        self.assertIn("Claim level: `demo_structure_only`", completed.stdout)
        self.assertIn("Can claim real quality: `False`", completed.stdout)
        self.assertIn("Forbidden Public Claims", completed.stdout)
        self.assertIn("Claim Upgrade Checklist", completed.stdout)
        self.assertIn("使用真实模型生成图片资产", completed.stdout)
        self.assertIn("不能宣称真实模型画质已验证", completed.stdout)


if __name__ == "__main__":
    unittest.main()
