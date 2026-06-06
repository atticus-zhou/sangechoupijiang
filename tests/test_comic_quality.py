import unittest

from src.comic_quality import (
    build_revised_prompt,
    parse_comic_image_review,
    should_retry_image,
)


class ComicImageQualityTests(unittest.TestCase):
    def test_parse_json_review_and_retry_decision(self):
        review = parse_comic_image_review(
            '{"status":"fail","score":62,"issues":["服装颜色漂移","场景不符合提示词"],'
            '"revision_prompt":"保持灰黑制服，加入无人机背包，背景改为昏暗公寓"}'
        )

        self.assertEqual(review.status, "fail")
        self.assertEqual(review.score, 62)
        self.assertTrue(should_retry_image(review))
        self.assertIn("服装颜色漂移", review.issues)

    def test_revised_prompt_preserves_original_and_adds_review_constraints(self):
        review = parse_comic_image_review(
            '{"status":"fail","score":70,"issues":["脸型不稳定"],'
            '"revision_prompt":"保持同一脸型，清晰正脸参考"}'
        )

        revised = build_revised_prompt("主角设定图，灰黑制服", review, attempt=2)

        self.assertIn("主角设定图，灰黑制服", revised)
        self.assertIn("第2次修正", revised)
        self.assertIn("保持同一脸型", revised)
        self.assertIn("脸型不稳定", revised)

    def test_non_json_review_is_kept_as_needs_review(self):
        review = parse_comic_image_review("图片基本可用，但需要人工看一下。")

        self.assertEqual(review.status, "needs_review")
        self.assertEqual(review.score, 0)
        self.assertFalse(should_retry_image(review))
        self.assertIn("图片基本可用", review.raw)


if __name__ == "__main__":
    unittest.main()
