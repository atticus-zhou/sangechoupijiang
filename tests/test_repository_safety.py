import subprocess
import sys
import unittest


class RepositorySafetyTests(unittest.TestCase):
    def test_tracked_files_do_not_contain_secrets_or_runtime_artifacts(self):
        result = subprocess.run(
            [sys.executable, "scripts/check_no_secrets.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn("Sensitive data scan passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
