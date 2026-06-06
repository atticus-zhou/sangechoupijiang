import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.image_generation import (
    generate_doubao_image,
    is_image_generation_config,
    normalize_image_model,
)
from src.llm.providers import ModelConfig


class ImageGenerationTests(unittest.TestCase):
    def test_seedream_alias_is_normalized(self):
        config = ModelConfig(provider="doubao", model="doubao-seedream-5")

        self.assertTrue(is_image_generation_config(config))
        self.assertEqual(normalize_image_model(config), "doubao-seedream-5-0-260128")

    def test_doubao_b64_response_is_saved_as_file(self):
        png_bytes = b"\x89PNG\r\n\x1a\nfake"
        fake_response = {
            "data": [{
                "b64_json": base64.b64encode(png_bytes).decode("ascii"),
                "size": "1024x1024",
            }]
        }
        config = ModelConfig(provider="doubao", model="doubao-seedream-5", api_key="secret-key")

        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.image_generation._post_json", return_value=fake_response):
                image = generate_doubao_image(
                    config,
                    prompt="主角设定图",
                    output_dir=Path(tmp),
                    title="char_01 人物设定图",
                )

            self.assertEqual(Path(image.path).read_bytes(), png_bytes)
            self.assertEqual(image.model, "doubao-seedream-5-0-260128")
            self.assertEqual(image.provider, "doubao")


if __name__ == "__main__":
    unittest.main()
