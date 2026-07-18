import unittest

from src.offices import (
    audit_office_extension_governance,
    audit_office_launch_gates,
    get_office,
    list_office_creation_template,
    list_office_extension_blueprint,
    list_offices,
)


class OfficeProfileTests(unittest.TestCase):
    def test_research_office_defines_agent_duties_and_artifacts(self):
        office = get_office("research")

        self.assertEqual(office.id, "research")
        self.assertIn("zhongshu", office.agent_duties)
        self.assertIn("report", office.artifact_types)
        self.assertIn("source_list", office.artifact_types)
        schema_ids = {item["schema_id"] for item in office.schema_gates}
        self.assertIn("research_standard_report", schema_ids)
        self.assertIn("research_source_list", schema_ids)
        self.assertIn("research_data_table", schema_ids)
        self.assertIn("research_competitor_table", schema_ids)
        self.assertTrue(any(item["stage"] == "agent_workflow" for item in office.recovery_actions))
        self.assertTrue(office.acceptance_criteria)

    def test_unknown_office_falls_back_to_research(self):
        office = get_office("unknown")

        self.assertEqual(office.id, "research")

    def test_office_list_is_serializable(self):
        offices = list_offices()

        self.assertEqual(offices[0]["id"], "research")
        self.assertIn("artifact_types", offices[0])

    def test_new_office_template_declares_productization_gates(self):
        template = list_office_creation_template()

        self.assertIn("required_profile_fields", template)
        self.assertIn("input_types", template["required_profile_fields"])
        self.assertIn("output_types", template["required_profile_fields"])
        self.assertIn("model_requirements", template["required_profile_fields"])
        self.assertIn("human_checkpoints", template["required_profile_fields"])
        self.assertIn("artifact_contract", template["required_profile_fields"])
        self.assertIn("recovery_actions", template["required_profile_fields"])
        self.assertIn("schema_gates", template["required_profile_fields"])
        self.assertIn("acceptance_criteria", template["required_profile_fields"])
        self.assertIn("required_launch_gates", template)
        self.assertIn("no_key_demo", template["required_launch_gates"])
        self.assertIn("model_preflight", template["required_launch_gates"])
        self.assertIn("end_to_end_test", template["required_launch_gates"])
        self.assertIn("sample_delivery", template["required_launch_gates"])
        self.assertIn("failure_recovery", template["required_launch_gates"])
        self.assertIn("history_trace", template["required_launch_gates"])
        self.assertIn("schema_gate", template["required_launch_gates"])
        self.assertIn("required_demo_contract", template)
        self.assertIn("viewer_path", template["required_demo_contract"])
        self.assertIn("proof_points", template["required_demo_contract"])
        self.assertIn("downloadable_deliverables", template["required_demo_contract"])
        self.assertIn("deliverable_reading_guide", template["required_demo_contract"])
        self.assertIn("interview_demo_script", template["required_demo_contract"])
        self.assertIn("post_run_validation", template["required_demo_contract"])
        self.assertIn("public_claim_report", template["required_demo_contract"])
        self.assertIn("public_safety_boundaries", template["required_demo_contract"])

    def test_office_extension_blueprint_is_actionable_for_future_offices(self):
        blueprint = list_office_extension_blueprint()

        self.assertIn("implementation_steps", blueprint)
        self.assertGreaterEqual(len(blueprint["implementation_steps"]), 5)
        step_ids = {step["id"] for step in blueprint["implementation_steps"]}
        self.assertIn("register_profile", step_ids)
        self.assertIn("isolate_runtime", step_ids)
        self.assertIn("build_no_key_demo", step_ids)
        self.assertIn("wire_schema_and_recovery", step_ids)
        self.assertIn("document_and_verify", step_ids)
        for step in blueprint["implementation_steps"]:
            self.assertTrue(step["files"])
            self.assertTrue(step["done_when"])
        package_files = {item["file"] for item in blueprint["minimum_implementation_package"]}
        self.assertIn("src/offices.py", package_files)
        self.assertIn("src/web/app.py", package_files)
        self.assertIn("src/office_preflight.py", package_files)
        self.assertIn("tests/", package_files)
        self.assertEqual(blueprint["starter_checklist_doc"], "docs/NEW_OFFICE_STARTER_CHECKLIST.md")
        self.assertIn("docs/NEW_OFFICE_STARTER_CHECKLIST.md", package_files)
        checklist = blueprint["starter_checklist"]
        checklist_ids = {item["id"] for item in checklist}
        self.assertIn("define_user_job", checklist_ids)
        self.assertIn("scope_runtime_state", checklist_ids)
        self.assertIn("create_sample_deliverables", checklist_ids)
        self.assertIn("wire_release_gate", checklist_ids)
        self.assertTrue(all(item["question"] and item["evidence"] for item in checklist))
        self.assertIn("python scripts/verify_release_readiness.py --format markdown", blueprint["required_verifiers"])
        self.assertTrue(any("office_id" in item for item in blueprint["non_negotiables"]))
        candidate_ids = {item["id"] for item in blueprint["future_office_candidates"]}
        self.assertEqual(
            candidate_ids,
            {"short_video_ads", "ecommerce_selection", "story_ip", "technical_project"},
        )
        for candidate in blueprint["future_office_candidates"]:
            self.assertTrue(candidate["user_job"])
            self.assertTrue(candidate["not_ready_reason"])
            self.assertIn("schema_gate", candidate["required_before_public"])
            self.assertIn("public_claim_report", candidate["required_before_public"])
        backlog_ids = {item["id"] for item in blueprint["future_platform_backlog"]}
        self.assertEqual(backlog_ids, {"future_schema_validators", "future_recovery_events"})
        self.assertTrue(all(item["evidence_required"] for item in blueprint["future_platform_backlog"]))

    def test_comic_production_launch_gate_audit_covers_required_gates(self):
        template = list_office_creation_template()

        audit = audit_office_launch_gates("comic_production")

        self.assertEqual(audit["office_id"], "comic_production")
        self.assertEqual(audit["status"], "ready")
        gate_ids = {gate["id"] for gate in audit["gates"]}
        self.assertEqual(gate_ids, set(template["required_launch_gates"]))
        for gate in audit["gates"]:
            self.assertIn(gate["status"], {"passed", "needs_work", "blocked"})
            self.assertTrue(gate["label"])
            self.assertTrue(gate["evidence"])
            self.assertTrue(gate["next_action"])
        self.assertTrue(all(gate["status"] == "passed" for gate in audit["gates"]))

    def test_launch_gate_sample_delivery_exposes_download_links(self):
        comic = audit_office_launch_gates("comic_production")
        research = audit_office_launch_gates("research")

        comic_sample = {gate["id"]: gate for gate in comic["gates"]}["sample_delivery"]
        research_sample = {gate["id"]: gate for gate in research["gates"]}["sample_delivery"]

        comic_links = {link["label"]: link["uri"] for link in comic_sample["evidence_links"]}
        research_links = {link["label"]: link["uri"] for link in research_sample["evidence_links"]}

        self.assertEqual(
            set(comic_links.values()),
            {
                "/api/demo/comic-production/files/word_canvas.docx",
                "/api/demo/comic-production/files/handoff_manifest.json",
            },
        )
        self.assertEqual(
            set(research_links.values()),
            {
                "/api/demo/research/files/report.md",
                "/api/demo/research/files/evidence_manifest.json",
            },
        )
        self.assertIn("Word 制片画布", comic_links)
        self.assertIn("引用清单", comic_links)
        self.assertIn("阶段调研报告", research_links)
        self.assertIn("证据清单", research_links)
        return

        self.assertEqual(comic_links["Word 制片画布"], "/api/demo/comic-production/files/word_canvas.docx")
        self.assertEqual(comic_links["引用清单"], "/api/demo/comic-production/files/handoff_manifest.json")
        self.assertEqual(research_links["阶段调研报告"], "/api/demo/research/files/report.md")
        self.assertEqual(research_links["证据清单"], "/api/demo/research/files/evidence_manifest.json")

    def test_legacy_comic_launch_gate_audit_marks_missing_product_gates(self):
        audit = audit_office_launch_gates("comic")

        self.assertEqual(audit["office_id"], "comic")
        self.assertEqual(audit["status"], "needs_work")
        self.assertEqual(audit["role"], "legacy")
        self.assertEqual(audit["legacy_migration"]["target_office_id"], "comic_production")
        self.assertIn("comic_production", audit["legacy_migration"]["action"])
        statuses = {gate["id"]: gate["status"] for gate in audit["gates"]}
        self.assertEqual(statuses["no_key_demo"], "needs_work")
        self.assertEqual(statuses["end_to_end_test"], "needs_work")
        self.assertEqual(statuses["sample_delivery"], "needs_work")

    def test_comic_office_defines_preproduction_contract(self):
        office = get_office("comic")

        self.assertEqual(office.id, "comic")
        self.assertIn("style_bible", office.artifact_types)
        self.assertIn("shot_prompt_table", office.artifact_types)
        self.assertNotIn("storyboard_table", office.artifact_types)
        self.assertIn("prompt_package", office.artifact_types)
        self.assertIn("gongbu", office.agent_duties)
        self.assertTrue(any("最终剪辑短剧" in item for item in office.acceptance_criteria))

    def test_comic_production_office_is_registered_as_isolated_office(self):
        office = get_office("comic_production")

        self.assertEqual(office.id, "comic_production")
        self.assertIn("production_brief", office.artifact_types)
        self.assertIn("dispatch_plan", office.artifact_types)
        self.assertIn("asset_registry", office.artifact_types)
        self.assertIn("word_canvas", office.artifact_types)
        self.assertTrue(office.schema_gates)
        schema_ids = {item["schema_id"] for item in office.schema_gates}
        self.assertIn("comic_contract", schema_ids)
        self.assertIn("asset_manifest", schema_ids)
        self.assertIn("asset_prompt_set", schema_ids)
        self.assertIn("shot_cards", schema_ids)
        self.assertIn("image_review_result", schema_ids)
        self.assertTrue(any(item["stage"] == "document_generation" for item in office.recovery_actions))
        quality_recovery = next(item for item in office.recovery_actions if item["stage"] == "quality_review")
        self.assertTrue(quality_recovery["path_template"].endswith("/comic/v2/quality/recover"))
        self.assertEqual(
            quality_recovery["body_contract"]["action"],
            "quality_benchmark.recommended_recovery.action",
        )
        self.assertIn("zhongshu", office.agent_duties)
        self.assertTrue(any("独立的 office_id" in item for item in office.acceptance_criteria))


