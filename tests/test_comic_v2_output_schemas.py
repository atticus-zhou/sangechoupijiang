import unittest

from src.comic_office.v2.output_schemas import (
    AgentOutputSchemaError,
    list_agent_output_schemas,
    validate_agent_output_schema,
)


class ComicV2OutputSchemaTests(unittest.TestCase):
    def test_schema_registry_exposes_comic_contract_gates(self):
        schemas = list_agent_output_schemas("comic_production")

        schema_ids = {item["schema_id"] for item in schemas}
        self.assertIn("comic_contract", schema_ids)
        self.assertIn("visual_revision", schema_ids)
        self.assertIn("asset_manifest", schema_ids)
        self.assertIn("asset_manifest_revision", schema_ids)
        self.assertIn("asset_prompt_set", schema_ids)
        self.assertIn("shot_cards", schema_ids)
        contract = next(item for item in schemas if item["schema_id"] == "comic_contract")
        self.assertEqual(contract["office_id"], "comic_production")
        self.assertEqual(contract["owner_agent"], "zhongshu")
        self.assertIn("visual", contract["required_fields"])
        self.assertIn("failure_impact", contract)

    def test_contract_schema_validation_rejects_missing_visual_rules(self):
        payload = self._planner_payload()
        payload["visual"].pop("prohibited_elements")

        with self.assertRaises(AgentOutputSchemaError) as raised:
            validate_agent_output_schema(
                "comic_production",
                "comic_contract",
                payload,
                context={"source_story": self.story, "source_mode": "full_story"},
            )

        self.assertIn("visual bible", str(raised.exception))
        self.assertIn("prohibited_elements", str(raised.exception))

    def test_contract_schema_validation_returns_formal_bundle(self):
        bundle = validate_agent_output_schema(
            "comic_production",
            "comic_contract",
            self._planner_payload(),
            context={"source_story": self.story, "source_mode": "full_story"},
        )

        self.assertEqual(bundle.creative.title, "Moon Archive")
        self.assertEqual(bundle.visual.story_id, bundle.creative.story_id)
        self.assertEqual(bundle.status, "visual_bible_review")

    def test_visual_revision_schema_preserves_story_and_increments_style_version(self):
        current = validate_agent_output_schema(
            "comic_production",
            "comic_contract",
            self._planner_payload(),
            context={"source_story": self.story, "source_mode": "full_story"},
        )
        revised_visual = dict(current.to_dict()["visual"])
        revised_visual["palette"] = ["cold blue", "ink black", "lamp gold"]

        revised = validate_agent_output_schema(
            "comic_production",
            "visual_revision",
            {"visual": revised_visual},
            context={"current_contract": current.to_dict()},
        )

        self.assertEqual(revised.creative.story_id, current.creative.story_id)
        self.assertEqual(revised.creative.source_story, current.creative.source_story)
        self.assertEqual(revised.visual.style_version, current.visual.style_version + 1)

    def test_asset_manifest_schema_validation_returns_formal_manifest(self):
        bundle = validate_agent_output_schema(
            "comic_production",
            "comic_contract",
            self._planner_payload(),
            context={"source_story": self.story, "source_mode": "full_story"},
        )

        manifest = validate_agent_output_schema(
            "comic_production",
            "asset_manifest",
            {"assets": self._asset_payload()},
            context={"contract_bundle": bundle},
        )

        self.assertEqual(manifest.story_id, bundle.creative.story_id)
        self.assertEqual(manifest.review_status, "awaiting_user_review")
        self.assertEqual({item.asset_type for item in manifest.items}, {"character", "prop", "scene"})

    def test_asset_manifest_revision_schema_replaces_manifest_with_version_chain(self):
        bundle = validate_agent_output_schema(
            "comic_production",
            "comic_contract",
            self._planner_payload(),
            context={"source_story": self.story, "source_mode": "full_story"},
        )
        first = validate_agent_output_schema(
            "comic_production",
            "asset_manifest",
            {"assets": self._asset_payload()},
            context={"contract_bundle": bundle},
        )
        revised_assets = self._asset_payload()
        revised_assets.append({
            "asset_type": "prop",
            "name": "lamp",
            "evidence_quote": "lamp",
            "scene_ids": ["scene_02"],
            "story_purpose": "secondary lighting reference for the archive",
            "visual_locks": ["same moonlit material family"],
            "allowed_changes": ["glow strength"],
        })

        second = validate_agent_output_schema(
            "comic_production",
            "asset_manifest_revision",
            {"assets": revised_assets},
            context={"previous_manifest": first, "revision_request": "add the archive key"},
        )

        self.assertEqual(second.version, first.version + 1)
        self.assertEqual(second.previous_manifest_hash, first.manifest_hash)
        self.assertIn("lamp", [item.name for item in second.items])

    def test_asset_prompt_set_schema_returns_valid_prompt_plans(self):
        bundle, manifest = self._bundle_and_manifest()
        asset = manifest.items[0]

        prompts = validate_agent_output_schema(
            "comic_production",
            "asset_prompt_set",
            {"prompts": self._prompt_payload(asset, bundle.visual)},
            context={"asset": asset, "visual": bundle.visual},
        )

        self.assertEqual({prompt.image_kind for prompt in prompts}, set(asset.planned_images))
        self.assertTrue(all(prompt.object_id == asset.asset_id for prompt in prompts))

    def test_shot_cards_schema_returns_valid_shot_cards(self):
        bundle, manifest = self._bundle_and_manifest()
        by_type = {item.asset_type: item for item in manifest.items}

        cards = validate_agent_output_schema(
            "comic_production",
            "shot_cards",
            {
                "shots": [{
                    "shot_id": "SHOT-01",
                    "scene_id": "scene_01",
                    "scene_asset_id": by_type["scene"].asset_id,
                    "character_asset_ids": [by_type["character"].asset_id],
                    "prop_asset_ids": [by_type["prop"].asset_id],
                    "evidence_quote": "cracked moon lamp",
                    "story_beat": "the archivist chooses to burn the cracked moon lamp",
                    "action_chain": ["archivist reaches for the lamp", "the lamp starts to dim"],
                    "performance_intent": "quiet resolve",
                    "framing": "medium close-up, eye-level",
                    "camera_movement": "fixed camera with slow push-in",
                    "lighting": "cold moonlight with warm lamp edge light",
                    "dialogue": "No spoken dialogue",
                    "sound": "soft flame and distant city hush",
                    "retry_strategy": "if identity drifts, lock character and lamp references first",
                    "acceptance_criteria": ["must reference approved asset identities"],
                    "platform_note": "upload asset references before pasting this video prompt",
                }]
            },
            context={"contract_bundle": bundle, "asset_manifest": manifest},
        )

        self.assertEqual(cards[0].reference_asset_ids, (
            by_type["character"].asset_id,
            by_type["prop"].asset_id,
            by_type["scene"].asset_id,
        ))
        self.assertTrue(cards[0].production_ready)

    @property
    def story(self):
        return "A quiet archivist finds a cracked moon lamp and burns it to free the city."

    def _planner_payload(self):
        return {
            "title": "Moon Archive",
            "genre": "fantasy mystery",
            "theme": "memory has a cost",
            "protagonist_goal": "free the city without losing her family memory",
            "main_conflict": "the city trades memory for light",
            "causal_chain": ["find lamp", "trace archive", "burn lamp"],
            "ending": "the archivist burns the lamp and accepts the dawn",
            "episodes": [
                {
                    "episode": 1,
                    "summary": "the cracked lamp points to the archive",
                    "evidence_quote": "cracked moon lamp",
                }
            ],
            "must_keep": ["cracked moon lamp"],
            "must_avoid": ["modern vehicles"],
            "visual": {
                "medium": "cinematic ink animation",
                "era": "fictional ancient city",
                "aspect_ratio": "9:16",
                "palette": ["moon white", "ink black", "rust red"],
                "lighting": "moonlight and warm lamp contrast",
                "camera_language": "restrained tracking shots",
                "character_rules": ["stable face shape"],
                "costume_rules": ["ancient layered robes"],
                "prop_rules": ["worn bronze and paper textures"],
                "architecture_rules": ["wood and stone archive halls"],
                "visual_motifs": ["cracked moon lamp"],
                "prohibited_elements": ["modern cars", "plastic props"],
            },
        }

    def _asset_payload(self):
        return [
            {
                "asset_type": "character",
                "name": "archivist",
                "evidence_quote": "archivist",
                "scene_ids": ["scene_01"],
                "story_purpose": "main character who frees the city",
                "visual_locks": ["plain archive robe"],
                "allowed_changes": ["expression", "pose"],
            },
            {
                "asset_type": "prop",
                "name": "cracked moon lamp",
                "evidence_quote": "cracked moon lamp",
                "scene_ids": ["scene_01", "scene_03"],
                "story_purpose": "core evidence and ending trigger",
                "visual_locks": ["fixed crack pattern"],
                "allowed_changes": ["glow strength"],
            },
            {
                "asset_type": "scene",
                "name": "city",
                "evidence_quote": "city",
                "scene_ids": ["scene_01"],
                "story_purpose": "world affected by the memory trade",
                "visual_locks": ["ancient archive skyline"],
                "allowed_changes": ["crowd density"],
            },
        ]

    def _bundle_and_manifest(self):
        bundle = validate_agent_output_schema(
            "comic_production",
            "comic_contract",
            self._planner_payload(),
            context={"source_story": self.story, "source_mode": "full_story"},
        )
        manifest = validate_agent_output_schema(
            "comic_production",
            "asset_manifest",
            {"assets": self._asset_payload()},
            context={"contract_bundle": bundle},
        )
        return bundle, manifest

    def _prompt_payload(self, asset, visual):
        return [
            {
                "object_id": asset.asset_id,
                "image_kind": image_kind,
                "purpose": "identity_reference",
                "generator_prompt": (
                    f"{asset.name} asset identity reference, asset ID {asset.asset_id}, "
                    f"composition for {image_kind}, lighting matches story, story use for continuity, "
                    f"visual lock {asset.visual_locks[0]}, clean white background"
                ),
                "negative_prompt": ["forbid text", "forbid watermark"],
                "style_id": visual.style_id,
            }
            for image_kind in asset.planned_images
        ]


if __name__ == "__main__":
    unittest.main()
