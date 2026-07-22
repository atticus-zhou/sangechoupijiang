import json
import subprocess
import sys
import unittest


class OfficeExtensionGovernanceVerifierTests(unittest.TestCase):
    def test_json_proves_primary_office_can_be_promoted(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_office_extension_governance.py",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        audit = json.loads(completed.stdout)
        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["primary_office_ids"], ["comic_production"])
        self.assertIn("required_demo_contract", audit)
        self.assertIn("extension_blueprint", audit)
        self.assertIn("protocol_doc", audit)
        self.assertEqual(audit["protocol_doc"]["status"], "passed")
        self.assertEqual(audit["protocol_doc"]["path"], "docs/OFFICE_EXTENSION_PROTOCOL.md")
        self.assertEqual(audit["creation_template_skeleton_audit"]["status"], "passed")
        self.assertTrue(audit["creation_template_skeleton_audit"]["recovery_has_preserve_clear"])
        self.assertTrue(audit["creation_template_skeleton_audit"]["claim_report_ready"])
        self.assertGreaterEqual(audit["creation_template_skeleton_audit"]["downloadable_deliverable_count"], 1)
        self.assertEqual(audit["starter_checklist_audit"]["status"], "passed")
        self.assertEqual(audit["starter_checklist_audit"]["count"], 8)
        self.assertEqual(audit["starter_checklist_audit"]["doc_path"], "docs/NEW_OFFICE_STARTER_CHECKLIST.md")
        self.assertFalse(audit["starter_checklist_audit"]["doc_missing_markers"])
        self.assertIn("isolation", audit["starter_checklist_audit"]["phases"])
        self.assertIn("public_demo", audit["starter_checklist_audit"]["phases"])
        self.assertEqual(audit["future_extension_audit"]["status"], "passed")
        self.assertEqual(audit["future_extension_audit"]["candidate_count"], 4)
        self.assertEqual(audit["future_extension_audit"]["backlog_count"], 2)
        self.assertIn("short_video_ads", audit["future_extension_audit"]["candidate_ids"])
        self.assertIn("future_schema_validators", audit["future_extension_audit"]["backlog_ids"])
        self.assertEqual(audit["launch_matrix_summary"]["office_count"], 3)
        self.assertEqual(audit["launch_matrix_summary"]["public_ready_count"], 2)
        self.assertEqual(audit["launch_matrix_summary"]["primary_allowed_count"], 1)
        launch_by_office = {item["office_id"]: item for item in audit["launch_matrix"]}
        self.assertTrue(launch_by_office["comic_production"]["can_show_publicly"])
        self.assertTrue(launch_by_office["comic_production"]["primary_allowed"])
        self.assertFalse(launch_by_office["comic"]["can_show_publicly"])
        self.assertIn("legacy_migration_required", launch_by_office["comic"]["blocked_by"])
        package_files = {
            item["file"] for item in audit["extension_blueprint"]["minimum_implementation_package"]
        }
        self.assertIn("src/offices.py", package_files)
        self.assertIn("src/web/app.py", package_files)
        self.assertIn("src/office_preflight.py", package_files)
        self.assertIn("deliverable_reading_guide", audit["required_demo_contract"])
        self.assertIn("interview_demo_script", audit["required_demo_contract"])
        self.assertIn("post_run_validation", audit["required_demo_contract"])
        self.assertIn("public_claim_report", audit["required_demo_contract"])
        self.assertIn("public_safety_boundaries", audit["required_demo_contract"])
        step_ids = {step["id"] for step in audit["extension_blueprint"]["implementation_steps"]}
        self.assertIn("register_profile", step_ids)
        self.assertIn("isolate_runtime", step_ids)
        self.assertIn("build_no_key_demo", step_ids)

        by_office = {item["office_id"]: item for item in audit["offices"]}
        self.assertTrue(by_office["comic_production"]["primary_allowed"])
        self.assertFalse(by_office["comic"]["can_be_primary"])
        self.assertEqual(by_office["comic"]["legacy_migration"]["target_office_id"], "comic_production")
        self.assertIn("comic_production", by_office["comic"]["legacy_migration"]["action"])

    def test_markdown_lists_four_primary_standards(self):
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/verify_office_extension_governance.py",
                "--format",
                "markdown",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Office Extension Governance Audit", completed.stdout)
        self.assertIn("Required Demo Contract", completed.stdout)
        self.assertIn("Extension Blueprint", completed.stdout)
        self.assertIn("Minimum Implementation Package", completed.stdout)
        self.assertIn("New Office Starter Checklist", completed.stdout)
        self.assertIn("Future Office Candidates", completed.stdout)
        self.assertIn("Future Backlog Audit", completed.stdout)
        self.assertIn("Office Launch Matrix", completed.stdout)
        self.assertIn("Public ready: `2/3`", completed.stdout)
        self.assertIn("legacy_migration_required", completed.stdout)
        self.assertIn("short_video_ads", completed.stdout)
        self.assertIn("future_schema_validators", completed.stdout)
        self.assertIn("Starter Checklist Audit", completed.stdout)
        self.assertIn("define_user_job", completed.stdout)
        self.assertIn("scope_runtime_state", completed.stdout)
        self.assertIn("wire_release_gate", completed.stdout)
        self.assertIn("Status: `passed`", completed.stdout)
        self.assertIn("Items: `8`", completed.stdout)
        self.assertIn("Document: `docs/NEW_OFFICE_STARTER_CHECKLIST.md`", completed.stdout)
        self.assertIn("Register an OfficeProfile", completed.stdout)
        self.assertIn("src/office_preflight.py", completed.stdout)
        self.assertIn("Isolate runtime state", completed.stdout)
        self.assertIn("Build a no-key demo contract", completed.stdout)
        self.assertIn("verify_release_readiness.py", completed.stdout)
        self.assertIn("Human-Readable Protocol", completed.stdout)
        self.assertIn("Creation Template Skeleton Audit", completed.stdout)
        self.assertIn("Recovery preserves/clears: `True`", completed.stdout)
        self.assertIn("Claim report ready: `True`", completed.stdout)
        self.assertIn("OFFICE_EXTENSION_PROTOCOL.md", completed.stdout)
        self.assertIn("viewer_path", completed.stdout)
        self.assertIn("downloadable_deliverables", completed.stdout)
        self.assertIn("deliverable_reading_guide", completed.stdout)
        self.assertIn("interview_demo_script", completed.stdout)
        self.assertIn("post_run_validation", completed.stdout)
        self.assertIn("public_claim_report", completed.stdout)
        self.assertIn("真实任务跑完后", completed.stdout)
        self.assertIn("public_safety_boundaries", completed.stdout)
        self.assertIn("可展示", completed.stdout)
        self.assertIn("可试用", completed.stdout)
        self.assertIn("可交付", completed.stdout)
        self.assertIn("可追溯", completed.stdout)
        self.assertIn("comic_production", completed.stdout)
        self.assertIn("Migration", completed.stdout)
        self.assertIn("旧 comic", completed.stdout)


if __name__ == "__main__":
    unittest.main()
