"""Office profiles for project-oriented multi-agent workflows.

An office is a product/workflow context. It reuses the same agents, but gives
them office-specific duties, expected artifacts, and acceptance standards.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class OfficeProfile:
    id: str
    name: str
    description: str
    input_types: list[str] = field(default_factory=list)
    output_types: list[str] = field(default_factory=list)
    agent_duties: dict[str, str] = field(default_factory=dict)
    artifact_types: list[str] = field(default_factory=list)
    model_requirements: list[dict] = field(default_factory=list)
    human_checkpoints: list[dict] = field(default_factory=list)
    artifact_contract: dict[str, object] = field(default_factory=dict)
    schema_gates: list[dict] = field(default_factory=list)
    recovery_actions: list[dict] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    default_template: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


RESEARCH_OFFICE = OfficeProfile(
    id="research",
    name="研究办公室",
    description=(
        "用于产品调研、电商平台分析、竞品表格、证据截图、老板简报和开品决策的人机协作办公室；"
        "第三方平台取证依赖账号权限、登录状态和页面可访问性，系统提供辅助截图与待补证据整理。"
    ),
    input_types=["调研对象", "完整调研需求", "第三方平台截图", "已有资料"],
    output_types=["阶段调研报告", "来源清单", "数据表", "竞品表", "截图计划", "证据清单"],
    agent_duties={
        "zhongshu": "把用户需求拆成调研计划，明确行业、平台数据、竞品、评论痛点、机会点和开品判断。",
        "menxia": "审查调研计划是否遗漏平台数据、竞品表、痛点分析、机会映射或老板可读的交付内容。",
        "shangshu": "统筹采集、核验、制表、写作和导出材料包的执行顺序。",
        "libu": "检索并归档项目背景、历史调研、资料来源和上下文记录。",
        "hubu": "整理数据表、竞品矩阵、价格带、销量字段和评论痛点摘要。",
        "libu_comm": "把过程进展和交付摘要整理成用户能看懂的说明。",
        "bingbu": "采集市场数据、平台/电商信息、竞品证据、来源链接和截图目标。",
        "xingbu": "检查来源质量、数据年份、占位数字、无依据结论和材料包完整度。",
        "gongbu": "组装最终调研材料：报告、简报、表格、机会地图、截图计划和可导出文件。",
    },
    artifact_types=[
        "research_plan",
        "report",
        "standard_report",
        "briefing",
        "data_table",
        "competitor_table",
        "review_pain_points",
        "opportunity_map",
        "chart",
        "chart_plan",
        "source_list",
        "screenshot_plan",
        "quality_report",
    ],
    model_requirements=[
        {"agent": "zhongshu", "model_kind": "text", "purpose": "调研目标拆解与报告结构规划"},
        {"agent": "bingbu", "model_kind": "text", "purpose": "来源整理、截图计划和平台取证说明"},
        {"agent": "hubu", "model_kind": "text", "purpose": "数据表、竞品表和评论痛点结构化"},
        {"agent": "xingbu", "model_kind": "text", "purpose": "来源质量、年份、结论依据和缺口检查"},
        {"agent": "gongbu", "model_kind": "text", "purpose": "报告、简报和材料包组装"},
    ],
    human_checkpoints=[
        {"id": "research_scope", "title": "确认调研范围", "owner": "zhongshu", "required": True},
        {"id": "evidence_capture", "title": "人工登录或补充第三方平台截图", "owner": "bingbu", "required": False},
        {"id": "report_review", "title": "确认阶段报告是否可继续补证据", "owner": "xingbu", "required": True},
    ],
    artifact_contract={
        "id_field": "artifact_id",
        "required_metadata": ["office_id", "source", "version", "responsible_agent", "reference_chain"],
        "trace_rule": "报告、截图、数据点和结论必须能追溯到来源或待补证据说明。",
    },
    schema_gates=[
        {"schema_id": "research_standard_report", "owner_agent": "gongbu", "stage": "artifact_packaging", "artifact_type": "standard_report"},
        {"schema_id": "research_source_list", "owner_agent": "bingbu", "stage": "evidence_extraction", "artifact_type": "source_list"},
        {"schema_id": "research_data_table", "owner_agent": "hubu", "stage": "artifact_packaging", "artifact_type": "data_table"},
        {"schema_id": "research_competitor_table", "owner_agent": "hubu", "stage": "artifact_packaging", "artifact_type": "competitor_table"},
    ],
    recovery_actions=[
        {
            "stage": "feigua_evidence_capture",
            "label": "整理已上传/已截取证据",
            "method": "POST",
            "path_template": "/api/workspaces/{workspace_id}/evidence/sync",
        },
        {
            "stage": "evidence_extraction",
            "label": "重新识别工作区截图证据",
            "method": "POST",
            "path_template": "/api/workspaces/{workspace_id}/evidence/extract-all",
        },
        {
            "stage": "agent_workflow",
            "label": "整理已有研究产出",
            "method": "POST",
            "path_template": "/api/tasks/{task_id}/recover-artifacts",
        },
        {
            "stage": "artifact_packaging",
            "label": "重新整理研究材料包",
            "method": "POST",
            "path_template": "/api/tasks/{task_id}/recover-artifacts",
        },
    ],
    acceptance_criteria=[
        "最终报告必须有清晰的老板摘要。",
        "近期数据尽量标注年份、日期和来源。",
        "重要判断需要能追溯到来源说明或证据产物。",
        "头部竞品需要形成可对比表格；无法获取时要明确标注。",
        "评论痛点和差异化机会要拆成独立产物，不能只埋在正文里。",
        "图表和表格要作为独立材料输出，方便复制到汇报文件。",
        "需要截图取证的平台页面要列出截图目标。",
        "第三方平台截图受账号权限、登录状态和页面变化影响；无法访问时必须标注待补证据和人工补证路径。",
        "最终材料包应能直接用于职场交接或老板汇报。",
    ],
    default_template=(
        "Research the following product/category and prepare a workplace-ready product research package. "
        "Follow the research office playbook: industry overview, platform/channel data, top competitors, "
        "sales and price-band fields, title/selling-point keywords, user profile, review pain points, "
        "common success factors, differentiation opportunities, chart/table opportunities, screenshot/evidence "
        "needs, pending evidence gaps, account-permission limits, and launch/development recommendations. "
        "Do not promise fully automatic third-party-platform evidence capture; mark unavailable pages as pending. "
        "User request: {user_input}"
    ),
)


COMIC_OFFICE = OfficeProfile(
    id="comic",
    name="AI漫剧办公室",
    description=(
        "用于 AI 漫剧前期制作：完善剧本、拆人物/道具/场景、制定风格圣经、镜头提示词、视频提示词和一致性检查。"
    ),
    input_types=["灵感", "完整剧本", "已有角色设定", "参考风格"],
    output_types=["剧本方向", "人物表", "道具表", "场景表", "提示词包", "交付清单"],
    agent_duties={
        "zhongshu": "把用户灵感整理成短剧方向、冲突结构、分集节奏和需要人工确认的节点。",
        "menxia": "审查故事方向是否有钩子、代价、动机闭环和可复用的生产标准。",
        "shangshu": "统筹剧本、资产拆解、画风锁定、镜头提示词、视频提示词包和一致性检查。",
        "libu": "归档故事圣经、风格圣经、人物锁定、道具规则、场景规则和历史生成批次。",
        "hubu": "维护人物、道具、场景、建筑及其连续性规则的结构化资产表。",
        "libu_comm": "把产物整理成适合交给生图、视频和剪辑平台的交接说明。",
        "bingbu": "准备镜头行、镜头画面提示词、视频生成提示词和下游生成任务。",
        "xingbu": "在资产通过前检查人物、道具、场景、画风和镜头连续性。",
        "gongbu": "产出前期制作材料包：风格圣经、基础资产图、提示词包和交付清单。",
    },
    artifact_types=[
        "script",
        "style_bible",
        "character_sheet",
        "prop_sheet",
        "scene_sheet",
        "shot_prompt_table",
        "prompt_package",
        "consistency_checklist",
        "delivery_manifest",
    ],
    model_requirements=[
        {"agent": "zhongshu", "model_kind": "text", "purpose": "故事方向、结构和生产信息整理"},
        {"agent": "hubu", "model_kind": "text", "purpose": "人物、道具、场景资产表维护"},
        {"agent": "bingbu", "model_kind": "text", "purpose": "镜头提示词和视频提示词规划"},
        {"agent": "xingbu", "model_kind": "vision", "purpose": "人物、道具、场景和画风连续性质检"},
        {"agent": "gongbu", "model_kind": "image", "purpose": "基础资产图和交付材料组装"},
    ],
    human_checkpoints=[
        {"id": "story_confirmation", "title": "确认故事方向", "owner": "neige", "required": True},
        {"id": "asset_review", "title": "确认人物、道具、场景清单", "owner": "menxia", "required": True},
        {"id": "delivery_review", "title": "确认交付包是否可给下游平台", "owner": "xingbu", "required": True},
    ],
    artifact_contract={
        "id_field": "artifact_id",
        "required_metadata": ["office_id", "source", "version", "responsible_agent", "reference_chain"],
        "trace_rule": "每个资产、镜头和提示词都必须引用故事来源和资产身份。",
    },
    acceptance_criteria=[
        "材料包要把原始灵感推进成可拍的剧本方向。",
        "人物、道具、场景需要有独立且可锁定的资产表。",
        "风格圣经要说明视觉一致性和返工规则。",
        "镜头提示词行需要包含场景、人物、道具、构图、画面提示词和视频生成提示词。",
        "场景资产需要包含基础场景图、广角建立图、俯视布局图和常用机位参考。",
        "材料包应能交给后续图片、视频或剪辑平台继续制作。",
        "本办公室只交付制片前期材料，不宣称生成最终剪辑短剧。",
    ],
    default_template=(
        "Create an AI comic-drama pre-production package from this idea. "
        "Do not produce the final edited video. Produce script direction, "
        "character sheets, prop sheets, scene sheets, style bible, shot prompts, "
        "video prompts, image prompts, negative prompts, consistency "
        "checklist, and delivery manifest. User idea: {user_input}"
    ),
)


COMIC_PRODUCTION_OFFICE = OfficeProfile(
    id="comic_production",
    name="AI漫剧制片办公室",
    description=(
        "隔离版 AI 漫剧制片办公室。它把已确认故事转换成结构化生产链：故事合约、部门交接、资产表、镜头提示词、视频提示词、质检和 Word 画布。"
    ),
    input_types=["灵感", "完整剧本", "已有角色设定", "参考风格"],
    output_types=["故事合同", "视觉母版", "资产身份证", "镜头生产包", "提示词包", "Word 制片画布"],
    agent_duties={
        "neige": "先和人类创作者对齐故事方向，在生产开始前冻结故事合约。",
        "zhongshu": "把确认稿转成生产任务书，列清需要填写的资产槽位、验收规则和部门交接要求。",
        "menxia": "审核任务书是否缺人物、道具、场景、连续性规则、镜头覆盖或交付要求。",
        "shangshu": "把通过审核的空白制片模板分发给各部门，并跟踪哪些槽位已完成或被阻塞。",
        "libu": "维护连续性记忆：故事圣经、人物锁定、场景规则、道具规则和版本变化。",
        "hubu": "维护资产登记表和资源台账，记录人物、道具、场景、生成图和提示词归属。",
        "libu_comm": "面向下游图片、视频和剪辑平台整理交接说明。",
        "bingbu": "根据审核通过的生产任务书生成镜头提示词行和视频提示词行。",
        "xingbu": "检查故事、连续性、画面提示词、视频提示词和 Word 画布是否完整。",
        "gongbu": "生成并组装交付材料，包括图片规格、生成图和 Word 制片画布。",
    },
    artifact_types=[
        "story_contract",
        "production_brief",
        "production_review",
        "asset_review_package",
        "production_chain_state",
        "dispatch_plan",
        "asset_registry",
        "continuity_bible",
        "platform_delivery_spec",
        "script",
        "character_sheet",
        "prop_sheet",
        "scene_sheet",
        "style_bible",
        "shot_prompt_table",
        "prompt_package",
        "generated_image",
        "image_quality_report",
        "quality_report",
        "word_canvas",
    ],
    model_requirements=[
        {"agent": "zhongshu", "model_kind": "text", "purpose": "故事合同、视觉母版和资产拆解初稿"},
        {"agent": "menxia", "model_kind": "text", "purpose": "故事、视觉母版和资产拆解审核"},
        {"agent": "bingbu", "model_kind": "text", "purpose": "镜头执行卡、动作链和视频提示词"},
        {"agent": "hubu", "model_kind": "text", "purpose": "资产登记、资源台账和引用关系"},
        {"agent": "xingbu", "model_kind": "vision", "purpose": "视觉质检、图片一致性和交付风险检查"},
        {"agent": "gongbu", "model_kind": "image", "purpose": "基础资产图生成和 Word 制片画布组装"},
    ],
    human_checkpoints=[
        {"id": "story_confirmation", "title": "确认完整故事后再生产", "owner": "neige", "required": True},
        {"id": "visual_bible_review", "title": "确认视觉母版和风格边界", "owner": "menxia", "required": True},
        {"id": "asset_review", "title": "确认人物、道具、场景资产拆解", "owner": "menxia", "required": True},
        {"id": "visual_quality_release", "title": "确认图片质检后进入交付", "owner": "xingbu", "required": False},
        {"id": "delivery_review", "title": "确认 Word 制片画布和引用清单", "owner": "libu_comm", "required": True},
    ],
    artifact_contract={
        "id_field": "artifact_id",
        "required_metadata": ["office_id", "source", "version", "responsible_agent", "reference_chain"],
        "trace_rule": "故事合同、视觉母版、资产、图片、镜头、提示词和 Word 画布必须保持可追溯引用链路。",
    },
    schema_gates=[
        {"schema_id": "comic_contract", "owner_agent": "zhongshu", "stage": "story_contract", "artifact_type": "story_contract"},
        {"schema_id": "visual_revision", "owner_agent": "zhongshu", "stage": "visual_bible_review", "artifact_type": "style_bible"},
        {"schema_id": "asset_manifest", "owner_agent": "zhongshu", "stage": "asset_review", "artifact_type": "asset_review_package"},
        {"schema_id": "asset_manifest_revision", "owner_agent": "zhongshu", "stage": "asset_review", "artifact_type": "asset_review_package"},
        {"schema_id": "asset_prompt_set", "owner_agent": "gongbu", "stage": "prompt_package", "artifact_type": "prompt_package"},
        {"schema_id": "shot_cards", "owner_agent": "bingbu", "stage": "shot_package", "artifact_type": "shot_prompt_table"},
        {"schema_id": "image_review_result", "owner_agent": "xingbu", "stage": "image_quality_review", "artifact_type": "image_quality_report"},
    ],
    recovery_actions=[
        {"stage": "visual_bible_planning", "label": "重新生成故事合同与视觉母版", "method": "POST", "path_template": "/api/workspaces/{workspace_id}/comic/v2/plan-confirmed"},
        {"stage": "asset_planning", "label": "重新生成资产拆解包", "method": "POST", "path_template": "/api/workspaces/{workspace_id}/comic/v2/assets/plan"},
        {"stage": "asset_review", "label": "重新生成资产拆解包", "method": "POST", "path_template": "/api/workspaces/{workspace_id}/comic/v2/assets/plan"},
        {"stage": "prompt_planning", "label": "重新生成资产与镜头提示词", "method": "POST", "path_template": "/api/workspaces/{workspace_id}/comic/v2/prompts/plan"},
        {"stage": "image_generation", "label": "重新生成并质检基础资产图", "method": "POST", "path_template": "/api/workspaces/{workspace_id}/comic/v2/images/generate"},
        {"stage": "visual_review", "label": "重新生成并质检基础资产图", "method": "POST", "path_template": "/api/workspaces/{workspace_id}/comic/v2/images/generate"},
        {"stage": "document_generation", "label": "重新生成 Word 制片画布", "method": "POST", "path_template": "/api/workspaces/{workspace_id}/comic/v2/delivery/build"},
        {
            "stage": "quality_review",
            "label": "按制片包质量基准退回责任部门",
            "method": "POST",
            "path_template": "/api/workspaces/{workspace_id}/comic/v2/quality/recover",
            "body_contract": {"action": "quality_benchmark.recommended_recovery.action"},
        },
    ],
    acceptance_criteria=[
        "本办公室必须使用独立的 office_id，不能和旧 AI 漫剧办公室混用底层配置。",
        "内阁先冻结故事合约，之后才能进入制片生产。",
        "中书省和门下省只负责任务书生成与审核，不直接替执行部门生产资产。",
        "尚书省接收带明确槽位的空白制片模板，并分派给各部门填写。",
        "户部维护资产登记表，不承担故事拆解职责。",
        "吏部保存连续性决策和版本变化，避免人物、道具、场景漂移。",
        "兵部产出的镜头画面提示词和视频提示词必须能被下游平台执行。",
        "工部组装生成资产和 Word 画布时，不能擅自改动故事合约。",
        "刑部在交付前标记缺图、泛化提示词、脚本绑定错误和不完整交付行。",
    ],
    default_template=(
        "Create an isolated AI comic-drama production package from the confirmed story. "
        "Follow the production office chain: story contract, Zhongshu production brief, "
        "Menxia review, Shangshu dispatch plan, Libu continuity bible, Hubu asset registry, "
        "Bingbu shot/video prompt plan, Gongbu assembly, Xingbu QA, and final Word canvas. "
        "User idea or confirmed story: {user_input}"
    ),
)


OFFICE_PROFILES = {
    RESEARCH_OFFICE.id: RESEARCH_OFFICE,
    COMIC_OFFICE.id: COMIC_OFFICE,
    COMIC_PRODUCTION_OFFICE.id: COMIC_PRODUCTION_OFFICE,
}


def list_offices() -> list[dict]:
    return [office.to_dict() for office in OFFICE_PROFILES.values()]


def list_office_protocols() -> list[dict]:
    return [_office_protocol(office) for office in OFFICE_PROFILES.values()]


def list_office_creation_template() -> dict:
    return {
        "required_profile_fields": [
            "id",
            "name",
            "description",
            "input_types",
            "output_types",
            "agent_duties",
            "artifact_types",
            "model_requirements",
            "human_checkpoints",
            "artifact_contract",
            "schema_gates",
            "recovery_actions",
            "acceptance_criteria",
            "default_template",
        ],
        "required_launch_gates": [
            "no_key_demo",
            "model_preflight",
            "end_to_end_test",
            "sample_delivery",
            "failure_recovery",
            "history_trace",
            "schema_gate",
            "readme_documentation",
            "secret_scan",
        ],
        "required_demo_contract": [
            "viewer_path",
            "proof_points",
            "downloadable_deliverables",
            "deliverable_reading_guide",
            "interview_demo_script",
            "post_run_validation",
            "public_claim_report",
            "public_safety_boundaries",
        ],
        "minimum_artifact_contract": _default_artifact_contract(),
        "notes": [
            "New offices must reuse the OfficeProfile protocol instead of copying one-off routes.",
            "Public showcase requires a no-key demo, model preflight, an end-to-end test, sample delivery files, post-run validation, a public claim report, failure recovery, history traceability, and a visitor-readable demo contract.",
        ],
    }


def list_office_extension_blueprint() -> dict:
    """Return the repeatable implementation path for future offices."""
    return {
        "purpose": "Give future offices a concrete path from idea to public-demo-ready workflow without sharing model config, history, artifacts, or runtime output with existing offices.",
        "starter_checklist_doc": "docs/NEW_OFFICE_STARTER_CHECKLIST.md",
        "implementation_steps": [
            {
                "order": 1,
                "id": "register_profile",
                "title": "Register an OfficeProfile",
                "owner": "platform",
                "files": ["src/offices.py"],
                "done_when": "The office has a unique id, agent duties, model requirements, checkpoints, artifact contract, schema gates, recovery actions, acceptance criteria, and default template.",
            },
            {
                "order": 2,
                "id": "isolate_runtime",
                "title": "Isolate runtime state",
                "owner": "platform",
                "files": ["src/config_manager.py", "src/office_runtime.py"],
                "done_when": "Model config, workspace id, artifacts, history, output paths, and recovery actions are scoped by office_id.",
            },
            {
                "order": 3,
                "id": "build_no_key_demo",
                "title": "Build a no-key demo contract",
                "owner": "office",
                "files": ["src/web/app.py", "tests/fixtures/"],
                "done_when": "The demo returns viewer_path, proof_points, downloadable_deliverables, deliverable_reading_guide, interview_demo_script, post_run_validation, public_claim_report, and public_safety_boundaries without calling real models.",
            },
            {
                "order": 4,
                "id": "wire_schema_and_recovery",
                "title": "Wire schema gates and recovery",
                "owner": "office",
                "files": ["src/offices.py", "src/web/app.py", "tests/"],
                "done_when": "Every long-running stage has a schema or artifact gate, a human-readable failure state, and a recovery action that explains what is preserved and what is cleared.",
            },
            {
                "order": 5,
                "id": "document_and_verify",
                "title": "Document, verify, and expose launch gates",
                "owner": "release",
                "files": ["README.md", "docs/", "scripts/verify_office_extension_governance.py"],
                "done_when": "README explains the office, launch-gates are ready or honestly blocked, no-key demo verifies, release readiness passes, and secret scan is clean.",
            },
        ],
        "minimum_implementation_package": [
            {
                "file": "src/offices.py",
                "proves": "The office has a unique OfficeProfile, declared model requirements, human checkpoints, artifact contract, schema gates, recovery actions, and acceptance criteria.",
            },
            {
                "file": "src/web/app.py",
                "proves": "The office exposes no-key demo endpoints, launch-gate evidence, model preflight, runtime status, post-run validation, public claim reporting, and downloadable sample artifacts without sharing another office's routes.",
            },
            {
                "file": "src/office_preflight.py",
                "proves": "The office explains missing text, image, vision, data, or tool capabilities before a user starts an expensive task.",
            },
            {
                "file": "tests/",
                "proves": "The new workflow has API, schema gate, post-run validation, recovery, history, and no-key demo coverage before it is shown as available.",
            },
            {
                "file": "README.md and docs/",
                "proves": "A stranger can understand what the office does, what it can download, what is demo-only, which claims are allowed or forbidden, which commands reproduce the result, and which checks prove a real run is safe to claim.",
            },
            {
                "file": "docs/NEW_OFFICE_STARTER_CHECKLIST.md",
                "proves": "Future offices have a repeatable product, safety, isolation, workflow, demo, quality, public-demo, and release checklist before feature work starts.",
            },
        ],
        "starter_checklist": [
            {
                "order": 1,
                "id": "define_user_job",
                "phase": "product",
                "question": "What painful job does this office finish for a human user?",
                "evidence": "A one-paragraph user job, expected input, expected output, and the reason this should be an office instead of a single prompt.",
            },
            {
                "order": 2,
                "id": "declare_boundaries",
                "phase": "safety",
                "question": "What must this office not claim or not touch?",
                "evidence": "Public safety boundaries, forbidden claims, and the list of keys, cookies, browser profiles, runtime output, and user data that must stay out of public assets.",
            },
            {
                "order": 3,
                "id": "scope_runtime_state",
                "phase": "isolation",
                "question": "Which model config, workspace, history, artifacts, and output paths are scoped by office_id?",
                "evidence": "Tests proving shared display department names do not share API keys, providers, workspace state, artifacts, or recovery actions.",
            },
            {
                "order": 4,
                "id": "design_human_checkpoints",
                "phase": "workflow",
                "question": "Where should the human review or correct the workflow before expensive generation continues?",
                "evidence": "Named checkpoints, what is preserved when a user rejects a stage, and which recovery action restarts only the affected stage.",
            },
            {
                "order": 5,
                "id": "create_sample_deliverables",
                "phase": "demo",
                "question": "What downloadable sample proves the office produces more than UI text?",
                "evidence": "At least one no-key sample deliverable, a manifest or audit file, and a reading guide explaining what each file proves.",
            },
            {
                "order": 6,
                "id": "add_schema_and_recovery_gates",
                "phase": "quality",
                "question": "How does the office prevent free-form model output from becoming an unverifiable blob?",
                "evidence": "Schema gates, post-run validation commands, failure states, preserved fields, cleared fields, and retry endpoints.",
            },
            {
                "order": 7,
                "id": "ship_public_demo_contract",
                "phase": "public_demo",
                "question": "Can a stranger understand and verify the office without an API key?",
                "evidence": "viewer_path, proof_points, downloadable_deliverables, deliverable_reading_guide, interview_demo_script, post_run_validation, public_claim_report, and public_safety_boundaries.",
            },
            {
                "order": 8,
                "id": "wire_release_gate",
                "phase": "release",
                "question": "Which single command proves the office is safe to show or honestly blocked?",
                "evidence": "Office-specific tests plus verify_office_isolation, verify_public_demo_mode, verify_office_extension_governance, verify_release_readiness, and check_no_secrets.",
            },
        ],
        "future_office_candidates": [
            {
                "id": "short_video_ads",
                "name": "短视频投放办公室",
                "user_job": "把产品卖点、素材、投放脚本和复盘数据组织成可执行的短视频投放工作流。",
                "not_ready_reason": "还缺可复现的投放样例、平台数据边界、素材审核规则和失败恢复动作。",
                "required_before_public": [
                    "no_key_demo",
                    "model_preflight",
                    "sample_delivery",
                    "schema_gate",
                    "failure_recovery",
                    "public_claim_report",
                    "public_safety_boundaries",
                ],
            },
            {
                "id": "ecommerce_selection",
                "name": "电商选品办公室",
                "user_job": "把市场需求、平台榜单、竞品价格带、评论痛点和供应链假设整理成选品决策包。",
                "not_ready_reason": "还缺真实数据来源边界、证据缺口标注、表格 schema 和可下载样例交付物。",
                "required_before_public": [
                    "no_key_demo",
                    "source_trace",
                    "sample_delivery",
                    "schema_gate",
                    "history_trace",
                    "public_claim_report",
                    "release_gate",
                ],
            },
            {
                "id": "story_ip",
                "name": "小说或短剧 IP 办公室",
                "user_job": "把一个故事 IP 拆成受众定位、人物资产、改编路线、分集卖点和可交付企划案。",
                "not_ready_reason": "还缺版权/素材边界、故事评审 schema、人工确认节点和作品集级样例。",
                "required_before_public": [
                    "no_key_demo",
                    "human_checkpoints",
                    "sample_delivery",
                    "schema_gate",
                    "recovery_actions",
                    "public_claim_report",
                    "public_safety_boundaries",
                ],
            },
            {
                "id": "technical_project",
                "name": "技术项目办公室",
                "user_job": "把技术需求拆成方案、任务、风险、实现记录、测试证据和可交接文档。",
                "not_ready_reason": "还缺代码仓库权限边界、测试证据采集、变更审计和失败恢复协议。",
                "required_before_public": [
                    "office_id_isolation",
                    "repo_boundary",
                    "sample_delivery",
                    "schema_gate",
                    "failure_recovery",
                    "public_claim_report",
                    "secret_scan",
                ],
            },
        ],
        "future_platform_backlog": [
            {
                "id": "future_schema_validators",
                "status": "future_office_required",
                "description": "Each future office must add concrete schema validators for its own model outputs instead of reusing comic or research validators.",
                "evidence_required": "Office-specific schema module, tests, launch-gate evidence, and a public demo artifact proving the schema gate ran.",
            },
            {
                "id": "future_recovery_events",
                "status": "future_office_required",
                "description": "Each future office must add explicit recovery events and retry actions for its own long-running stages.",
                "evidence_required": "Runtime status, task timeline, history trace, recovery endpoint, and tests showing what is preserved and what is cleared.",
            },
        ],
        "required_tests": [
            "tests.test_offices",
            "tests.test_office_preflight",
            "tests.test_office_extension_governance_verifier",
            "tests.test_frontend_comic_routing",
        ],
        "required_verifiers": [
            "python scripts/verify_office_isolation.py --format markdown",
            "python scripts/verify_office_extension_governance.py --format markdown",
            "python scripts/verify_public_demo_mode.py --format markdown",
            "python scripts/verify_release_readiness.py --format markdown",
            "python scripts/check_no_secrets.py",
        ],
        "non_negotiables": [
            "Do not reuse another office's office_id for runtime code.",
            "Do not put API keys, cookies, config.yaml, user_data, output, or browser profiles into public demo assets.",
            "Do not mark an office as primary unless its launch gates, sample delivery, history trace, schema gates, and recovery actions are all proven.",
            "Do not ship a public demo that only shows UI; it must include downloadable and reviewable deliverables.",
        ],
    }


LAUNCH_GATE_LABELS = {
    "no_key_demo": "无 Key 演示",
    "model_preflight": "模型预检",
    "end_to_end_test": "端到端测试",
    "sample_delivery": "样例交付物",
    "failure_recovery": "失败恢复",
    "history_trace": "历史追踪",
    "schema_gate": "结构化验收",
    "readme_documentation": "README 文档",
    "secret_scan": "密钥安全扫描",
}


LAUNCH_GATE_EVIDENCE = {
    "research": {
        "no_key_demo": "/api/demo/research exposes a read-only public demo.",
        "model_preflight": "/api/offices/research/preflight checks office-scoped models.",
        "end_to_end_test": "tests.test_office_preflight covers research demo/readiness paths.",
        "sample_delivery": "Research demo returns artifacts, viewer_path, and proof_points.",
        "failure_recovery": "Research profile declares evidence and artifact recovery actions.",
        "history_trace": "Research artifact contract requires source, version, agent, and reference_chain metadata.",
        "schema_gate": "Research profile declares report, source list, data table, and competitor table schema gates.",
        "readme_documentation": "README documents office protocols and public demo endpoints.",
        "secret_scan": "Readiness script and secret scan keep public source free of API keys.",
    },
    "comic_production": {
        "no_key_demo": "/api/demo/comic-production exposes a read-only public demo.",
        "model_preflight": "/api/offices/comic_production/preflight checks isolated office models.",
        "end_to_end_test": "tests cover comic production readiness, routing, history, and demo behavior.",
        "sample_delivery": "Comic production demo and history expose downloadable Word canvas artifacts.",
        "failure_recovery": "Comic production profile declares story, asset, prompt, image, and document recovery actions.",
        "history_trace": "Comic artifact contract requires office_id, source, version, responsible_agent, and reference_chain.",
        "schema_gate": "Comic production profile declares story, asset, prompt, shot, and image review schema gates.",
        "readme_documentation": "README documents model setup, safety modes, office protocols, and demos.",
        "secret_scan": "Repository checks include secret scan before public push.",
    },
}

LAUNCH_GATE_EVIDENCE_LINKS = {
    "research": {
        "sample_delivery": [
            {"label": "阶段调研报告", "uri": "/api/demo/research/files/report.md"},
            {"label": "证据清单", "uri": "/api/demo/research/files/evidence_manifest.json"},
        ],
        "no_key_demo": [
            {"label": "研究办公室无 Key 演示", "uri": "/api/demo/research"},
        ],
    },
    "comic_production": {
        "sample_delivery": [
            {"label": "Word 制片画布", "uri": "/api/demo/comic-production/files/word_canvas.docx"},
            {"label": "引用清单", "uri": "/api/demo/comic-production/files/handoff_manifest.json"},
        ],
        "no_key_demo": [
            {"label": "AI 漫剧制片办公室无 Key 演示", "uri": "/api/demo/comic-production"},
        ],
    },
}

LAUNCH_GATE_LABELS.update(
    {
        "no_key_demo": "无 Key 演示",
        "model_preflight": "模型预检",
        "end_to_end_test": "端到端测试",
        "sample_delivery": "样例交付物",
        "failure_recovery": "失败恢复",
        "history_trace": "历史追踪",
        "schema_gate": "结构化验收",
        "readme_documentation": "README 文档",
        "secret_scan": "密钥安全扫描",
    }
)

LAUNCH_GATE_EVIDENCE_LINKS.update(
    {
        "research": {
            "sample_delivery": [
                {"label": "阶段调研报告", "uri": "/api/demo/research/files/report.md"},
                {"label": "证据清单", "uri": "/api/demo/research/files/evidence_manifest.json"},
            ],
            "no_key_demo": [
                {"label": "研究办公室无 Key 演示", "uri": "/api/demo/research"},
            ],
        },
        "comic_production": {
            "sample_delivery": [
                {"label": "Word 制片画布", "uri": "/api/demo/comic-production/files/word_canvas.docx"},
                {"label": "引用清单", "uri": "/api/demo/comic-production/files/handoff_manifest.json"},
            ],
            "no_key_demo": [
                {"label": "AI 漫剧制片办公室无 Key 演示", "uri": "/api/demo/comic-production"},
            ],
        },
    }
)


PRIMARY_OFFICE_IDS = {"comic_production"}
LEGACY_OFFICE_IDS = {"comic"}
LEGACY_OFFICE_MIGRATIONS = {
    "comic": {
        "target_office_id": "comic_production",
        "target_office_name": "AI漫剧制片办公室",
        "reason": "旧 AI 漫剧办公室已被隔离版 V2 制片链覆盖；真实使用、无 Key 演示、历史追溯和失败恢复都应进入 comic_production。",
        "action": "在 UI、模型配置和 API 调用中使用 comic_production；旧 comic 只保留为兼容入口和迁移提示。",
    }
}

PRIMARY_OFFICE_STANDARDS = {
    "showcaseable": {
        "label": "可展示",
        "required_gates": ["no_key_demo", "readme_documentation"],
    },
    "trial_ready": {
        "label": "可试用",
        "required_gates": ["model_preflight", "end_to_end_test"],
    },
    "deliverable": {
        "label": "可交付",
        "required_gates": ["sample_delivery", "schema_gate"],
    },
    "traceable": {
        "label": "可追溯",
        "required_gates": ["history_trace", "failure_recovery", "secret_scan"],
    },
}


def audit_office_launch_gates(office_id: str) -> dict:
    """Return the productization gate audit for one office."""
    office = get_office(office_id)
    is_legacy = office.id in LEGACY_OFFICE_IDS
    required_gates = list_office_creation_template()["required_launch_gates"]
    evidence_by_gate = LAUNCH_GATE_EVIDENCE.get(office.id, {})
    gates = []

    for gate_id in required_gates:
        inferred_evidence = _infer_launch_gate_evidence(office, gate_id)
        evidence = evidence_by_gate.get(gate_id) or inferred_evidence
        status = "passed" if evidence_by_gate.get(gate_id) else ("passed" if inferred_evidence else "needs_work")
        gates.append(
            {
                "id": gate_id,
                "label": LAUNCH_GATE_LABELS.get(gate_id, gate_id),
                "status": status,
                "evidence": evidence or "No concrete evidence is declared for this office yet.",
                "evidence_links": LAUNCH_GATE_EVIDENCE_LINKS.get(office.id, {}).get(gate_id, []),
                "next_action": (
                    "Keep this evidence current when the office workflow changes."
                    if status == "passed"
                    else _launch_gate_next_action(gate_id)
                ),
            }
        )

    audit_status = "ready" if all(gate["status"] == "passed" for gate in gates) else "needs_work"
    return {
        "office_id": office.id,
        "office_name": office.name,
        "status": audit_status,
        "role": "legacy" if is_legacy else ("primary" if office.id in PRIMARY_OFFICE_IDS else "available"),
        "legacy_migration": LEGACY_OFFICE_MIGRATIONS.get(office.id, {}),
        "gates": gates,
    }


def audit_office_extension_governance() -> dict:
    """Audit whether office expansion follows the shared product protocol."""
    template = list_office_creation_template()
    required_profile_fields = template["required_profile_fields"]
    office_audits = []

    for office in OFFICE_PROFILES.values():
        launch_audit = audit_office_launch_gates(office.id)
        gate_statuses = {gate["id"]: gate["status"] for gate in launch_audit["gates"]}
        missing_profile_fields = [
            field
            for field in required_profile_fields
            if not _has_profile_field_value(office, field)
        ]
        standards = []
        for standard_id, standard in PRIMARY_OFFICE_STANDARDS.items():
            missing_gates = [
                gate_id
                for gate_id in standard["required_gates"]
                if gate_statuses.get(gate_id) != "passed"
            ]
            standards.append(
                {
                    "id": standard_id,
                    "label": standard["label"],
                    "status": "passed" if not missing_gates else "needs_work",
                    "required_gates": standard["required_gates"],
                    "missing_gates": missing_gates,
                }
            )
        is_legacy = office.id in LEGACY_OFFICE_IDS
        legacy_migration = LEGACY_OFFICE_MIGRATIONS.get(office.id, {})
        can_be_primary = not is_legacy and not missing_profile_fields and all(
            standard["status"] == "passed" for standard in standards
        )
        office_audits.append(
            {
                "office_id": office.id,
                "office_name": office.name,
                "role": (
                    "primary"
                    if office.id in PRIMARY_OFFICE_IDS
                    else "legacy"
                    if is_legacy
                    else "available"
                ),
                "protocol_status": (
                    "legacy_needs_upgrade"
                    if is_legacy and missing_profile_fields
                    else "passed"
                    if not missing_profile_fields
                    else "needs_work"
                ),
                "missing_profile_fields": missing_profile_fields,
                "launch_gate_status": launch_audit["status"],
                "legacy_migration": legacy_migration,
                "primary_standards": standards,
                "can_be_primary": can_be_primary,
                "primary_allowed": office.id in PRIMARY_OFFICE_IDS and can_be_primary,
            }
        )

    protocol_errors = [
        item["office_id"]
        for item in office_audits
        if item["role"] != "legacy" and item["protocol_status"] != "passed"
    ]
    primary_errors = [
        item["office_id"]
        for item in office_audits
        if item["office_id"] in PRIMARY_OFFICE_IDS and not item["primary_allowed"]
    ]
    return {
        "status": "passed" if not protocol_errors and not primary_errors else "failed",
        "mode": "offline_office_extension_governance",
        "primary_office_ids": sorted(PRIMARY_OFFICE_IDS),
        "required_profile_fields": required_profile_fields,
        "required_launch_gates": template["required_launch_gates"],
        "required_demo_contract": template["required_demo_contract"],
        "extension_blueprint": list_office_extension_blueprint(),
        "primary_standards": PRIMARY_OFFICE_STANDARDS,
        "offices": office_audits,
        "errors": {
            "protocol_errors": protocol_errors,
            "primary_errors": primary_errors,
        },
    }


def _has_profile_field_value(office: OfficeProfile, field: str) -> bool:
    value = getattr(office, field, None)
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, set, tuple)):
        return bool(value)
    return value is not None


def _infer_launch_gate_evidence(office: OfficeProfile, gate_id: str) -> str:
    if gate_id == "model_preflight" and office.model_requirements:
        return "Office profile declares model requirements for preflight checks."
    if gate_id == "failure_recovery" and office.recovery_actions:
        return "Office profile declares recovery actions for failed workflow stages."
    if gate_id == "history_trace" and office.artifact_contract:
        return "Office profile declares an artifact contract with traceability metadata."
    if gate_id == "schema_gate" and office.schema_gates:
        return "Office profile declares schema gates for structured acceptance."
    return ""


def _launch_gate_next_action(gate_id: str) -> str:
    actions = {
        "no_key_demo": "Add a read-only no-key demo endpoint before public showcase.",
        "model_preflight": "Declare office-scoped model requirements and expose a preflight check.",
        "end_to_end_test": "Add an automated end-to-end test for the office happy path.",
        "sample_delivery": "Publish at least one safe sample delivery artifact.",
        "failure_recovery": "Declare recovery actions for every long-running production stage.",
        "history_trace": "Attach source, version, responsible agent, and reference chain metadata to outputs.",
        "schema_gate": "Declare structured schema gates for the office artifacts.",
        "readme_documentation": "Document setup, demo mode, model needs, and safety boundaries in README.",
        "secret_scan": "Run a secret scan and keep API keys out of committed files.",
    }
    return actions.get(gate_id, "Declare concrete evidence and an owner for this launch gate.")


def _office_protocol(office: OfficeProfile) -> dict:
    return {
        "office_id": office.id,
        "office_name": office.name,
        "description": office.description,
        "input_types": office.input_types,
        "output_types": office.output_types,
        "agent_duties": office.agent_duties,
        "model_requirements": office.model_requirements,
        "human_checkpoints": office.human_checkpoints,
        "artifact_contract": office.artifact_contract or _default_artifact_contract(),
        "schema_gates": office.schema_gates,
        "recovery_actions": office.recovery_actions,
        "artifact_types": office.artifact_types,
        "acceptance_criteria": office.acceptance_criteria,
    }


def _default_artifact_contract() -> dict:
    return {
        "id_field": "artifact_id",
        "required_metadata": ["office_id", "source", "version", "responsible_agent", "reference_chain"],
        "trace_rule": "所有交付产物必须能追溯到来源、版本、责任 Agent 和上游引用。",
    }


def get_office(office_id: str) -> OfficeProfile:
    return OFFICE_PROFILES.get(office_id, RESEARCH_OFFICE)
