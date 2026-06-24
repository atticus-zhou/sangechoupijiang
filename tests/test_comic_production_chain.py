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
        self.assertIn("shot_prompt_handoff", departments["bingbu"]["outputs"])
        self.assertEqual(departments["xingbu"]["status"], "completed")
        self.assertEqual(state["overall_status"], "ready_for_handoff")
        self.assertEqual(state["current_department"], "礼部")
        self.assertFalse(state["human_action_required"])

    def test_chain_state_marks_asset_review_as_human_checkpoint(self):
        package = {
            "title": "Review Needed",
            "script_binding": {"confirmed": True, "script_hash": "hash-review", "script_version": 1},
            "confirmed_script": {"story_draft": "Story exists."},
            "characters": [{"id": "char_001", "name": "A"}],
            "props": [{"id": "prop_001", "name": "P"}],
            "scenes": [{"id": "scene_001", "name": "S"}],
            "shots": [{"id": "shot_001", "image_prompt": "frame", "video_prompt": "move"}],
        }

        state = build_production_chain_state(package, asset_review_status="pending")

        self.assertEqual(state["overall_status"], "waiting_for_asset_review")
        self.assertEqual(state["current_department"], "门下省")
        self.assertTrue(state["human_action_required"])
        self.assertIn("审核资产拆解包", state["next_action"])
        departments = {item["department_id"]: item for item in state["departments"]}
        self.assertEqual(departments["menxia"]["ui_status"], "waiting_for_human")
        self.assertIn("审核资产拆解包", departments["menxia"]["human_checkpoint"])

    def test_chain_state_marks_returned_asset_review_as_revision_checkpoint(self):
        package = {
            "title": "Returned Review",
            "script_binding": {"confirmed": True, "script_hash": "hash-returned", "script_version": 1},
            "confirmed_script": {"story_draft": "Story exists."},
            "characters": [{"id": "char_001", "name": "A"}],
            "props": [{"id": "prop_001", "name": "P"}],
            "scenes": [{"id": "scene_001", "name": "S"}],
            "shots": [{"id": "shot_001", "image_prompt": "frame", "video_prompt": "move"}],
        }

        state = build_production_chain_state(package, asset_review_status="revision_requested")

        self.assertEqual(state["overall_status"], "waiting_for_asset_revision")
        self.assertEqual(state["current_department"], "中书省/门下省")
        self.assertTrue(state["human_action_required"])
        self.assertIn("重新拆解", state["next_action"])
        departments = {item["department_id"]: item for item in state["departments"]}
        self.assertEqual(departments["zhongshu"]["ui_status"], "waiting_for_human")
        self.assertIn("退回意见", departments["zhongshu"]["human_checkpoint"])

    def test_quality_gate_blocks_when_shot_prompts_or_assets_are_missing(self):
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
        self.assertIn("shot prompts missing", gate["blocking_issues"])
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
            },
        )

        self.assertEqual(gate["status"], "blocked")
        self.assertIn("工部需要生图模型", " ".join(gate["blocking_issues"]))

    def test_visual_reviews_wait_for_human_when_any_image_is_unreviewed_or_low_score(self):
        package = {
            "title": "Visual Review Package",
            "script_binding": {"confirmed": True, "script_hash": "hash-visual", "script_version": 1},
            "confirmed_script": {"story_draft": "Story exists."},
            "characters": [{"id": "char_001"}],
            "props": [{"id": "prop_001"}],
            "scenes": [{"id": "scene_001"}],
            "shots": [{"id": "shot_001", "image_prompt": "frame", "video_prompt": "push in"}],
            "image_quality_summary": {
                "expected": 2,
                "generated": 2,
                "failed": 0,
                "reviews": [
                    {"source_id": "char_001", "status": "pass", "score": 92, "issues": []},
                    {"source_id": "prop_001", "status": "needs_review", "score": 0, "issues": ["未完成自动视觉检查"]},
                ],
            },
        }

        gate = build_production_quality_gate(package)
        state = build_production_chain_state(package, asset_review_status="approved")
        departments = {item["department_id"]: item for item in state["departments"]}

        self.assertEqual(gate["status"], "waiting_for_human")
        self.assertLess(gate["score"], 80)
        self.assertIn("prop_001", " ".join(gate["blocking_issues"]))
        self.assertEqual(state["overall_status"], "waiting_for_visual_review")
        self.assertEqual(departments["xingbu"]["status"], "blocked")
        self.assertEqual(departments["xingbu"]["ui_status"], "waiting_for_human")
        self.assertTrue(state["human_action_required"])

    def test_visual_reviews_block_handoff_when_images_are_missing(self):
        package = {
            "title": "Missing Images",
            "script_binding": {"confirmed": True, "script_hash": "hash-missing", "script_version": 1},
            "confirmed_script": {"story_draft": "Story exists."},
            "characters": [{"id": "char_001"}],
            "props": [{"id": "prop_001"}],
            "scenes": [{"id": "scene_001"}],
            "shots": [{"id": "shot_001", "image_prompt": "frame", "video_prompt": "push in"}],
            "image_quality_summary": {"expected": 2, "generated": 1, "failed": 1, "reviews": []},
        }

        gate = build_production_quality_gate(package)

        self.assertEqual(gate["status"], "blocked")
        self.assertIn("1 image generation failures", gate["blocking_issues"])


if __name__ == "__main__":
    unittest.main()
