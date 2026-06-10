import unittest

from src.comic_office.production_handoff import build_production_handoff_artifacts


class ComicProductionHandoffTests(unittest.TestCase):
    def test_builds_production_handoff_artifacts_from_comic_package(self):
        result = {
            "comic_package": {
                "title": "The Fallen Healer",
                "confirmed_script": {
                    "title": "The Fallen Healer",
                    "story_draft": "Ah Heng dies after buying supplies for the cultivation team.",
                    "script_hash": "hash-1",
                    "script_version": 2,
                },
                "script_binding": {"confirmed": True, "script_hash": "hash-1", "script_version": 2},
                "characters": [{"id": "char_001", "name": "Ah Heng", "image_prompt": "gentle healer"}],
                "props": [{"id": "prop_001", "name": "osmanthus cake", "image_prompt": "wrapped cake"}],
                "scenes": [{"id": "scene_001", "name": "alley", "image_prompt": "quiet alley"}],
                "shots": [
                    {
                        "id": "shot_001",
                        "beat": "Ah Heng protects the medicine bag.",
                        "characters": ["Ah Heng"],
                        "props": ["medicine bag"],
                        "scene": "alley",
                        "framing": "close-up",
                        "image_prompt": "Ah Heng in the alley, no text",
                        "video_prompt": "slow push-in",
                        "negative_prompt": "text, labels",
                    }
                ],
            }
        }

        artifacts = build_production_handoff_artifacts("task-prod", result)
        by_type = {artifact["artifact_type"]: artifact for artifact in artifacts}

        self.assertIn("production_brief", by_type)
        self.assertIn("dispatch_plan", by_type)
        self.assertIn("asset_registry", by_type)
        self.assertIn("shot_prompt_handoff", by_type)
        self.assertIn("Ah Heng", by_type["asset_registry"]["content"])
        self.assertIn("shot_001", by_type["shot_prompt_handoff"]["content"])
        self.assertIn("Ah Heng in the alley", by_type["shot_prompt_handoff"]["content"])
        self.assertEqual(by_type["production_brief"]["metadata"]["office_id"], "comic_production")
        self.assertEqual(by_type["production_brief"]["metadata"]["script_hash"], "hash-1")


if __name__ == "__main__":
    unittest.main()
