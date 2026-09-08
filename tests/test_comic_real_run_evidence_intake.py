import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.verify_comic_v2_delivery import verify_delivery
from scripts.verify_comic_real_run_evidence_intake import find_latest_user_handoff_manifest
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

class ComicRealRunEvidenceIntakeTests(unittest.TestCase):
    def test_real_run_intake_is_bound_to_current_claim_gates(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_comic_real_run_evidence_intake.py",
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
        self.assertEqual(payload["mode"], "comic_real_run_evidence_intake")
        self.assertEqual(payload["document"], "docs/COMIC_REAL_RUN_EVIDENCE_INTAKE.md")
        self.assertEqual(payload["missing_marker_count"], 0)
        self.assertEqual(payload["human_flow_step_count"], 6)
        self.assertEqual(payload["recovery_action_count"], 4)
        self.assertEqual(payload["benchmark_claim"], "demo_structure_verified")
        self.assertFalse(payload["benchmark_real_quality_verified"])
        self.assertEqual(payload["claim_level"], "demo_structure_only")
        self.assertFalse(payload["can_claim_real_quality"])
        self.assertEqual(payload["downstream_status"], "structure_demo_only")
        self.assertFalse(payload["handoff_allowed"])
        self.assertTrue(all(payload["section_status"].values()))

    def test_real_run_intake_explains_assets_prompts_word_and_recovery(self):
        text = Path("docs/COMIC_REAL_RUN_EVIDENCE_INTAKE.md").read_text(encoding="utf-8")

        self.assertIn("人物资产和道具资产默认应该是干净白底或极简背景", text)
        self.assertIn("不讲故事、不加剧情动作", text)
        self.assertIn("提示词不能只是固定模板堆词", text)
        self.assertIn("像导演交代现场一样", text)
        self.assertIn("哪张图服务哪个镜头，哪个镜头使用哪些资产", text)
        self.assertIn("不能让用户重新开盲盒", text)

    def test_markdown_output_is_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_comic_real_run_evidence_intake.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("AI Comic Real-Run Evidence Intake Audit", completed.stdout)
        self.assertIn("Benchmark: `demo_structure_verified` / real_quality=False", completed.stdout)
        self.assertIn("Public claim: `demo_structure_only` / can_claim_real_quality=False", completed.stdout)
        self.assertIn("Downstream: `structure_demo_only` / handoff_allowed=False", completed.stdout)
        self.assertIn("Audit subject: `fixed_public_sample`", completed.stdout)
        self.assertIn("Image Evidence", completed.stdout)
        self.assertIn("Real Model Evidence", completed.stdout)

    def test_existing_real_manifest_can_pass_the_intake_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _real_verified_manifest(Path(tmp))
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/verify_comic_real_run_evidence_intake.py",
                    "--manifest",
                    str(manifest_path),
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
        self.assertEqual(payload["audit_subject"], "existing_manifest")
        self.assertEqual(payload["audited_manifest"], str(manifest_path))
        self.assertEqual(payload["claim_level"], "real_quality_verified")
        self.assertTrue(payload["can_claim_real_quality"])
        self.assertEqual(payload["downstream_status"], "ready_for_downstream")
        self.assertTrue(payload["handoff_allowed"])
        self.assertTrue(payload["real_quality_promotion_ready"])
        self.assertEqual(payload["visual_evidence_level"], "model_reviewed")
        self.assertEqual(payload["real_model_evidence_requirements"]["status"], "ready")
        self.assertEqual(payload["image_quality_summary"]["waste_or_rework_images"], 0)

    def test_latest_manifest_finder_prefers_newest_workspace_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_path = root / "ws_old" / "delivery" / "old_handoff_manifest.json"
            new_path = root / "ws_new" / "delivery" / "new_handoff_manifest.json"
            old_path.parent.mkdir(parents=True)
            new_path.parent.mkdir(parents=True)
            old_path.write_text("{}", encoding="utf-8")
            new_path.write_text("{}", encoding="utf-8")

            old_time = 1_700_000_000
            new_time = 1_800_000_000
            old_path.touch()
            new_path.touch()
            import os

            os.utime(old_path, (old_time, old_time))
            os.utime(new_path, (new_time, new_time))

            self.assertEqual(find_latest_user_handoff_manifest(root), new_path)

    def test_latest_cli_audits_newest_user_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace_delivery = root / "ws_latest" / "delivery"
            workspace_delivery.mkdir(parents=True)
            manifest_path = _real_verified_manifest(workspace_delivery)
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/verify_comic_real_run_evidence_intake.py",
                    "--latest",
                    "--latest-output-root",
                    str(root),
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
        self.assertEqual(payload["audit_subject"], "latest_user_manifest")
        self.assertEqual(payload["audited_manifest"], str(manifest_path))
        self.assertEqual(payload["claim_level"], "real_quality_verified")
        self.assertTrue(payload["handoff_allowed"])


if __name__ == "__main__":
    unittest.main()
