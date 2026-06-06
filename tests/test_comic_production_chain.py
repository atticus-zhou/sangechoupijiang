import unittest

from src.comic_office.production_chain import build_production_chain_state, build_production_quality_gate


class ComicProductionChainTests(unittest.TestCase):
    def test_builds_department_chain_with_dependencies_outputs_and_status(self):
        package = {
            "title": "The Fallen Healer",
            "script_binding": {"confirmed": True, "script_hash": "hash-1", "script_version": 2},
            "confirmed_script": {"story_draft": "Ah Heng dies after buying supplies."},
            "characters": [{"id": "char_001", "name": "Ah Heng"}],
            "props": [{"id": "prop_001", "name": "medicine bag"}],
            "scenes": [{"id": "scene_001", "name": "alley"}],
            "shots": [{"id": "shot_001", "image_prompt": "Ah Heng in alley", "video_prompt": "slow push-in"}],
        }

        state = build_production_chain_state(package)

        self.assertEqual(state["project"], "The Fallen Healer")
        self.assertEqual(state["script_hash"], "hash-1")
        departments = {item["department_id"]: item for item in state["departments"]}
        self.assertEqual(departments["zhongshu"]["status"], "completed")
        self.assertEqual(departments["menxia"]["depends_on"], ["zhongshu"])
        self.assertIn("production_brief", departments["zhongshu"]["outputs"])
        self.assertIn("storyboard_handoff", departments["bingbu"]["outputs"])
        self.assertEqual(departments["xingbu"]["status"], "completed")
        self.assertEqual(state["overall_status"], "ready_for_handoff")

    def test_quality_gate_blocks_when_storyboard_or_assets_are_missing(self):
        package = {
            "title": "Broken Package",
            "script_binding": {"confirmed": True, "script_hash": "hash-2", "script_version": 1},
            "confirmed_script": {"story_draft": "Story exists."},
            "characters": [],
            "props": [],
            "scenes": [],
            "shots": [],
        }

        gate = build_production_quality_gate(package)

        self.assertEqual(gate["status"], "blocked")
        self.assertIn("character assets missing", gate["blocking_issues"])
        self.assertIn("storyboard shots missing", gate["blocking_issues"])
        self.assertLess(gate["score"], 80)

    def test_quality_gate_blocks_when_required_image_model_is_not_configured(self):
        package = {
            "title": "Model Blocked Package",
            "script_binding": {"confirmed": True, "script_hash": "hash-3", "script_version": 1},
            "confirmed_script": {"story_draft": "Story exists."},
            "characters": [{"id": "char_001"}],
            "props": [{"id": "prop_001"}],
            "scenes": [{"id": "scene_001"}],
            "shots": [{"id": "shot_001", "image_prompt": "frame", "video_prompt": "push in"}],
        }

        gate = build_production_quality_gate(
            package,
            model_readiness={
                "gongbu": {"ready": False, "detail": "工部需要生图模型，例如 doubao-seedream-5。"},
                "bingbu": {"ready": False, "detail": "兵部需要生图模型，例如 doubao-seedream-5。"},
            },
        )

        self.assertEqual(gate["status"], "blocked")
        self.assertIn("工部需要生图模型", " ".join(gate["blocking_issues"]))
        self.assertIn("兵部需要生图模型", " ".join(gate["blocking_issues"]))


if __name__ == "__main__":
    unittest.main()