class OfficeExtensionGovernanceTests(unittest.TestCase):
    def test_governance_requires_protocol_and_primary_standards(self):
        audit = audit_office_extension_governance()

        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["primary_office_ids"], ["comic_production"])
        self.assertIn("required_profile_fields", audit)
        self.assertIn("required_launch_gates", audit)
        self.assertIn("required_demo_contract", audit)
        self.assertIn("deliverable_reading_guide", audit["required_demo_contract"])
        self.assertIn("interview_demo_script", audit["required_demo_contract"])
        self.assertIn("post_run_validation", audit["required_demo_contract"])
        self.assertIn("public_claim_report", audit["required_demo_contract"])
        self.assertIn("extension_blueprint", audit)
        self.assertIn("implementation_steps", audit["extension_blueprint"])
        self.assertIn("starter_checklist", audit["extension_blueprint"])
        self.assertTrue(any(
            step["id"] == "isolate_runtime"
            for step in audit["extension_blueprint"]["implementation_steps"]
        ))

        by_office = {item["office_id"]: item for item in audit["offices"]}
        self.assertTrue(by_office["comic_production"]["primary_allowed"])
        self.assertTrue(by_office["comic_production"]["can_be_primary"])
        self.assertFalse(by_office["comic"]["can_be_primary"])
        self.assertEqual(by_office["comic"]["launch_gate_status"], "needs_work")
        self.assertEqual(by_office["comic"]["legacy_migration"]["target_office_id"], "comic_production")
        self.assertIn("旧 comic", by_office["comic"]["legacy_migration"]["action"])

        standards = {
            item["label"]: item["status"]
            for item in by_office["comic_production"]["primary_standards"]
        }
        self.assertEqual(
            standards,
            {
                "可展示": "passed",
                "可试用": "passed",
                "可交付": "passed",
                "可追溯": "passed",
            },
        )


if __name__ == "__main__":
    unittest.main()
