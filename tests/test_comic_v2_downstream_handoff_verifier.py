import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path("scripts/verify_comic_v2_downstream_handoff.py")
FIXTURE = Path("tests/fixtures/comic_v2_sample.json")
UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class ComicV2DownstreamHandoffVerifierTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.spec_from_file_location("verify_comic_v2_downstream_handoff", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_fixture_package_is_downstream_handoff_ready(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            result = module.verify_downstream_handoff(FIXTURE, Path(tmp))

        self.assertEqual(result["status"], "passed", result["errors"])
        self.assertTrue(result["downstream_handoff_ready"])
        self.assertEqual(result["asset_count"], 3)
        self.assertEqual(result["image_count"], 7)
        self.assertEqual(result["shot_count"], 2)
        self.assertEqual(result["character_identity_sets"], 1)
        self.assertEqual(result["prop_reference_sets"], 1)
        self.assertEqual(result["scene_spatial_sets"], 1)
        self.assertEqual(result["shot_video_packages"], 2)
        self.assertEqual(result["structured_director_shots"], 2)
        self.assertEqual(result["clean_asset_prompt_sets"], 7)
        self.assertEqual(result["director_prompt_sets"], 2)
        self.assertGreaterEqual(result["lineage_stage_count"], 7)
        self.assertEqual(result["quick_start_step_count"], 5)

    def test_cli_json_exposes_downstream_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixture",
                    str(FIXTURE),
                    "--output-dir",
                    tmp,
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=UTF8_ENV,
            )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["downstream_handoff_ready"])
        self.assertIn("handoff_manifest", payload)
        self.assertEqual(payload["quick_start_step_count"], 5)
        self.assertEqual(payload["errors"], [])

    def test_cli_markdown_is_readable_for_reviewers(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--fixture",
                    str(FIXTURE),
                    "--output-dir",
                    tmp,
                    "--format",
                    "markdown",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=UTF8_ENV,
            )

        self.assertIn("Comic V2 Downstream Handoff Audit", completed.stdout)
        self.assertIn("Output directory:", completed.stdout)
        self.assertIn("Word canvas: `present`", completed.stdout)
        self.assertIn("Handoff manifest: `present`", completed.stdout)
        self.assertIn("Downstream Readiness", completed.stdout)
        self.assertIn("Character identity sets", completed.stdout)
        self.assertIn("Shot video packages", completed.stdout)
        self.assertIn("Clean asset prompt sets", completed.stdout)
        self.assertIn("Director prompt sets", completed.stdout)
        self.assertIn("Structured director shots: 2", completed.stdout)
        self.assertIn("Quick-start playbook: 5 steps", completed.stdout)

    def test_missing_structured_director_fields_block_handoff(self):
        module = self._module()
        shot = {
            "shot_id": "SHOT-01",
            "reference_asset_ids": ["character_01", "scene_01"],
            "first_frame_reference_image": {"image_id": "image_01"},
            "video_prompt_block": "首帧参考、故事目的、动作链、表演意图、摄影、灯光。严格继承参考资产。",
            "negative_prompt_block": "禁止资产身份漂移；禁止动作顺序混乱",
            "execution_steps": ["绑定首帧", "粘贴提示词", "检查结果"],
            "acceptance_criteria": ["资产一致", "动作正确", "镜头可用"],
            "retry_strategy": "减少角色数量后重试",
        }

        failures = module._shot_handoff_failures(
            [shot],
            {"character_01", "scene_01"},
            {"image_01"},
        )

        self.assertTrue(any("structured director execution missing fields" in item for item in failures))

    def test_missing_shot_story_purpose_blocks_handoff(self):
        module = self._module()
        shot = {
            "shot_id": "SHOT-01",
            "reference_asset_ids": ["character_01"],
            "first_frame_reference_image": {
                "image_id": "image_01",
                "asset_id": "character_01",
                "file": "character_01_three_view.png",
                "image_kind": "three_view",
            },
            "reference_asset_chain": [
                {
                    "asset_id": "character_01",
                    "asset_type": "character",
                    "name": "林昭",
                    "first_frame_image_id": "image_01",
                    "first_frame_file": "character_01_three_view.png",
                }
            ],
            "video_prompt_block": "首帧参考、动作链、表演意图、摄影、灯光。严格继承参考资产。",
            "negative_prompt_block": "禁止资产身份漂移；禁止动作顺序混乱",
            "execution_steps": ["绑定首帧", "粘贴提示词", "检查结果"],
            "acceptance_criteria": ["资产一致", "动作正确", "镜头可用"],
            "retry_strategy": "减少角色数量后重试",
            "director_execution": {
                "contract_version": 1,
                "style_id": "style_01",
                "style_version": 1,
                "first_frame_image_id": "image_01",
                "reference_asset_ids": ["character_01"],
                "action_chain": ["抬头", "停住"],
                "performance_intent": "克制震惊",
                "framing": "特写",
                "camera_movement": "固定机位",
                "lighting": "冷光",
                "dialogue": "林昭：哥？",
                "sound": "灯花低鸣",
            },
            "action_chain": ["抬头", "停住"],
        }

        failures = module._shot_handoff_failures([shot], {"character_01"}, {"image_01"})

        self.assertTrue(any("missing shot story_purpose" in item for item in failures))

    def test_incomplete_first_frame_reference_blocks_handoff(self):
        module = self._module()
        shot = {
            "shot_id": "SHOT-01",
            "reference_asset_ids": ["character_01"],
            "first_frame_reference_image": {"image_id": "image_01"},
            "reference_asset_chain": [
                {
                    "asset_id": "character_01",
                    "asset_type": "character",
                    "name": "林昭",
                    "first_frame_image_id": "image_01",
                    "first_frame_file": "character_01_three_view.png",
                }
            ],
            "video_prompt_block": "首帧参考、故事目的、动作链、表演意图、摄影、灯光。严格继承参考资产。",
            "negative_prompt_block": "禁止资产身份漂移；禁止动作顺序混乱",
            "execution_steps": ["绑定首帧", "粘贴提示词", "检查结果"],
            "acceptance_criteria": ["资产一致", "动作正确", "镜头可用"],
            "retry_strategy": "减少角色数量后重试",
        }

        failures = module._shot_handoff_failures([shot], {"character_01"}, {"image_01"})

        self.assertTrue(any("first-frame reference image missing fields" in item for item in failures))

    def test_incomplete_reference_asset_chain_blocks_handoff(self):
        module = self._module()
        shot = {
            "shot_id": "SHOT-02",
            "reference_asset_ids": ["character_01", "scene_01"],
            "first_frame_reference_image": {
                "image_id": "image_01",
                "asset_id": "character_01",
                "file": "character_01_three_view.png",
                "image_kind": "three_view",
            },
            "reference_asset_chain": [
                {
                    "asset_id": "character_01",
                    "asset_type": "character",
                    "name": "林昭",
                    "first_frame_image_id": "image_01",
                    "first_frame_file": "character_01_three_view.png",
                }
            ],
            "video_prompt_block": "首帧参考、故事目的、动作链、表演意图、摄影、灯光。严格继承参考资产。",
            "negative_prompt_block": "禁止资产身份漂移；禁止动作顺序混乱",
            "execution_steps": ["绑定首帧", "粘贴提示词", "检查结果"],
            "acceptance_criteria": ["资产一致", "动作正确", "镜头可用"],
            "retry_strategy": "减少角色数量后重试",
        }

        failures = module._shot_handoff_failures(
            [shot],
            {"character_01", "scene_01"},
            {"image_01", "image_02"},
        )

        self.assertTrue(any("reference_asset_chain missing assets" in item for item in failures))

    def test_missing_quick_start_steps_block_handoff(self):
        module = self._module()

        failures = module._quick_start_failures(
            [
                {
                    "step": 1,
                    "title": "确认制片画布",
                    "owner": "礼部",
                    "input_refs": ["canvas.docx"],
                    "action": "看 Word",
                    "output": "阅读基准",
                    "acceptance": "文件存在",
                }
            ],
            [{"shot_id": "shot_001"}],
        )

        self.assertTrue(any("at least five" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
