from pathlib import Path
import unittest


APP_JS = Path("src/web/static/js/app.js")
INDEX_HTML = Path("src/web/static/index.html")


class FrontendComicRoutingTests(unittest.TestCase):
    def test_comic_image_progress_events_have_human_labels(self):
        source = Path("src/web/static/js/app.js").read_text(encoding="utf-8")
        self.assertIn("comic_image_item_started: '正在生成图片'", source)
        self.assertIn("comic_image_item_completed: '图片生成完成'", source)
        self.assertIn("comic_image_item_failed: '图片生成失败'", source)

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


    def test_comic_stage_board_renders_department_flow_and_review_action(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("function renderComicProductionFlow", js)
        self.assertIn("function renderComicDepartmentStep", js)
        self.assertIn("production_chain_state", js)
        self.assertIn("meta.current_department", js)
        self.assertIn("meta.next_action", js)
        self.assertIn("focusComicAssetReview()", js)

    def test_returned_asset_review_can_be_regenerated_from_frontend(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("按退回意见重新拆解", js)
        self.assertIn("reviewStatus !== 'approved' && reviewStatus !== 'revision_requested'", js)
        self.assertIn("submitComicTask({ revisionMode: true })", js)
        self.assertIn("Asset revision notes:", js)
        self.assertIn("资产拆解已退回。你可以修改上方要求，然后点击“按退回意见重新拆解”。", js)

    def test_v2_stage_board_loads_honest_current_work_state(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("async function loadComicV2Status", js)
        self.assertIn("/comic/v2/status", js)
        self.assertIn("currentComicV2Status.current_agent", js)
        self.assertIn("currentComicV2Status.current_object", js)
        self.assertIn("currentComicV2Status.blocking_reason", js)
        self.assertIn("currentComicV2Status.next_action", js)


if __name__ == "__main__":
    unittest.main()
