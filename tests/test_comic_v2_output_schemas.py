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


if __name__ == "__main__":
    unittest.main()
