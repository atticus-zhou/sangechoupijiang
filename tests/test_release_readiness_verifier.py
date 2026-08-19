import json
import subprocess
import sys
import unittest


class ReleaseReadinessVerifierTests(unittest.TestCase):
    def test_json_runs_all_public_release_gates(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_release_readiness.py",
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
        self.assertTrue(payload["safe_for_public_release"])
        self.assertFalse(payload["failures"])

        check_ids = {item["id"] for item in payload["checks"]}
        self.assertEqual(
            check_ids,
            {
                "first_run",
                "productization_status",
                "model_guidance",
                "development_checklist",
                "github_release_contract",
                "public_docs_readability",
                "runtime_health",
                "first_run_guide",
                "public_demo",
                "static_showcase_export",
                "static_showcase",
                "portfolio_showcase_sync",
                "comic_delivery",
                "comic_downstream_handoff",
                "comic_production_benchmark",
                "comic_real_production_claim",
                "comic_production_acceptance",
                "comic_real_quality_upgrade_plan",
                "public_comic_trace_bundle",
                "comic_handoff_inventory",
                "research_readiness",
                "office_governance",
                "future_office_backlog",
                "office_schema_registry",
                "office_recovery_registry",
                "office_isolation",
                "product_readiness",
                "secret_scan",
            },
        )
        for check in payload["checks"]:
            self.assertEqual(check["status"], "passed")
            self.assertTrue(check["summary"])
            self.assertTrue(check["command"].startswith("python scripts/"))
        first_run = next(item for item in payload["checks"] if item["id"] == "first_run")
        self.assertIn("deployment_modes=3", first_run["summary"])
        self.assertIn("github_download=ready:14/14", first_run["summary"])
        self.assertIn("private_boundaries=10", first_run["summary"])
        model_guidance = next(item for item in payload["checks"] if item["id"] == "model_guidance")
        self.assertIn("offices=2", model_guidance["summary"])
        self.assertIn("comic_ladder=3", model_guidance["summary"])
        development_checklist = next(item for item in payload["checks"] if item["id"] == "development_checklist")
        self.assertIn("checks=6", development_checklist["summary"])
        self.assertIn("skip_release=True", development_checklist["summary"])
        github_contract = next(item for item in payload["checks"] if item["id"] == "github_release_contract")
        self.assertIn("artifact=no-key-release-evidence", github_contract["summary"])
        self.assertIn("failures=0", github_contract["summary"])
        runtime_health = next(item for item in payload["checks"] if item["id"] == "runtime_health")
        self.assertIn("endpoint=/health", runtime_health["summary"])
        self.assertIn("credentials=False", runtime_health["summary"])
        self.assertIn("real_models=False", runtime_health["summary"])
        first_run_guide = next(item for item in payload["checks"] if item["id"] == "first_run_guide")
        self.assertIn("endpoint=/api/first-run-guide", first_run_guide["summary"])
        self.assertIn("paths=3", first_run_guide["summary"])
        self.assertIn("quick_checks=5", first_run_guide["summary"])
        self.assertIn("credentials=False", first_run_guide["summary"])
        public_demo = next(item for item in payload["checks"] if item["id"] == "public_demo")
        self.assertIn("fast_review=5/5", public_demo["summary"])
        self.assertIn("reading_guide=", public_demo["summary"])
        self.assertIn("quick_start=5/5", public_demo["summary"])
        self.assertIn("interview_script=", public_demo["summary"])
        self.assertIn("reproducibility=5/5", public_demo["summary"])
        self.assertIn("badge=safe_public_demo", public_demo["summary"])
        static_showcase = next(item for item in payload["checks"] if item["id"] == "static_showcase")
        self.assertIn("downloads=8", static_showcase["summary"])
        self.assertIn("fast_review=5/5", static_showcase["summary"])
        self.assertIn("reading_guide=9/9", static_showcase["summary"])
        self.assertIn("quick_start=5/5", static_showcase["summary"])
        self.assertIn("post_run=3/3", static_showcase["summary"])
        self.assertIn("visitor_route=7", static_showcase["summary"])
        self.assertIn("download_acceptance=9", static_showcase["summary"])
        self.assertIn("handoff_recovery=8:regenerate_images", static_showcase["summary"])
        self.assertIn("backend=False", static_showcase["summary"])
        self.assertIn("prompt_quality=ready", static_showcase["summary"])
        self.assertIn("prompt_issues=0", static_showcase["summary"])
        self.assertIn("research_claim=staged_research_demo", static_showcase["summary"])
        self.assertIn("research_full_auto=False", static_showcase["summary"])
        portfolio_sync = next(item for item in payload["checks"] if item["id"] == "portfolio_showcase_sync")
        self.assertIn("compared=", portfolio_sync["summary"])
        self.assertIn("missing=0", portfolio_sync["summary"])
        self.assertIn("mismatched=0", portfolio_sync["summary"])
        self.assertIn("live_external=True", portfolio_sync["summary"])
        public_docs = next(item for item in payload["checks"] if item["id"] == "public_docs_readability")
        self.assertIn("docs=", public_docs["summary"])
        self.assertIn("failures=0", public_docs["summary"])
        comic_delivery = next(item for item in payload["checks"] if item["id"] == "comic_delivery")
        self.assertIn("quick_start=5", comic_delivery["summary"])
        comic_handoff = next(item for item in payload["checks"] if item["id"] == "comic_downstream_handoff")
        self.assertIn("structured_director_shots=2", comic_handoff["summary"])
        self.assertIn("quick_start=5", comic_handoff["summary"])
        comic_benchmark = next(item for item in payload["checks"] if item["id"] == "comic_production_benchmark")
        self.assertIn("score=100", comic_benchmark["summary"])
        self.assertIn("claim=demo_structure_verified", comic_benchmark["summary"])
        self.assertIn("real_quality_verified=False", comic_benchmark["summary"])
        self.assertIn("prompt_quality=ready", comic_benchmark["summary"])
        self.assertIn("prompt_issues=0", comic_benchmark["summary"])
        comic_claim = next(item for item in payload["checks"] if item["id"] == "comic_real_production_claim")
        self.assertIn("claim_level=demo_structure_only", comic_claim["summary"])
        self.assertIn("real_quality=False", comic_claim["summary"])
        self.assertIn("downstream=structure_demo_only", comic_claim["summary"])
        self.assertIn("upgrade_checklist=4", comic_claim["summary"])
        self.assertIn("recovery=regenerate_images", comic_claim["summary"])
        self.assertIn("recovery_steps=3", comic_claim["summary"])
        comic_acceptance = next(item for item in payload["checks"] if item["id"] == "comic_production_acceptance")
        self.assertIn("public_demo=True", comic_acceptance["summary"])
        self.assertIn("real_downstream=False", comic_acceptance["summary"])
        self.assertIn("downstream=structure_demo_only", comic_acceptance["summary"])
        self.assertIn("claim=demo_structure_only", comic_acceptance["summary"])
        self.assertIn("failures=0", comic_acceptance["summary"])
        self.assertIn("prompt_quality=ready", comic_acceptance["summary"])
        comic_upgrade = next(item for item in payload["checks"] if item["id"] == "comic_real_quality_upgrade_plan")
        self.assertIn("current=demo_structure_only", comic_upgrade["summary"])
        self.assertIn("target=real_quality_verified", comic_upgrade["summary"])
        self.assertIn("status=blocked_until_real_model_evidence", comic_upgrade["summary"])
        self.assertIn("steps=5", comic_upgrade["summary"])
        self.assertIn("models=gongbu,xingbu,bingbu", comic_upgrade["summary"])
        self.assertIn("recovery=regenerate_images", comic_upgrade["summary"])
        public_trace = next(item for item in payload["checks"] if item["id"] == "public_comic_trace_bundle")
        self.assertIn("assets=3", public_trace["summary"])
        self.assertIn("images=7", public_trace["summary"])
        self.assertIn("shots=2", public_trace["summary"])
        self.assertIn("claim=demo_structure_only", public_trace["summary"])
        self.assertIn("visual=fixture_only", public_trace["summary"])
        self.assertIn("real_quality=False", public_trace["summary"])
        self.assertIn("supports_real_quality=False", public_trace["summary"])
        self.assertIn("reproducibility=3", public_trace["summary"])
        comic_inventory = next(item for item in payload["checks"] if item["id"] == "comic_handoff_inventory")
        self.assertIn("production_verified=0", comic_inventory["summary"])
        self.assertIn("demo_only=", comic_inventory["summary"])
        research_readiness = next(item for item in payload["checks"] if item["id"] == "research_readiness")
        self.assertIn("reading_guide=3/3", research_readiness["summary"])
        self.assertIn("handoff=3/3", research_readiness["summary"])
        self.assertIn("capture=5/5", research_readiness["summary"])
        self.assertIn("claim=staged_research_demo", research_readiness["summary"])
        self.assertIn("full_auto=False", research_readiness["summary"])
        self.assertIn("upgrade_checklist=3", research_readiness["summary"])
        office_governance = next(item for item in payload["checks"] if item["id"] == "office_governance")
        self.assertIn("demo_contract=", office_governance["summary"])
        self.assertIn("starter=passed", office_governance["summary"])
        self.assertIn("starter_items=8", office_governance["summary"])
        self.assertIn("schema_bindings=11/11", office_governance["summary"])
        self.assertIn("recovery_bindings=12/12", office_governance["summary"])
        future_backlog = next(item for item in payload["checks"] if item["id"] == "future_office_backlog")
        self.assertIn("candidates=4/4", future_backlog["summary"])
        self.assertIn("backlog=2", future_backlog["summary"])
        self.assertIn("short_video_ads", future_backlog["summary"])
        self.assertIn("technical_project", future_backlog["summary"])
        self.assertIn("future_schema_validators", future_backlog["summary"])
        self.assertIn("future_recovery_events", future_backlog["summary"])
        office_schema_registry = next(item for item in payload["checks"] if item["id"] == "office_schema_registry")
        self.assertIn("providers=comic_production,research", office_schema_registry["summary"])
        self.assertIn("bindings=11/11", office_schema_registry["summary"])
        self.assertIn("errors=0", office_schema_registry["summary"])
        office_recovery_registry = next(item for item in payload["checks"] if item["id"] == "office_recovery_registry")
        self.assertIn("offices=comic_production,research", office_recovery_registry["summary"])
        self.assertIn("bindings=12/12", office_recovery_registry["summary"])
        self.assertIn("errors=0", office_recovery_registry["summary"])
        office_isolation = next(item for item in payload["checks"] if item["id"] == "office_isolation")
        self.assertIn("checks=5", office_isolation["summary"])
        self.assertIn("failures=0", office_isolation["summary"])
        self.assertNotIn("sk-", completed.stdout.lower())

    def test_markdown_is_release_operator_readable(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_release_readiness.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Release Readiness Audit", completed.stdout)
        self.assertIn("Safe for public release", completed.stdout)
        self.assertIn("github_download=ready:14/14", completed.stdout)
        self.assertIn("deployment_modes=3", completed.stdout)
        self.assertIn("private_boundaries=10", completed.stdout)
        self.assertIn("Productization objective coverage", completed.stdout)
        self.assertIn("Model configuration guidance", completed.stdout)
        self.assertIn("offices=2; comic_ladder=3", completed.stdout)
        self.assertIn("Developer post-change checklist", completed.stdout)
        self.assertIn("skip_release=True", completed.stdout)
        self.assertIn("GitHub release evidence contract", completed.stdout)
        self.assertIn("artifact=no-key-release-evidence", completed.stdout)
        self.assertIn("Public docs readability", completed.stdout)
        self.assertIn("Backend-free static showcase export", completed.stdout)
        self.assertIn("Portfolio showcase copy sync", completed.stdout)
        self.assertIn("AI comic Word canvas delivery", completed.stdout)
        self.assertIn("AI comic downstream handoff", completed.stdout)
        self.assertIn("AI comic production quality benchmark", completed.stdout)
        self.assertIn("AI comic real production claim boundary", completed.stdout)
        self.assertIn("AI comic production acceptance card", completed.stdout)
        self.assertIn("AI comic real quality upgrade plan", completed.stdout)
        self.assertIn("Public AI comic trace bundle", completed.stdout)
        self.assertIn("Office schema gate registry", completed.stdout)
        self.assertIn("bindings=11/11", completed.stdout)
        self.assertIn("Office recovery registry", completed.stdout)
        self.assertIn("bindings=12/12", completed.stdout)
        self.assertIn("Future office backlog boundary", completed.stdout)
        self.assertIn("AI comic handoff inventory", completed.stdout)
        self.assertIn("Research office staged delivery", completed.stdout)
        self.assertIn("Office isolation", completed.stdout)
        self.assertIn("Secret and runtime artifact scan", completed.stdout)
        self.assertIn("interview_script=4/4", completed.stdout)
        self.assertIn("reproducibility=5/5", completed.stdout)
        self.assertIn("fast_review=5/5", completed.stdout)
        self.assertIn("quick_start=5/5", completed.stdout)
        self.assertIn("badge=safe_public_demo", completed.stdout)
        self.assertIn("downloads=8; catalog=9; fast_review=5/5; reading_guide=9/9; quick_start=5/5; post_run=3/3; visitor_route=7; download_acceptance=9; handoff_recovery=8:regenerate_images; backend=False", completed.stdout)
        self.assertIn("compared=", completed.stdout)
        self.assertIn("mismatched=0", completed.stdout)
        self.assertIn("live_external=True", completed.stdout)
        self.assertIn("prompt_quality=ready", completed.stdout)
        self.assertIn("prompt_issues=0", completed.stdout)
        self.assertIn("research_claim=staged_research_demo", completed.stdout)
        self.assertIn("research_full_auto=False", completed.stdout)
        self.assertIn("failures=0; mode=public_docs_readability", completed.stdout)
        self.assertIn("structured_director_shots=2", completed.stdout)
        self.assertIn("quick_start=5", completed.stdout)
        self.assertIn("claim=demo_structure_verified", completed.stdout)
        self.assertIn("prompt_quality=ready", completed.stdout)
        self.assertIn("prompt_issues=0", completed.stdout)
        self.assertIn("claim_level=demo_structure_only", completed.stdout)
        self.assertIn("public_demo=True; real_downstream=False; downstream=structure_demo_only; claim=demo_structure_only; failures=0; prompt_quality=ready", completed.stdout)
        self.assertIn("target=real_quality_verified", completed.stdout)
        self.assertIn("status=blocked_until_real_model_evidence", completed.stdout)
        self.assertIn("assets=3; images=7; shots=2; claim=demo_structure_only; visual=fixture_only; real_quality=False; supports_real_quality=False", completed.stdout)
        self.assertIn("upgrade_checklist=3", completed.stdout)
        self.assertIn("recovery=regenerate_images", completed.stdout)
        self.assertIn("production_verified=0", completed.stdout)
        self.assertIn("reading_guide=3/3", completed.stdout)
        self.assertIn("handoff=3/3", completed.stdout)
        self.assertIn("claim=staged_research_demo", completed.stdout)
        self.assertIn("full_auto=False", completed.stdout)
        self.assertIn("demo_contract=8", completed.stdout)
        self.assertIn("starter=passed", completed.stdout)
        self.assertIn("starter_items=8", completed.stdout)
        self.assertIn("candidates=4/4; backlog=2", completed.stdout)
        self.assertIn("checks=5; failures=0", completed.stdout)


if __name__ == "__main__":
    unittest.main()
