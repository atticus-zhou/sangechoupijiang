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
    agent_duties: dict[str, str] = field(default_factory=dict)
    artifact_types: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    default_template: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


RESEARCH_OFFICE = OfficeProfile(
    id="research",
    name="研究办公室",
    description=(
        "用于产品调研、电商平台分析、竞品表格、证据截图、老板简报和开品决策的项目办公室。"
    ),
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
        "report",
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
    acceptance_criteria=[
        "最终报告必须有清晰的老板摘要。",
        "近期数据尽量标注年份、日期和来源。",
        "重要判断需要能追溯到来源说明或证据产物。",
        "头部竞品需要形成可对比表格；无法获取时要明确标注。",
        "评论痛点和差异化机会要拆成独立产物，不能只埋在正文里。",
        "图表和表格要作为独立材料输出，方便复制到汇报文件。",
        "需要截图取证的平台页面要列出截图目标。",
        "最终材料包应能直接用于职场交接或老板汇报。",
    ],
    default_template=(
        "Research the following product/category and prepare a workplace-ready product research package. "
        "Follow the research office playbook: industry overview, platform/channel data, top competitors, "
        "sales and price-band fields, title/selling-point keywords, user profile, review pain points, "
        "common success factors, differentiation opportunities, chart/table opportunities, screenshot/evidence "
        "needs, and launch/development recommendations. User request: {user_input}"
    ),
)


COMIC_OFFICE = OfficeProfile(
    id="comic",
    name="AI漫剧办公室",
    description=(
        "用于 AI 漫剧前期制作：完善剧本、拆人物/道具/场景、制定风格圣经、镜头提示词、视频提示词和一致性检查。"
    ),
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


def get_office(office_id: str) -> OfficeProfile:
    return OFFICE_PROFILES.get(office_id, RESEARCH_OFFICE)
