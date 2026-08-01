import json
import subprocess
import sys
import unittest

from src.office_schema_registry import (
    audit_office_schema_gate_registry,
    list_office_schema_gate_bindings,
)


class OfficeSchemaRegistryTests(unittest.TestCase):
    def test_declared_schema_gates_bind_to_concrete_validators(self):
        audit = audit_office_schema_gate_registry()

        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["missing_provider_offices"], [])
        self.assertIn("comic_production", audit["provider_offices"])
        self.assertIn("research", audit["provider_offices"])
        self.assertIn("comic_production", audit["offices_with_declared_gates"])
        self.assertIn("research", audit["offices_with_declared_gates"])
        self.assertGreaterEqual(audit["binding_count"], 11)
        self.assertEqual(audit["binding_count"], audit["passed_binding_count"])
        self.assertEqual(audit["missing_schema_ids"], [])
        self.assertEqual(audit["orphan_schema_ids"], [])

    def test_each_binding_has_traceable_office_stage_and_artifact(self):
        bindings = list_office_schema_gate_bindings()

        by_id = {(item["office_id"], item["schema_id"]): item for item in bindings}
        self.assertIn(("comic_production", "asset_manifest"), by_id)
        self.assertEqual(by_id[("comic_production", "asset_manifest")]["artifact_type"], "asset_review_package")
        self.assertEqual(by_id[("comic_production", "asset_manifest")]["owner_agent"], "zhongshu")
        self.assertEqual(by_id[("research", "research_standard_report")]["artifact_type"], "standard_report")
        self.assertEqual(by_id[("research", "research_standard_report")]["owner_agent"], "gongbu")
        self.assertTrue(all(item["validator_provider"] for item in bindings))
        self.assertTrue(all(item["status"] == "passed" for item in bindings))

    def test_verifier_json_and_markdown_expose_registry_evidence(self):
        json_completed = subprocess.run(
            [sys.executable, "scripts/verify_office_schema_registry.py", "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        audit = json.loads(json_completed.stdout)
        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["error_count"], 0)

        markdown_completed = subprocess.run(
            [sys.executable, "scripts/verify_office_schema_registry.py", "--format", "markdown"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertIn("Office Schema Gate Registry Audit", markdown_completed.stdout)
        self.assertIn("comic_production", markdown_completed.stdout)
        self.assertIn("research_standard_report", markdown_completed.stdout)
        self.assertIn("Bindings: `11/11`", markdown_completed.stdout)


if __name__ == "__main__":
    unittest.main()
