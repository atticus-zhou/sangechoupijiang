from pathlib import Path
import unittest


APP_JS = Path("src/web/static/js/app.js")
INDEX_HTML = Path("src/web/static/index.html")


class FrontendComicRoutingTests(unittest.TestCase):
    def test_legacy_comic_hall_card_routes_to_production_office(self):
        html = INDEX_HTML.read_text(encoding="utf-8")

        self.assertNotIn("onclick=\"navigate('comic')\"", html)
        self.assertEqual(html.count("onclick=\"navigate('comic_production')\""), 1)

    def test_stored_legacy_comic_context_migrates_to_production(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("if (saved === 'comic') return 'comic_production';", js)

    def test_comic_task_watcher_handles_interrupted_tasks(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("task.status === 'interrupted'", js)
        self.assertIn("current_phase === 'interrupted'", js)
        self.assertIn("interrupted: '后台已中断'", js)
        self.assertIn("task_interrupted_after_restart: '后台已中断'", js)


if __name__ == "__main__":
    unittest.main()
