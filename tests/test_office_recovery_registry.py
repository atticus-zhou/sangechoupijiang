import json
import subprocess
import sys
import unittest

from src.office_recovery_registry import (
    audit_office_recovery_registry,
    enriched_recovery_actions,
    list_office_recovery_action_bindings,
)


class OfficeRecoveryRegistryTests(unittest.TestCase):
    def test_recovery_actions_have_preserve_and_clear_contracts(self):
        audit = audit_office_recovery_registry()

        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["error_count"], 0)
        self.assertIn("comic_production", audit["offices_with_actions"])
        self.assertIn("research", audit["offices_with_actions"])
        self.assertGreaterEqual(audit["binding_count"], 12)
        self.assertEqual(audit["binding_count"], audit["passed_binding_count"])

    def test_comic_recovery_contracts_are_visible_to_runtime(self):
        actions = {item["stage"]: item for item in enriched_recovery_actions("comic_production")}

        self.assertIn("quality_review", actions)
        self.assertIn("prompt_package", actions["quality_review"]["preserves"])
        self.assertIn("word_canvas", actions["quality_review"]["clears"])
        self.assertIn("image_generation", actions)
        self.assertIn("fixture_images", actions["image_generation"]["clears"])

    def test_each_binding_is_scoped_and_non_overlapping(self):
        for item in list_office_recovery_action_bindings():
            self.assertEqual(item["status"], "passed", item)
            self.assertTrue(item["path_template"].startswith("/api/"))
            self.assertTrue("{workspace_id}" in item["path_template"] or "{task_id}" in item["path_template"])
            self.assertFalse(set(item["preserves"]) & set(item["clears"]))

    def test_verifier_outputs_registry_evidence(self):
        json_completed = subprocess.run(
            [sys.executable, "scripts/verify_office_recovery_registry.py", "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        audit = json.loads(json_completed.stdout)
        self.assertEqual(audit["status"], "passed")

        markdown_completed = subprocess.run(
            [sys.executable, "scripts/verify_office_recovery_registry.py", "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertIn("Office Recovery Registry Audit", markdown_completed.stdout)
        self.assertIn("comic_production", markdown_completed.stdout)
        self.assertIn("Bindings: `12/12`", markdown_completed.stdout)


if __name__ == "__main__":
    unittest.main()
