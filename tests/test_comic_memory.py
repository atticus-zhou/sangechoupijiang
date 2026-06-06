import unittest

from src.comic_office.memory import build_core_memory_vault, build_memory_context_prompt


class ComicMemoryVaultTests(unittest.TestCase):
    def test_core_memory_vault_extracts_stable_story_settings(self):
        session = {
            "idea": "A healer dies in a cultivation team.",
            "genre": "xianxia tragedy",
            "visual_style": "ink wash Chinese fantasy",
            "creative_brief": {
                "story_promise": "The team realizes the ignored healer carried everyone.",
                "main_conflict": "Revenge versus guilt.",
            },
            "script_preview": {
                "title": "The Fallen Healer",
                "story_draft": "Ah Heng buys osmanthus cake for the senior brother, medicine for the second sister, and pills for the junior brother.",
            },
            "user_notes": [
                "The healer must stay gentle, not vengeful.",
                "The team should feel guilt before revenge.",
            ],
        }

        vault = build_core_memory_vault(session)

        self.assertEqual(vault["title"], "The Fallen Healer")
        self.assertEqual(vault["visual_style"], "ink wash Chinese fantasy")
        self.assertIn("ignored healer", vault["story_promise"])
        self.assertIn("healer must stay gentle", " ".join(vault["locked_user_notes"]))
        self.assertLessEqual(len(vault["conversation_window"]), 3)

    def test_memory_context_prompt_is_short_and_usable_for_llm_injection(self):
        vault = build_core_memory_vault({
            "idea": "A paper bride opens her eyes.",
            "visual_style": "dark suspense comic",
            "creative_brief": {"main_conflict": "Expose the ritual before dawn."},
            "user_notes": [f"note {index}" for index in range(10)],
        })

        prompt = build_memory_context_prompt(vault)

        self.assertIn("Core memory vault", prompt)
        self.assertIn("dark suspense comic", prompt)
        self.assertIn("Expose the ritual", prompt)
        self.assertIn("note 9", prompt)
        self.assertNotIn("note 0", prompt)


if __name__ == "__main__":
    unittest.main()
