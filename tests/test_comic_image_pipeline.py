import asyncio
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.comic_quality import ComicImageReview
from src.image_generation import GeneratedImage
from src.image_generation import ImageGenerationError
from src.llm.providers import ModelConfig
from src.web.app import _generate_comic_images


class ComicImagePipelineTests(unittest.TestCase):
    def test_failed_review_retries_with_revised_prompt_and_records_quality(self):
        result = {
            "comic_package": {
                "characters": [{
                    "id": "char_01",
                    "image_prompt": "主角设定图，灰黑制服，无人机背包",
                }],
                "scenes": [],
                "shots": [],
            }
        }
        prompts = []

        def fake_generate(config, prompt, output_dir, title):
            prompts.append(prompt)
            path = Path(output_dir) / f"{title}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
            return GeneratedImage(
                title=title,
                prompt=prompt,
                path=str(path),
                provider="doubao",
                model="doubao-seedream-5-0-260128",
                size="2K",
            )

        reviews = [
            ComicImageReview(
                status="fail",
                score=55,
                issues=["缺少无人机背包"],
                revision_prompt="补上无人机背包，保持灰黑制服",
                raw='{"status":"fail"}',
            ),
            ComicImageReview(
                status="pass",
                score=91,
                issues=[],
                revision_prompt="",
                raw='{"status":"pass"}',
            ),
        ]

        manager = Mock()
        manager.get_model_config.side_effect = lambda agent, office_id="": ModelConfig(
            provider="doubao" if agent == "gongbu" else "dashscope",
            model="doubao-seedream-5" if agent == "gongbu" else "qwen-vl-max",
            api_key="key",
        )

        with patch("src.web.app.config_manager", manager), \
            patch("src.web.app.generate_doubao_image", side_effect=fake_generate), \
            patch("src.web.app.review_comic_image", side_effect=reviews), \
            patch.dict("os.environ", {"COMIC_IMAGE_LIMIT": "1", "COMIC_IMAGE_MAX_ATTEMPTS": "2"}):
            artifacts = asyncio.run(_generate_comic_images("task-1", "ws-1", result))

        generated = [a for a in artifacts if a["artifact_type"] == "generated_image"]
        report = [a for a in artifacts if a["artifact_type"] == "image_quality_report"]

        self.assertEqual(len(generated), 1)
        self.assertEqual(len(report), 1)
        self.assertEqual(len(prompts), 2)
        self.assertIn("第2次修正", prompts[1])
        self.assertEqual(generated[0]["metadata"]["quality_review"]["status"], "pass")
        self.assertEqual(generated[0]["metadata"]["attempts"], 2)
        self.assertIn("质检结果：pass", generated[0]["content"])

    def test_transient_generation_error_retries_before_recording_error(self):
        result = {
            "comic_package": {
                "characters": [{
                    "id": "char_01",
                    "image_prompt": "主角设定图，灰黑制服",
                }],
                "scenes": [],
                "shots": [],
            }
        }
        calls = {"count": 0}

        def fake_generate(config, prompt, output_dir, title):
            calls["count"] += 1
            if calls["count"] == 1:
                raise ImageGenerationError("Remote end closed connection without response")
            path = Path(output_dir) / f"{title}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
            return GeneratedImage(
                title=title,
                prompt=prompt,
                path=str(path),
                provider="doubao",
                model="doubao-seedream-5-0-260128",
            )

        manager = Mock()
        manager.get_model_config.side_effect = lambda agent, office_id="": ModelConfig(
            provider="doubao" if agent == "gongbu" else "dashscope",
            model="doubao-seedream-5" if agent == "gongbu" else "qwen-vl-max",
            api_key="key",
        )

        with patch("src.web.app.config_manager", manager), \
            patch("src.web.app.generate_doubao_image", side_effect=fake_generate), \
            patch("src.web.app.review_comic_image", return_value=ComicImageReview(status="pass", score=90)), \
            patch.dict("os.environ", {"COMIC_IMAGE_LIMIT": "1", "COMIC_IMAGE_MAX_ATTEMPTS": "2"}):
            artifacts = asyncio.run(_generate_comic_images("task-2", "ws-2", result))

        self.assertEqual(calls["count"], 2)
        self.assertEqual(len([a for a in artifacts if a["artifact_type"] == "generated_image"]), 1)
        self.assertEqual(len([a for a in artifacts if a["artifact_type"] == "image_generation_error"]), 0)


if __name__ == "__main__":
    unittest.main()
