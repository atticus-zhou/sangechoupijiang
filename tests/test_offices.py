import unittest

from src.offices import get_office, list_office_creation_template, list_offices


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
        self.assertIn("zhongshu", office.agent_duties)
        self.assertTrue(any("独立的 office_id" in item for item in office.acceptance_criteria))


if __name__ == "__main__":
    unittest.main()
