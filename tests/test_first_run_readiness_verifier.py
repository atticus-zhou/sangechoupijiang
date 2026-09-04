import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_first_run_readiness.py")


class FirstRunReadinessVerifierTests(unittest.TestCase):
    def test_json_guides_new_user_through_demo_local_and_developer_paths(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["status"], "ready_for_guided_first_run")
        self.assertEqual(payload["mode"], "new_user_reproducibility")
        self.assertTrue(payload["safe_for_public_repo"])
        self.assertNotIn("sk-", result.stdout.lower())

        checklist = payload["github_download_checklist"]
        self.assertEqual(checklist["status"], "ready")
        self.assertEqual(
            checklist["present_public_file_count"],
            checklist["expected_public_file_count"],
        )
        checklist_text = json.dumps(checklist, ensure_ascii=False)
        for marker in [
            "START_HERE.md",
            "README.md",
            "requirements.txt",
            "config.example.yaml",
            "scripts/doctor.py",
            "scripts/verify_release_readiness.py",
            "docs/FIRST_RUN_DECISION_CARD.md",
            "docs/MODEL_CONFIGURATION.md",
            "docs/MODEL_CAPABILITY_MATRIX.json",
            "docs/STATIC_SHOWCASE_DEPLOYMENT.md",
        ]:
            self.assertIn(marker, checklist_text)
        for private_marker in [
            "config.yaml",
            ".env",
            "user_data/",
            "output/",
            "runtime_logs/",
            "browser profiles",
        ]:
            self.assertIn(private_marker, checklist_text)
        self.assertIn("python scripts/check_no_secrets.py", checklist_text)
        self.assertIn("python scripts/verify_release_readiness.py --format markdown", checklist_text)
        self.assertEqual(checklist["missing_python_packages"], [])
        for package in [
            "fastapi",
            "litellm",
            "python-docx",
            "pillow",
            "requests",
            "beautifulsoup4",
            "python-multipart",
        ]:
            self.assertIn(package, checklist["present_python_packages"])

        deployment_modes = {item["id"]: item for item in payload["deployment_mode_matrix"]}
        self.assertEqual(set(deployment_modes), {"public_demo", "local_real_use", "future_saas"})
        self.assertEqual(deployment_modes["public_demo"]["status"], "ready")
        self.assertFalse(deployment_modes["public_demo"]["requires_api_key"])
        self.assertFalse(deployment_modes["public_demo"]["allows_real_model_calls"])
        self.assertFalse(deployment_modes["public_demo"]["allows_workspace_writes"])
        self.assertIn("/api/demo", " ".join(deployment_modes["public_demo"]["allowed"]))
        self.assertIn("config.yaml", " ".join(deployment_modes["public_demo"]["forbidden"]))
        self.assertTrue(deployment_modes["local_real_use"]["requires_api_key"])
        self.assertTrue(deployment_modes["local_real_use"]["allows_real_model_calls"])
        self.assertTrue(deployment_modes["local_real_use"]["allows_workspace_writes"])
        self.assertIn("output", " ".join(deployment_modes["local_real_use"]["forbidden"]))
        self.assertEqual(deployment_modes["future_saas"]["status"], "not_current_product")
        self.assertEqual(deployment_modes["future_saas"]["allows_real_model_calls"], "not_implemented")
        self.assertIn("前端 JavaScript", " ".join(deployment_modes["future_saas"]["forbidden"]))

        paths = {item["id"]: item for item in payload["paths"]}
        for path_id in ["public_demo", "local_real_use", "developer_extension"]:
            self.assertIn(path_id, paths)
            self.assertIn(paths[path_id]["status"], {"ready", "needs_user_action"})
            self.assertGreaterEqual(len(paths[path_id]["steps"]), 3)
            self.assertTrue(paths[path_id]["next_action"])

        self.assertEqual(paths["public_demo"]["status"], "ready")
        self.assertFalse(paths["public_demo"]["requires_api_key"])
        self.assertIn("/api/demo/public-showcase", "\n".join(paths["public_demo"]["evidence"]))
        self.assertIn("/api/demo/comic-production/files/handoff_manifest.json", "\n".join(paths["public_demo"]["evidence"]))
        self.assertIn("/api/demo/research/files/evidence_manifest.json", "\n".join(paths["public_demo"]["evidence"]))
        self.assertIn("/api/demo/research/claim-report", "\n".join(paths["public_demo"]["evidence"]))
        self.assertIn("verify_comic_v2_downstream_handoff.py", "\n".join(paths["public_demo"]["steps"]))
        self.assertIn("export_public_showcase.py", "\n".join(paths["public_demo"]["steps"]))
        self.assertIn("dist/public-showcase/index.html", "\n".join(paths["public_demo"]["evidence"]))
        self.assertIn("docs/COMIC_DOWNSTREAM_HANDOFF.md", "\n".join(paths["public_demo"]["evidence"]))
        reading_guide = paths["public_demo"]["deliverable_reading_guide"]
        self.assertEqual(len(reading_guide), 8)
        self.assertTrue(all(item["file"] and item["uri"] and item["look_for"] and item["proves"] for item in reading_guide))
        self.assertTrue(any("Word 制片画布" in item["file"] for item in reading_guide))
        self.assertTrue(any("handoff manifest" in item["file"] for item in reading_guide))
        self.assertTrue(any("资产规格矩阵" in item["file"] for item in reading_guide))
        self.assertTrue(any("资产使用地图" in item["file"] for item in reading_guide))
        guide_text = json.dumps(reading_guide, ensure_ascii=False)
        self.assertIn("portfolio_embed.asset_requirement_matrix", guide_text)
        self.assertIn("portfolio_embed.asset_usage_map", guide_text)
        self.assertIn("identity_baseline_image", guide_text)
        self.assertIn("image_roles", guide_text)
        self.assertIn("referenced_shots", guide_text)
        self.assertIn("downstream_instruction", guide_text)
        self.assertIn("handoff_ready", guide_text)
        self.assertIn("three_view", guide_text)
        self.assertIn("expression_sheet", guide_text)
        self.assertIn("turnaround", guide_text)
        self.assertIn("top_down", guide_text)
        self.assertIn("clean_background_required", guide_text)
        self.assertTrue(any("真实生产声明报告" in item["file"] for item in reading_guide))
        self.assertTrue(any("阶段性交付声明" in item["file"] for item in reading_guide))
        self.assertTrue(any("证据清单" in item["file"] for item in reading_guide))
        self.assertTrue(paths["local_real_use"]["requires_api_key"])
        self.assertIn("config.yaml", "\n".join(paths["local_real_use"]["steps"]))
        self.assertIn("真实生产前检查", "\n".join(paths["local_real_use"]["steps"]))
        self.assertIn("audit_comic_v2_handoffs.py", "\n".join(paths["local_real_use"]["steps"]))
        self.assertIn("verify_comic_real_production_claim.py", "\n".join(paths["local_real_use"]["steps"]))
        self.assertIn("verify_comic_v2_production_benchmark.py", "\n".join(paths["local_real_use"]["steps"]))
        model_ladder = paths["local_real_use"]["model_setup_ladder"]
        self.assertEqual([item["level"] for item in model_ladder], ["no_key_demo", "minimum_text", "full_comic_production"])
        ladder_text = json.dumps(model_ladder, ensure_ascii=False)
        self.assertIn("中书省文本模型", ladder_text)
        self.assertIn("尚书省文本模型", ladder_text)
        self.assertIn("吏部文本模型", ladder_text)
        self.assertIn("工部生图模型", ladder_text)
        self.assertIn("刑部视觉理解模型", ladder_text)
        self.assertIn("ready_for_real_run", ladder_text)
        self.assertIn("real_production.status=", "\n".join(paths["local_real_use"]["evidence"]))
        self.assertIn("real_production.full=", "\n".join(paths["local_real_use"]["evidence"]))
        self.assertIn("real_output_evidence.status=", "\n".join(paths["local_real_use"]["evidence"]))
        self.assertIn("real_output_evidence.verified=", "\n".join(paths["local_real_use"]["evidence"]))
        real_output = paths["local_real_use"]["real_output_evidence"]
        self.assertFalse(real_output["has_verified_real_output"])
        self.assertEqual(real_output["verified_output_status"], "structure_demo_only")
        self.assertIn("结构样例", real_output["summary"])
        self.assertIn("production benchmark", real_output["next_action"])
        self.assertIn("真实画质已验证", real_output["public_claim_rule"])
        validations = paths["local_real_use"]["post_run_validation"]
        self.assertEqual([item["name"] for item in validations], ["交付物清点", "真实生产声明", "制片质量基准"])
        validation_text = json.dumps(validations, ensure_ascii=False)
        self.assertIn("Word canvas", validation_text)
        self.assertIn("can_claim_real_quality=True", validation_text)
        self.assertIn("production_quality_verified", validation_text)
        self.assertIn("verify_office_isolation.py", "\n".join(paths["developer_extension"]["steps"]))

        safety = "\n".join(payload["safety_boundaries"])
        self.assertIn("API Key", safety)
        self.assertIn("user_data", safety)
        self.assertIn("output", safety)

        failures = {item["id"]: item for item in payload["common_first_run_failures"]}
        for failure_id in [
            "missing_dependencies",
            "missing_local_config",
            "model_preflight_blocked",
            "port_in_use",
            "codex_windows_sandbox_setup_failed",
            "public_deploy_real_mode",
            "incomplete_handoff_download",
            "github_showcase_workflow_email_failed",
        ]:
            self.assertIn(failure_id, failures)
            self.assertTrue(failures[failure_id]["symptom"])
            self.assertTrue(failures[failure_id]["check_command"])
            self.assertTrue(failures[failure_id]["recovery_action"])
        self.assertFalse(failures["missing_dependencies"]["requires_api_key"])
        self.assertTrue(failures["model_preflight_blocked"]["requires_api_key"])
        self.assertIn("requirements.txt", failures["missing_dependencies"]["recovery_action"])
        self.assertIn("不是三个臭皮匠项目代码报错", failures["codex_windows_sandbox_setup_failed"]["likely_cause"])
        self.assertFalse(failures["codex_windows_sandbox_setup_failed"]["requires_api_key"])
        self.assertIn("dist/public-showcase", failures["public_deploy_real_mode"]["recovery_action"])
        self.assertIn("audit_comic_v2_handoffs.py", failures["incomplete_handoff_download"]["check_command"])
        self.assertIn("manifest v3", failures["incomplete_handoff_download"]["likely_cause"])
        self.assertIn("重新生成缺失阶段", failures["incomplete_handoff_download"]["recovery_action"])
        self.assertFalse(failures["github_showcase_workflow_email_failed"]["requires_api_key"])
        self.assertIn("atticus-zhou/me", failures["github_showcase_workflow_email_failed"]["recovery_action"])
        self.assertIn("npm run check:showcase-ci", failures["github_showcase_workflow_email_failed"]["check_command"])
        self.assertIn("sangechoupijiang", failures["github_showcase_workflow_email_failed"]["recovery_action"])

    def test_markdown_is_readable_as_a_github_first_run_checklist(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("# First Run Readiness", result.stdout)
        self.assertIn("GitHub Download Checklist", result.stdout)
        self.assertIn("START_HERE.md", result.stdout)
        self.assertIn("docs/FIRST_RUN_DECISION_CARD.md", result.stdout)
        self.assertIn("Expected public files", result.stdout)
        self.assertIn("Never Commit", result.stdout)
        self.assertIn("config.example.yaml", result.stdout)
        self.assertIn("runtime_logs/", result.stdout)
        self.assertIn("Before Public Sharing", result.stdout)
        self.assertIn("Deployment Mode Matrix", result.stdout)
        self.assertIn("public_demo - 公开无 Key 演示", result.stdout)
        self.assertIn("local_real_use - 本地真实使用", result.stdout)
        self.assertIn("future_saas - 未来 SaaS 模式", result.stdout)
        self.assertIn("Allows real model calls: `False`", result.stdout)
        self.assertIn("not_current_product", result.stdout)
        self.assertIn("public_demo", result.stdout)
        self.assertIn("local_real_use", result.stdout)
        self.assertIn("real_production.status=", result.stdout)
        self.assertIn("developer_extension", result.stdout)
        self.assertIn("python run.py --port 8080", result.stdout)
        self.assertIn("python scripts/verify_public_demo_mode.py --format markdown", result.stdout)
        self.assertIn("python scripts/export_public_showcase.py", result.stdout)
        self.assertIn("python scripts/verify_static_public_showcase.py --format markdown", result.stdout)
        self.assertIn("python scripts/verify_comic_v2_downstream_handoff.py --format markdown", result.stdout)
        self.assertIn("python scripts/verify_office_isolation.py --format markdown", result.stdout)
        self.assertIn("Deliverable reading guide", result.stdout)
        self.assertIn("AI 漫剧 Word 制片画布", result.stdout)
        self.assertIn("handoff manifest", result.stdout)
        self.assertIn("AI 漫剧资产规格矩阵", result.stdout)
        self.assertIn("portfolio_embed.asset_requirement_matrix", result.stdout)
        self.assertIn("AI 漫剧资产使用地图", result.stdout)
        self.assertIn("portfolio_embed.asset_usage_map", result.stdout)
        self.assertIn("identity_baseline_image", result.stdout)
        self.assertIn("downstream_instruction", result.stdout)
        self.assertIn("clean_background_required", result.stdout)
        self.assertIn("AI 漫剧真实生产声明报告", result.stdout)
        self.assertIn("研究办公室证据清单", result.stdout)
        self.assertIn("研究办公室阶段性交付声明", result.stdout)
        self.assertIn("Model setup ladder", result.stdout)
        self.assertIn("full_comic_production", result.stdout)
        self.assertIn("Post-run validation", result.stdout)
        self.assertIn("交付物清点", result.stdout)
        self.assertIn("python scripts/audit_comic_v2_handoffs.py --format markdown", result.stdout)
        self.assertIn("can_claim_real_quality=True", result.stdout)
        self.assertIn("production_quality_verified", result.stdout)
        self.assertIn("Common First-run Failures", result.stdout)
        self.assertIn("missing_dependencies", result.stdout)
        self.assertIn("python -m pip install -r requirements.txt", result.stdout)
        self.assertIn("netstat -ano | findstr :8080", result.stdout)
        self.assertIn("codex_windows_sandbox_setup_failed", result.stdout)
        self.assertIn("codex-windows-sandbox-setup.exe", result.stdout)
        self.assertIn("public_deploy_real_mode", result.stdout)
        self.assertIn("incomplete_handoff_download", result.stdout)
        self.assertIn("python scripts/audit_comic_v2_handoffs.py --format markdown", result.stdout)
        self.assertIn("github_showcase_workflow_email_failed", result.stdout)
        self.assertIn("Three Cobblers showcase workflow run failed", result.stdout)
        self.assertIn("npm run check:showcase-ci", result.stdout)


if __name__ == "__main__":
    unittest.main()
