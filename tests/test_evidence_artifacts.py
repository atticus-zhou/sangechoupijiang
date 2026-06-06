import unittest

from src.evidence_artifacts import build_evidence_artifacts


class EvidenceArtifactTests(unittest.TestCase):
    def test_builds_standard_artifacts_from_extractions(self):
        artifacts = [
            {
                "artifact_id": "shot1",
                "artifact_type": "screenshot_evidence",
                "title": "截图证据：榜单.png",
                "uri": "/files/shot1.png",
                "metadata": {"original_filename": "榜单.png", "note": "无人机榜单"},
            },
            {
                "artifact_id": "ext1",
                "artifact_type": "screenshot_extraction",
                "title": "截图识别结果：榜单.png",
                "uri": "/files/shot1.png",
                "metadata": {"source_artifact_id": "shot1"},
                "content": """
                {
                  "key_numbers": [{"metric": "销量", "value": "1200", "context": "榜单第一", "confidence": "high"}],
                  "competitors": [{"brand": "A品牌", "product": "无人机X", "price": "2999", "sales": "1200"}]
                }
                """,
            },
        ]

        built = build_evidence_artifacts("ws_test", artifacts)
        by_type = {a["artifact_type"]: a for a in built}

        self.assertIn("source_list", by_type)
        self.assertIn("data_table", by_type)
        self.assertIn("competitor_table", by_type)
        self.assertIn("chart_plan", by_type)
        self.assertIn("review_pain_points", by_type)
        self.assertIn("opportunity_map", by_type)
        self.assertIn("quality_report", by_type)
        self.assertIn("销量", by_type["data_table"]["content"])
        self.assertIn("无人机X", by_type["competitor_table"]["content"])
        self.assertEqual(by_type["quality_report"]["metadata"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
