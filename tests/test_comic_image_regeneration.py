import unittest

from src.web.app import _build_comic_regeneration_spec, _extract_comic_prompt_from_content


class ComicImageRegenerationTests(unittest.TestCase):
    def test_extract_prompt_from_generated_image_content(self):
        content = "\n".join([
            "# char_01 人物设定图",
            "",
            "## 生图提示词",
            "主角设定图，灰黑制服，无人机背包",
            "",
            "## 刑部视觉检查",
            "未发现明显问题。",
        ])

        self.assertEqual(
            _extract_comic_prompt_from_content(content),
            "主角设定图，灰黑制服，无人机背包",
        )

    def test_regeneration_spec_preserves_metadata_and_adds_instruction(self):
        artifact = {
            "title": "char_01 人物设定图",
            "content": "## 生图提示词\n主角设定图，灰黑制服\n\n## 刑部视觉检查\npass",
            "metadata": {
                "kind": "character",
                "source_id": "char_01",
            },
        }

        spec = _build_comic_regeneration_spec(artifact, "改成短发，更冷峻")

        self.assertEqual(spec["kind"], "character")
        self.assertEqual(spec["source_id"], "char_01")
        self.assertEqual(spec["agent"], "gongbu")
        self.assertIn("主角设定图，灰黑制服", spec["prompt"])
        self.assertIn("改成短发，更冷峻", spec["prompt"])


if __name__ == "__main__":
    unittest.main()
