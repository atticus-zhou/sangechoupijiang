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

    def test_model_page_explains_comic_production_model_requirements(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("需要：${escapeHtml(requirement.type || '文本模型')}", js)
        self.assertIn("豆包 Seedream / 火山方舟等生图 API Key", js)
        self.assertIn("千问 VL / GPT 多模态等图片理解 API Key", js)
        self.assertIn("bingbu: '分镜生图'", js)
        self.assertIn("xingbu: '视觉质检'", js)
        self.assertIn("gongbu: '资产组装'", js)

    def test_confirm_story_button_has_visible_loading_and_error_handling(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn('id="comic-confirm-start-btn"', html)
        self.assertIn("async function apiJson", js)
        self.assertIn("button.textContent = '确认中...'", js)
        self.assertIn("确认版故事已锁定", js)
        self.assertIn("deriveComicStoryDraft", js)


if __name__ == "__main__":
    unittest.main()
