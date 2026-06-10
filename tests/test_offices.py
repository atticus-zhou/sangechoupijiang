import unittest

from src.offices import get_office, list_offices


class OfficeProfileTests(unittest.TestCase):
    def test_research_office_defines_agent_duties_and_artifacts(self):
        office = get_office("research")

        self.assertEqual(office.id, "research")
        self.assertIn("zhongshu", office.agent_duties)
        self.assertIn("report", office.artifact_types)
        self.assertIn("source_list", office.artifact_types)
        self.assertTrue(office.acceptance_criteria)

    def test_unknown_office_falls_back_to_research(self):
        office = get_office("unknown")

        self.assertEqual(office.id, "research")

    def test_office_list_is_serializable(self):
        offices = list_offices()

        self.assertEqual(offices[0]["id"], "research")
        self.assertIn("artifact_types", offices[0])

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
        self.assertIn("zhongshu", office.agent_duties)
        self.assertTrue(any("独立的 office_id" in item for item in office.acceptance_criteria))


if __name__ == "__main__":
    unittest.main()
