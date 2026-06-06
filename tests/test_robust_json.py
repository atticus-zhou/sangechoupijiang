import asyncio
import unittest

from src.llm.robust_json import parse_json_object, retry_async


class RobustJsonTests(unittest.TestCase):
    def test_parse_json_object_extracts_fenced_json_with_trailing_commas(self):
        raw = """
        Here is the result:
        ```json
        {
          "assistant_message": "ok",
          "story": {
            "title": "Test",
            "questions": ["one",],
          },
        }
        ```
        """

        parsed = parse_json_object(raw)

        self.assertEqual(parsed["assistant_message"], "ok")
        self.assertEqual(parsed["story"]["title"], "Test")
        self.assertEqual(parsed["story"]["questions"], ["one"])

    def test_parse_json_object_repairs_single_quoted_simple_payload(self):
        parsed = parse_json_object("{'verdict': 'ok', 'comment': 'safe', 'question': ''}")

        self.assertEqual(parsed["verdict"], "ok")
        self.assertEqual(parsed["comment"], "safe")

    def test_retry_async_retries_until_operation_succeeds(self):
        attempts = {"count": 0}

        async def operation():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("temporary")
            return "done"

        result = asyncio.run(retry_async(operation, attempts=3, delay_seconds=0))

        self.assertEqual(result, "done")
        self.assertEqual(attempts["count"], 3)


if __name__ == "__main__":
    unittest.main()
