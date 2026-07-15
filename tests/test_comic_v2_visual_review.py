import unittest

from src.comic_office.v2.visual_review import (
    build_visual_review_request,
    normalize_baseline_review,
    normalize_visual_review,
)


def review_payload(**overrides):
    scores = {
        "identity_consistency": 92,
        "style_consistency": 90,
        "era_media": 95,
        "spatial_structure": 88,
        "asset_purity": 93,
        "anatomy": 86,
        "purpose_fit": 91,
    }
    scores.update(overrides)
    return {
        "status": "pass",
        "scores": scores,
        "issues": [],
        "revision_prompt": "",
        "evidence": ["人物脸型、服装主色与参考图一致"],
    }


class ComicV2VisualReviewTests(unittest.TestCase):
    def test_review_without_reference_cannot_claim_consistency(self):
        request = build_visual_review_request(
            current_image="current.png",
            reference_images=[],
            visual_bible_summary="古风厚涂，靛青与银白",
            acceptance_criteria=["人物身份一致"],
        )

        result = normalize_visual_review(review_payload(), request)

        self.assertEqual(result.consistency_status, "not_evaluated")
        self.assertEqual(result.status, "needs_review")
        self.assertFalse(result.handoff_ready)
        self.assertIn("缺少批准参考图", result.issues)

    def test_low_identity_score_blocks_handoff(self):
        request = build_visual_review_request(
            "current.png",
            ["char-approved.png"],
            visual_bible_summary="古风厚涂",
            acceptance_criteria=["脸型与服装一致"],
        )

        result = normalize_visual_review(review_payload(identity_consistency=62), request)

        self.assertEqual(result.status, "fail")
        self.assertEqual(result.consistency_status, "fail")
        self.assertFalse(result.handoff_ready)
        self.assertIn("identity_consistency", result.failed_dimensions)

    def test_missing_required_dimension_blocks_handoff(self):
        request = build_visual_review_request(
            "current.png",
            ["scene-approved.png"],
            visual_bible_summary="古风厚涂",
            acceptance_criteria=["空间结构一致"],
        )
        payload = review_payload()
        del payload["scores"]["spatial_structure"]

        result = normalize_visual_review(payload, request)

        self.assertEqual(result.status, "needs_review")
        self.assertFalse(result.handoff_ready)
        self.assertIn("spatial_structure", result.missing_dimensions)

    def test_all_dimensions_pass_with_reference(self):
        request = build_visual_review_request(
            "current.png",
            ["approved.png"],
            previous_accepted_image="previous-shot.png",
            visual_bible_summary="古风厚涂，架空古代",
            acceptance_criteria=["脸型固定", "服装主色固定"],
        )

        result = normalize_visual_review(review_payload(), request)

        self.assertEqual(result.status, "pass")
        self.assertEqual(result.consistency_status, "pass")
        self.assertTrue(result.handoff_ready)
        self.assertEqual(result.reference_count, 2)

    def test_request_labels_image_roles_for_vision_model(self):
        request = build_visual_review_request(
            "current.png",
            ["identity.png", "turnaround.png"],
            previous_accepted_image="previous.png",
            visual_bible_summary="电影级国风厚涂动画",
            acceptance_criteria=["同一人物", "没有现代服装"],
        )

        self.assertEqual(request.image_paths[0], "current.png")
        self.assertEqual(
            request.image_roles,
            ("current", "approved_reference", "approved_reference", "previous_accepted"),
        )
        self.assertIn("当前待检图", request.instruction)
        self.assertIn("批准参考图", request.instruction)
        self.assertIn("上一张合格图", request.instruction)

    def test_first_identity_sheet_can_establish_baseline_without_false_cross_image_claim(self):
        request = build_visual_review_request(
            "character-three-view.png",
            [],
            visual_bible_summary="电影级国风厚涂动画",
            acceptance_criteria=["三视图内部脸型一致", "纯白干净背景"],
        )

        result = normalize_baseline_review(review_payload(), request)

        self.assertEqual(result.status, "pass")
        self.assertEqual(result.consistency_status, "baseline_established")
        self.assertTrue(result.handoff_ready)
        self.assertNotIn("缺少批准参考图", result.issues)

    def test_review_request_carries_production_role_and_background_policy(self):
        request = build_visual_review_request(
            "current.png",
            ["identity.png"],
            visual_bible_summary="ancient fantasy style",
            acceptance_criteria=["same character", "clean background"],
            production_role="clean_character_identity_three_view",
            clean_background_required=True,
        )

        self.assertEqual(request.production_role, "clean_character_identity_three_view")
        self.assertTrue(request.clean_background_required)
        self.assertIn("production_role: clean_character_identity_three_view", request.instruction)
        self.assertIn("clean_background_required: True", request.instruction)


if __name__ == "__main__":
    unittest.main()
