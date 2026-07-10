from pathlib import Path
import unittest


APP_JS = Path("src/web/static/js/app.js")
INDEX_HTML = Path("src/web/static/index.html")
README = Path("README.md")


class FrontendComicRoutingTests(unittest.TestCase):
    def test_comic_image_progress_events_have_human_labels(self):
        source = Path("src/web/static/js/app.js").read_text(encoding="utf-8")
        self.assertIn("comic_image_item_started: '正在生成图片'", source)
        self.assertIn("comic_image_item_completed: '图片生成完成'", source)
        self.assertIn("comic_image_item_failed: '图片生成失败'", source)

    def test_legacy_comic_hall_card_routes_to_production_office(self):
        html = INDEX_HTML.read_text(encoding="utf-8")

        self.assertNotIn("onclick=\"navigate('comic')\"", html)
        self.assertIn('id="office-card-comic-production"', html)
        self.assertIn("onclick=\"navigate('comic_production')\"", html)

    def test_stored_legacy_comic_context_migrates_to_production(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("if (saved === 'comic') return 'comic_production';", js)

    def test_comic_task_watcher_handles_interrupted_tasks(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("task.status === 'interrupted'", js)
        self.assertIn("current_phase === 'interrupted'", js)
        self.assertIn("interrupted: '后台已中断'", js)
        self.assertIn("task_interrupted_after_restart: '后台已中断'", js)

    def test_task_timelines_render_recovery_plan(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")

        self.assertIn("function renderTaskRecoveryPlan", js)
        research_fn = js[js.index("function renderResearchTaskTimeline"):js.index("function phaseLabel")]
        comic_fn = js[js.index("async function loadComicTimeline"):js.index("async function loadComicArtifacts")]
        self.assertIn("renderTaskRecoveryPlan(task.recovery_plan)", research_fn)
        self.assertIn("renderTaskRecoveryPlan(t.recovery_plan)", comic_fn)
        self.assertIn("继续处理", js)
        self.assertIn(".task-recovery-plan", css)

    def test_model_page_explains_comic_production_model_requirements(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("需要：${escapeHtml(requirement.type || '文本模型')}", js)
        self.assertIn("豆包 Seedream / 火山方舟等生图 API Key", js)
        self.assertIn("千问 VL / GPT 多模态等图片理解 API Key", js)
        self.assertIn("requirement.test", js)
        self.assertIn("requirement.impact", js)
        self.assertIn("测试方式", js)
        self.assertIn("缺失影响", js)
        self.assertIn("bingbu: '镜头提示词'", js)
        self.assertIn("xingbu: '视觉质检'", js)
        self.assertIn("gongbu: '资产组装'", js)

    def test_readme_model_table_matches_comic_production_roles(self):
        readme = README.read_text(encoding="utf-8")

        self.assertIn("| 兵部 | 文本镜头 / 视频提示词 |", readme)
        self.assertIn("| 工部 | 生图 + 文本组装，也就是图片生成模型加文本模型 |", readme)
        self.assertIn("    bingbu:\n      provider: deepseek\n      model: deepseek-chat", readme)
        self.assertIn("    gongbu:\n      provider: doubao\n      model: doubao-seedream-5", readme)
        self.assertNotIn("| 兵部 | 生图模型 |", readme)

    def test_model_page_and_comic_workbench_render_office_preflight(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn('id="model-preflight-panel"', html)
        self.assertIn('id="comic-preflight-panel"', html)
        self.assertIn("async function loadOfficePreflight", js)
        self.assertIn("/api/offices/${officeId}/preflight", js)
        self.assertIn("function renderOfficePreflight", js)
        self.assertIn("loadOfficePreflight(MODEL_OFFICE_ID", js)
        self.assertIn("loadOfficePreflight(activeComicOfficeId()", js)
        self.assertIn("/api/offices/${officeId}/readiness", js)
        self.assertIn("renderProductReadiness", js)

    def test_model_page_renders_current_office_model_requirement_summary(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn('id="model-requirement-summary"', html)
        self.assertIn("function renderModelRequirementSummary", js)
        self.assertIn("renderModelRequirementSummary()", js)
        self.assertIn("MODEL_REQUIREMENT_GROUPS", js)
        self.assertIn("MODEL_OFFICE_ID", js[js.index("function renderModelRequirementSummary"):js.index("async function loadModels")])
        self.assertIn("关键部门先填", js)
        self.assertIn("生图模型", js)
        self.assertIn("视觉理解", js)

    def test_model_page_renders_new_user_setup_path(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")

        self.assertIn('id="model-setup-path"', html)
        self.assertIn("function renderModelSetupPath", js)
        self.assertIn("先跑无 Key 演示", js)
        self.assertIn("最小可跑配置", js)
        self.assertIn("完整制片配置", js)
        self.assertIn("每个部门先点测试按钮", js)
        self.assertIn("renderModelSetupPath()", js)
        self.assertIn(".model-setup-path", css)

    def test_history_renders_delivery_summary(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")

        self.assertIn("function renderHistoryDeliverySummary", js)
        self.assertIn("renderHistoryDeliverySummary(h.delivery_summary", js)
        self.assertIn("renderHistoryDeliverySummary(item.delivery_summary", js)
        self.assertIn("downloadable_files", js)
        self.assertIn("missing_items", js)
        self.assertIn("recovery_actions", js)
        self.assertIn("function runHistoryRecoveryAction", js)
        self.assertIn("runHistoryRecoveryAction", js)
        self.assertIn("history-delivery-actions", js)
        self.assertIn("comic_v2_trace_uri", js)
        self.assertIn("download_uri", js)
        self.assertIn("history-artifact-links", js)
        self.assertIn("交付摘要", js)
        self.assertIn(".history-delivery-summary", css)
        self.assertIn(".history-delivery-actions", css)
        self.assertIn(".history-artifact-links", css)

    def test_office_hall_renders_system_preflight(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")

        self.assertIn('id="system-preflight-panel"', html)
        self.assertIn("async function loadSystemPreflight", js)
        self.assertIn("/api/system/preflight", js)
        self.assertIn("if (page === 'offices') loadSystemPreflight()", js)
        system_fn = js[js.index("function renderSystemPreflight"):js.index("function renderOfficePreflight")]
        self.assertIn("available_modes", system_fn)
        self.assertIn("limited_features", system_fn)
        self.assertIn("preflight-modes", system_fn)
        self.assertIn("preflight-limited", system_fn)
        self.assertIn(".preflight-modes", css)
        self.assertIn(".preflight-limited", css)

    def test_office_hall_cards_render_office_availability(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn('id="office-card-research"', html)
        self.assertIn('id="office-card-comic-production"', html)
        self.assertIn('id="office-availability-research"', html)
        self.assertIn('id="office-availability-comic-production"', html)
        self.assertIn("const OFFICE_HALL_PREFLIGHTS", js)
        self.assertIn("async function loadOfficeHallAvailability", js)
        self.assertIn("renderOfficeHallAvailability", js)
        self.assertIn("/api/offices/${officeId}/preflight", js)
        self.assertIn("if (page === 'offices') loadOfficeHallAvailability()", js)

    def test_office_hall_renders_launch_gate_audit(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")

        self.assertIn('id="office-launch-gates-panel"', html)
        self.assertIn("async function loadOfficeLaunchGates", js)
        self.assertIn("renderOfficeLaunchGates", js)
        self.assertIn("/api/offices/${officeId}/launch-gates", js)
        self.assertIn("if (page === 'offices') loadOfficeLaunchGates()", js)
        self.assertIn("上线门禁", js)
        self.assertIn("gate.next_action", js)
        self.assertIn("gate.evidence_links", js)
        self.assertIn("launch-gate-links", js)
        self.assertIn(".launch-gates-panel", css)
        self.assertIn(".launch-gate-links", css)
        self.assertIn(".launch-gate-grid", css)
        self.assertIn(".launch-gates-head,\n    .launch-gate-office > div", css)

    def test_hall_renders_public_showcase_and_no_key_demo_entry(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")

        self.assertIn('id="product-showcase"', html)
        self.assertIn('id="btn-open-comic-demo"', html)
        self.assertIn('id="btn-open-research-demo"', html)
        self.assertIn("navigate('demo_comic')", html)
        self.assertIn("navigate('demo_research')", html)
        self.assertIn('id="page-demo"', html)
        self.assertIn('id="comic-demo-content"', html)
        self.assertIn("demo_comic", js)
        self.assertIn("demo_research", js)
        self.assertIn("async function loadComicDemo", js)
        self.assertIn("async function loadResearchDemo", js)
        self.assertIn("/api/demo/comic-production", js)
        self.assertIn("/api/demo/research", js)
        self.assertIn("function renderComicDemo", js)
        self.assertIn("function renderResearchDemo", js)
        self.assertIn("function renderDemoViewerPath", js)
        self.assertIn("demo.viewer_path", js)
        self.assertIn("demo.proof_points", js)
        self.assertIn("function renderDemoQualityGates", js)
        self.assertIn("demo.quality_gates", js)
        self.assertIn("demo-viewer-path", css)
        self.assertIn("demo-quality-gates", css)
        self.assertIn("交付质量", js)
        self.assertIn("item.uri", js)
        self.assertIn("下载样例", js)
        self.assertIn(".product-showcase", css)
        self.assertIn(".demo-stage-grid", css)

    def test_comic_v2_actions_check_preflight_before_costly_steps(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("let currentOfficePreflight = null;", js)
        self.assertIn("function ensureComicCapabilities", js)
        self.assertIn("capabilityIds.includes(item.id)", js)
        self.assertIn("blockedStatuses.includes(item.status)", js)

        gated_actions = [
            ("planComicV2Assets", "['story_planning', 'asset_planning']"),
            ("planComicV2Prompts", "['prompt_planning']"),
            ("generateComicV2Images", "['image_generation', 'visual_review']"),
            ("buildComicV2Delivery", "['local_output']"),
        ]
        for function_name, gate in gated_actions:
            fn = js[js.index(f"async function {function_name}"):js.index("async function", js.index(f"async function {function_name}") + 1)]
            self.assertIn(f"ensureComicCapabilities({gate}", fn)

    def test_office_preflight_panel_has_soft_product_styles(self):
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")

        self.assertIn(".preflight-card", css)
        self.assertIn(".preflight-grid", css)
        self.assertIn(".preflight-item", css)

    def test_confirm_story_button_has_visible_loading_and_error_handling(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")
        confirm_fn = js[js.index("async function confirmComicScript"):js.index("function unconfirmComicScript")]
        board_fn = js[js.index("function renderComicPackageBoard"):js.index("function latestComicProductionChain")]

        self.assertIn('id="comic-confirm-start-btn"', html)
        self.assertIn("async function apiJson", js)
        self.assertIn("button.textContent = '确认中...'", js)
        self.assertIn("确认版故事已锁定", js)
        self.assertIn("deriveComicStoryDraft", js)
        self.assertIn("currentComicV2PendingAction = buildComicV2PendingAction", confirm_fn)
        self.assertIn("currentComicV2Status = currentComicV2Status ||", confirm_fn)
        self.assertIn("renderComicPackageBoard(currentComicArtifacts)", confirm_fn)
        self.assertIn("currentComicV2ActionError = {", confirm_fn)
        self.assertIn("currentComicV2PendingAction", board_fn)

    def test_api_json_preserves_structured_error_detail_for_action_feedback(self):
        js = APP_JS.read_text(encoding="utf-8")
        api_fn = js[js.index("async function apiJson"):js.index("const API =")]
        v2_action = js[js.index("async function runComicV2Action"):js.index("async function ensureComicCapabilities")]

        self.assertIn("error.detail = detail", api_fn)
        self.assertIn("error.status = response.status", api_fn)
        self.assertIn("function formatApiError", js)
        self.assertIn("detail.department", js)
        self.assertIn("detail.impact", js)
        self.assertIn("detail.next_action", js)
        self.assertIn("formatApiError(e)", v2_action)
        self.assertIn("setComicV2BlockingActionError", js)
        self.assertIn("currentOfficePreflight", js)

    def test_v2_action_pending_state_is_visible_in_stage_board(self):
        js = APP_JS.read_text(encoding="utf-8")
        v2_action = js[js.index("async function runComicV2Action"):js.index("async function ensureComicCapabilities")]
        v2_flow = js[js.index("function renderComicV2ProductionFlow"):js.index("function renderComicV2ActionError")]

        self.assertIn("let currentComicV2PendingAction = null;", js)
        self.assertIn("currentComicV2PendingAction = buildComicV2PendingAction", v2_action)
        self.assertIn("renderComicPackageBoard(currentComicArtifacts);", v2_action)
        self.assertIn("currentComicV2PendingAction = null;", v2_action)
        self.assertIn("renderComicV2PendingAction()", v2_flow)
        self.assertIn("function buildComicV2PendingAction", js)
        self.assertIn("function renderComicV2PendingAction", js)
        self.assertIn("正在处理", js)
        self.assertIn("负责部门", js)
        self.assertIn("下一步", js)
    def test_v2_action_error_stays_visible_in_stage_board(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")
        v2_action = js[js.index("async function runComicV2Action"):js.index("async function ensureComicCapabilities")]
        v2_flow = js[js.index("function renderComicV2ProductionFlow"):js.index("function renderComicV2StageActions")]

        self.assertIn("let currentComicV2ActionError = null;", js)
        self.assertIn("currentComicV2ActionError = null;", js)
        self.assertIn("currentComicV2ActionError = {", v2_action)
        self.assertIn("formatApiError(e)", v2_action)
        self.assertIn("renderComicV2ActionError()", v2_flow)
        self.assertIn("function renderComicV2ActionError", js)
        self.assertIn("function renderComicV2ActionRecovery", js)
        self.assertIn("currentComicV2ActionError.detail", js)
        self.assertIn("detail.department", js)
        self.assertIn("detail.next_action", js)
        self.assertIn("navigate('models')", js)
        self.assertIn("refreshComicV2Panel", js)
        self.assertIn(".v2-action-recovery", css)
        self.assertIn("最近一次操作失败", js)
        self.assertIn(".v2-action-error", css)

    def test_history_detail_renders_comic_v2_trace(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")
        detail_fn = js[js.index("async function viewHistoryDetail"):js.index("async function viewReport")]

        self.assertIn("function renderComicV2HistoryTrace", js)
        self.assertIn("renderComicV2HistoryTrace(item.comic_v2_trace)", detail_fn)
        self.assertIn("item.handoff_manifest_uri", detail_fn)
        self.assertIn("下载引用清单", detail_fn)
        self.assertIn("故事版本", js)
        self.assertIn("资产版本", js)
        self.assertIn("提示词", js)
        self.assertIn("视觉质检", js)
        self.assertIn("引用清单", js)

        self.assertIn("function renderComicV2LineageTimeline", js)
        self.assertIn("renderComicV2LineageTimeline(trace.production_lineage)", js)
        self.assertIn("function renderComicV2HistoryShotPackages", js)
        self.assertIn("renderComicV2HistoryShotPackages(trace.shots)", js)
        self.assertIn("镜头生产包", js)
        self.assertIn("首帧参考", js)
        self.assertIn("视频提示词", js)
        self.assertIn("lineage-stage-card", js)
        self.assertIn("human_checkpoint", js)
        self.assertIn(".lineage-stage-grid", css)
        self.assertIn(".lineage-stage-card", css)

    def test_handoff_manifest_is_treated_as_delivery_artifact(self):
        js = APP_JS.read_text(encoding="utf-8")
        groups_fn = js[js.index("function comicArtifactGroups"):js.index("function renderComicArtifactGroup")]
        history_summary_fn = js[js.index("function historyArtifactSummary"):js.index("async function viewHistoryDetail")]

        self.assertIn("comic_v2_handoff_manifest", groups_fn)
        self.assertIn("handoff_manifest_uri", history_summary_fn)
        self.assertIn("含引用清单", history_summary_fn)

    def test_cabinet_llm_fallback_error_renders_persistent_warning(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")
        cabinet_fn = js[js.index("function renderComicCabinet"):js.index("async function confirmComicScript")]

        self.assertIn("function renderComicCabinetModelWarning", js)
        self.assertIn("llm_fallback_error", cabinet_fn)
        self.assertIn("renderComicCabinetModelWarning", cabinet_fn)
        self.assertIn("主创模型没有正常返回", js)
        self.assertIn("这不是正式模型输出", js)
        self.assertIn("comic-model-warning", css)

    def test_office_preflight_renders_blocking_owner_and_model_kind(self):
        js = APP_JS.read_text(encoding="utf-8")
        preflight_fn = js[js.index("function renderOfficePreflight"):js.index("function preflightBadgeClass")]

        self.assertIn("owner_label", preflight_fn)
        self.assertIn("model_kind", preflight_fn)
        self.assertIn("preflight-owner", preflight_fn)
        self.assertIn("办公室", preflight_fn)
        self.assertIn("下一步", preflight_fn)

    def test_comic_input_accepts_character_and_style_references(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")
        read_fields = js[js.index("function readComicFormFields"):js.index("function toggleComicInputMode")]
        payload_fn = js[js.index("function comicPayloadForCabinet"):js.index("function formatComicBriefForRequest")]

        self.assertIn('id="comic-character-source"', html)
        self.assertIn('id="comic-style-reference"', html)
        self.assertIn("character_source", read_fields)
        self.assertIn("style_reference", read_fields)
        self.assertIn("Character references:", payload_fn)
        self.assertIn("Style references:", payload_fn)
    def test_cabinet_assistant_message_renders_even_without_chat_history(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("let currentComicAssistantMessage = '';", js)
        self.assertIn("currentComicAssistantMessage = result.assistant_message || '';", js)
        self.assertIn("const assistantFallback", js)
        self.assertIn("currentComicAssistantMessage && !messages.some", js)
        self.assertIn("role: 'assistant'", js)

    def test_cabinet_renders_clickable_suggested_replies(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")
        cabinet_fn = js[js.index("function renderComicCabinet"):js.index("function renderComicCabinetModelWarning")]

        self.assertIn("function renderComicSuggestedReplies", js)
        self.assertIn("currentComicCabinetSession?.story_state?.suggested_replies", js)
        self.assertIn("renderComicSuggestedReplies", cabinet_fn)
        self.assertIn("function selectComicSuggestedReply", js)
        self.assertIn("window.selectComicSuggestedReply = selectComicSuggestedReply;", js)
        self.assertIn(".comic-suggested-replies", css)


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

    def test_comic_workbench_renders_runtime_status_panel(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")
        select_fn = js[js.index("async function selectComicWorkspace"):js.index("function resetComicWorkspaceState")]

        self.assertIn('id="comic-runtime-status-panel"', html)
        self.assertIn("let currentComicRuntimeStatus = null;", js)
        self.assertIn("async function loadComicRuntimeStatus", js)
        self.assertIn("/api/workspaces/${workspaceId}/runtime-status", js)
        self.assertIn("function renderOfficeRuntimeStatus", js)
        self.assertIn("artifact_progress", js)
        self.assertIn("missing_count", js)
        self.assertIn("retry_action", js)
        self.assertIn("loadComicRuntimeStatus(workspaceId)", select_fn)
        self.assertIn("renderOfficeRuntimeStatus(null", js)
        self.assertIn(".runtime-status-panel", css)

    def test_v2_stage_board_renders_review_gate_map_from_lineage(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")
        v2_flow = js[js.index("function renderComicV2ProductionFlow"):js.index("function buildComicV2PendingAction")]
        self.assertIn("function renderComicV2ReviewGateMap", js)
        gate_fn = js[js.index("function renderComicV2ReviewGateMap"):js.index("function renderComicV2LineageTimeline")]

        self.assertIn("renderComicV2ReviewGateMap(currentComicV2Status.production_lineage)", v2_flow)
        self.assertIn("human_checkpoint", gate_fn)
        self.assertIn("handoff_to", gate_fn)
        self.assertIn("acceptance_criteria", gate_fn)
        self.assertIn("审核节点", gate_fn)
        self.assertIn(".v2-review-gate-map", css)
        self.assertIn(".v2-review-gate.current", css)

    def test_comic_production_confirm_story_enters_v2_pipeline_not_legacy_task(self):
        js = APP_JS.read_text(encoding="utf-8")
        confirm_fn = js[js.index("async function confirmComicScript"):js.index("function unconfirmComicScript")]

        self.assertIn("/api/comic/confirm-script", confirm_fn)
        self.assertIn("/comic/v2/plan-confirmed", confirm_fn)
        self.assertIn("await refreshComicV2Panel", confirm_fn)
        self.assertNotIn("/api/comic/confirm-and-start", confirm_fn)
        self.assertNotIn("watchComicTask(", confirm_fn)

    def test_v2_stage_board_exposes_real_next_step_actions(self):
        js = APP_JS.read_text(encoding="utf-8")
        v2_flow = js[js.index("function renderComicV2ProductionFlow"):js.index("function renderComicDepartmentStep")]

        for action in [
            "approveComicV2VisualBible",
            "reviseComicV2VisualBible",
            "planComicV2Assets",
            "approveComicV2Assets",
            "reviseComicV2Assets",
            "planComicV2Prompts",
            "generateComicV2Images",
            "overrideComicV2VisualReview",
            "buildComicV2Delivery",
        ]:
            self.assertIn(action, js)
            self.assertIn(action, v2_flow)

    def test_v2_action_row_has_responsive_button_spacing(self):
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")

        self.assertIn(".v2-action-row", css)
        self.assertIn("flex-wrap: wrap", css)
        self.assertIn(".v2-action-row .btn-sm", css)
        self.assertIn(".v2-action-pending", css)
        self.assertIn("box-shadow: 0 0 0 4px", css)

    def test_selecting_new_comic_project_clears_visible_v2_state_immediately(self):
        js = APP_JS.read_text(encoding="utf-8")
        select_fn = js[js.index("async function selectComicWorkspace"):js.index("async function loadComicV2Status")]

        self.assertIn("resetComicWorkspaceState", js)
        self.assertIn("resetComicWorkspaceState({ clearInputs: true })", select_fn)
        self.assertIn("renderComicPackageBoard()", select_fn)

    def test_switching_existing_comic_project_clears_old_state_before_loading(self):
        js = APP_JS.read_text(encoding="utf-8")
        select_fn = js[js.index("async function selectComicWorkspace"):js.index("async function loadComicV2Status")]

        self.assertIn("resetComicWorkspaceState({ preserveInputs: true })", select_fn)
        reset_index = select_fn.index("resetComicWorkspaceState({ preserveInputs: true })")
        load_index = select_fn.index("await loadComicRuntimeStatus(workspaceId)")
        self.assertLess(reset_index, load_index)
        self.assertIn("renderComicPackageBoard()", select_fn)

    def test_comic_workspace_async_loaders_ignore_stale_responses(self):
        js = APP_JS.read_text(encoding="utf-8")
        status_fn = js[js.index("async function loadComicV2Status"):js.index("async function refreshComicV2Panel")]
        runtime_fn = js[js.index("async function loadComicRuntimeStatus"):js.index("function renderOfficeRuntimeStatus")]
        cabinet_fn = js[js.index("async function loadComicCabinetSession"):js.index("async function loadComicTimeline")]
        timeline_fn = js[js.index("async function loadComicTimeline"):js.index("async function loadComicArtifacts")]
        artifact_fn = js[js.index("async function loadComicArtifacts"):js.index("function renderComicArtifactNavigator")]

        for fn in [status_fn, runtime_fn, cabinet_fn, timeline_fn, artifact_fn]:
            self.assertIn("if (currentComicWorkspace !== workspaceId) return null;", fn)

    def test_inline_comic_handlers_are_exposed_on_window(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("window.selectComicWorkspace = selectComicWorkspace;", js)
        self.assertIn("window.confirmComicScript = confirmComicScript;", js)
        self.assertIn("window.buildComicV2Delivery = buildComicV2Delivery;", js)
        self.assertIn("window.planComicV2Assets = planComicV2Assets;", js)
        self.assertNotIn("window.regenerateComicStory = regenerateComicStory;", js)

    def test_index_uses_fresh_comic_v2_script_cache_key(self):
        html = INDEX_HTML.read_text(encoding="utf-8")

        self.assertIn("/static/js/app.js?v=comic-v2-shot-cards-20260701", html)
        self.assertNotIn("comic-confirm-feedback-20260610", html)

    def test_empty_artifact_board_still_renders_v2_stage_actions(self):
        js = APP_JS.read_text(encoding="utf-8")
        board_fn = js[js.index("function renderComicPackageBoard"):js.index("function latestComicProductionChain")]

        self.assertIn("currentComicV2Status && currentComicV2Status.pipeline_version === 2", board_fn)
        self.assertIn("renderComicV2ProductionFlow()", board_fn)

    def test_v2_package_board_does_not_mix_legacy_score_grid(self):
        js = APP_JS.read_text(encoding="utf-8")
        board_fn = js[js.index("function renderComicPackageBoard"):js.index("function latestComicProductionChain")]

        v2_check = board_fn.index("const hasV2Status = Boolean(currentComicV2PendingAction)")
        legacy_grid = board_fn.index("COMIC_REQUIRED_ARTIFACTS.map")
        self.assertLess(v2_check, legacy_grid)

    def test_v2_stage_board_shows_human_review_summary(self):
        js = APP_JS.read_text(encoding="utf-8")
        v2_flow = js[js.index("function renderComicV2ProductionFlow"):js.index("function renderComicV2StageActions")]

        self.assertIn("renderComicV2ReviewSummary(currentComicV2Status)", v2_flow)
        self.assertIn("function renderComicV2ReviewSummary", js)
        self.assertIn("status.contract?.visual", js)
        self.assertIn("status.asset_manifest?.items", js)
        self.assertIn("status.delivery?.audit", js)

    def test_v2_stage_board_renders_department_flow(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("function renderComicV2DepartmentFlow", js)
        self.assertIn("currentComicV2Status.department_flow", js)
        self.assertIn("department-flow v2-department-flow", js)
        self.assertIn("dept.responsibility", js)
        self.assertIn("dept.human_checkpoint", js)

    def test_v2_stage_board_renders_current_production_lineage(self):
        js = APP_JS.read_text(encoding="utf-8")
        v2_flow = js[js.index("function renderComicV2ProductionFlow"):js.index("function renderComicV2StageActions")]

        self.assertIn("renderComicV2LineageTimeline(currentComicV2Status.production_lineage)", v2_flow)
        self.assertIn("production_lineage", js)
        self.assertIn("item.handoff_to", js)
        self.assertIn("item.acceptance_criteria", js)
        self.assertIn("交给：", js)
        self.assertIn("验收：", js)

    def test_v2_asset_review_summary_uses_human_review_projection(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("function renderComicV2AssetReviewGroups", js)
        self.assertIn("status.asset_review?.groups", js)
        self.assertIn("source_evidence", js)
        self.assertIn("planned_image_labels", js)
        self.assertIn("只确认人物、道具和场景", js)
        self.assertNotIn("提示词会在这里提前展示", js)

    def test_v2_asset_review_items_can_write_structured_revision_notes(self):
        js = APP_JS.read_text(encoding="utf-8")

        self.assertIn("function appendComicV2AssetReviewNote", js)
        self.assertIn("删除这个资产", js)
        self.assertIn("修改这个资产", js)
        self.assertIn("comic-asset-review-notes", js)
        self.assertIn("删除【${typeLabel}】资产「${name}」", js)
        self.assertIn("修改【${typeLabel}】资产「${name}」", js)
        self.assertIn("window.appendComicV2AssetReviewNote = appendComicV2AssetReviewNote;", js)

    def test_v2_asset_review_renders_revision_diff_and_retry_feedback(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")

        self.assertIn("function renderComicV2AssetRevisionSummary", js)
        self.assertIn("revision_summary", js)
        self.assertIn("previous_manifest_hash", js)
        self.assertIn("新增", js)
        self.assertIn("删除", js)
        self.assertIn("修改", js)
        self.assertIn("资产重拆已提交", js)
        self.assertIn(".v2-asset-revision-summary", css)

    def test_v2_asset_detail_renders_identity_and_reference_chain(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")
        select_fn = js[js.index("function selectComicArtifact"):js.index("async function regenerateComicImage")]

        self.assertIn("comic_v2_generated_image", select_fn)
        self.assertIn("renderComicV2AssetIdentityPanel(artifact)", select_fn)
        self.assertIn("function renderComicV2AssetIdentityPanel", js)
        self.assertIn("function comicV2AssetIdentityForArtifact", js)
        self.assertIn("currentComicV2Status.asset_manifest?.items", js)
        self.assertIn("currentComicV2Status.prompt_package?.prompts", js)
        self.assertIn("currentComicV2Status.image_production?.records", js)
        self.assertIn("reference_asset_ids", js)
        self.assertIn("资产身份证", js)
        self.assertIn("引用链路", js)
        self.assertIn(".v2-asset-identity-panel", css)

    def test_v2_stage_board_renders_production_ready_shot_prompt_cards(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")
        v2_flow = js[js.index("function renderComicV2ProductionFlow"):js.index("function renderComicV2StageActions")]

        self.assertIn("renderComicV2ShotPromptCards(currentComicV2Status)", v2_flow)
        self.assertIn("function renderComicV2ShotPromptCards", js)
        self.assertIn("currentComicV2Status.prompt_package?.shots", js)
        self.assertIn("reference_asset_ids", js)
        self.assertIn("action_chain", js)
        self.assertIn("camera_movement", js)
        self.assertIn("generator_prompt", js)
        self.assertIn("negative_prompt", js)
        self.assertIn("镜头执行卡", js)
        self.assertIn("首帧参考资产", js)
        self.assertIn("视频提示词", js)
        self.assertIn("负面提示词", js)
        self.assertIn("验收标准", js)
        self.assertIn(".v2-shot-prompt-cards", css)
        self.assertIn(".v2-shot-card", css)
        self.assertIn(".v2-shot-negative", css)

    def test_artifact_detail_renders_schema_gate_status(self):
        js = APP_JS.read_text(encoding="utf-8")
        css = Path("src/web/static/css/style.css").read_text(encoding="utf-8")
        research_detail = js[js.index("function selectResearchArtifact"):js.index("async function submitResearchTask")]
        comic_detail = js[js.index("function selectComicArtifact"):js.index("function renderComicV2AssetIdentityPanel")]

        self.assertIn("function renderArtifactSchemaGatePanel", js)
        self.assertIn("schema_gate", js)
        self.assertIn("renderArtifactSchemaGatePanel(artifact)", research_detail)
        self.assertIn("renderArtifactSchemaGatePanel(artifact)", comic_detail)
        self.assertIn("artifact.artifact_type === 'quality_report'", js)
        self.assertIn("artifact-schema-gate", css)
        self.assertIn("schema-gate-failed", css)
        self.assertIn("schema-gate-passed", css)


if __name__ == "__main__":
    unittest.main()
