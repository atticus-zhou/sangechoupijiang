import json
import tempfile
import unittest
from pathlib import Path

from src.research_artifacts import build_research_artifacts


COMIC_FIXTURE = Path("tests/fixtures/comic_v2_sample.json")
RESEARCH_FIXTURE = Path("tests/fixtures/research_sample.json")


class SampleProjectFixtureTests(unittest.TestCase):
    def test_comic_v2_sample_project_builds_delivery_canvas(self):
        from scripts.verify_comic_v2_delivery import verify_delivery

        with tempfile.TemporaryDirectory() as tmp:
            result = verify_delivery(COMIC_FIXTURE, Path(tmp))

        self.assertTrue(result["handoff_ready"])
        self.assertGreaterEqual(result["embedded_images"], 1)
        self.assertTrue(result["path"].endswith(".docx"))

    def test_research_sample_project_builds_stage_artifacts(self):
        payload = json.loads(RESEARCH_FIXTURE.read_text(encoding="utf-8"))

        artifacts = build_research_artifacts("sample_research", payload)
        by_type = {item["artifact_type"]: item for item in artifacts}

        for artifact_type in (
            "report",
            "briefing",
            "source_list",
            "screenshot_plan",
            "data_table",
            "competitor_table",
            "chart_plan",
            "opportunity_map",
        ):
            self.assertIn(artifact_type, by_type)
        self.assertIn("民用无人机", by_type["report"]["content"])
        self.assertIn("local://pending", by_type["source_list"]["content"])
        self.assertIn("evidence_01.png", by_type["screenshot_plan"]["content"])


if __name__ == "__main__":
    unittest.main()
