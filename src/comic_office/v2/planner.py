"""Model-backed planning for the comic-production V2 contract boundary."""

from __future__ import annotations

import json

from src.llm.providers import LLMFactory, LLMMessage, ModelConfig
from src.llm.robust_json import parse_json_object, retry_async

from .contracts import ContractBundle, ContractValidationError, build_contract_bundle


class PlannerError(RuntimeError):
    """Raised when a model response cannot become a formal V2 contract."""


async def plan_contract(
    source_story: str,
    model_config: ModelConfig,
    *,
    source_mode: str = "full_story",
    story_version: int = 1,
    style_version: int = 1,
    llm=None,
) -> ContractBundle:
    """Ask the configured text model for a candidate and validate it as a contract."""
    if not _model_config_usable(model_config):
        raise PlannerError("中书省文本模型未配置，无法生成正式故事合同与视觉母版")
    provider = llm or LLMFactory.create(model_config)

    async def request_candidate() -> ContractBundle:
        response = await provider.chat(
            [
                LLMMessage(role="system", content=_planner_system_prompt()),
                LLMMessage(role="user", content=_planner_user_prompt(source_story)),
            ],
            response_format={"type": "json_object"},
        )
        raw = (response.content or "").strip()
        if not raw or raw.startswith("[API错误]"):
            detail = raw.removeprefix("[API错误]").strip() or "模型返回空内容"
            raise PlannerError(f"模型调用失败：{detail}")
        payload = parse_json_object(raw)
        if not payload:
            raise PlannerError("模型没有返回可解析的 JSON 合同")
        try:
            return build_contract_bundle(
                source_story,
                payload,
                source_mode=source_mode,
                story_version=story_version,
                style_version=style_version,
            )
        except ContractValidationError as exc:
            raise PlannerError(f"模型合同未通过校验：{exc}") from exc

    try:
        return await retry_async(request_candidate, attempts=2, delay_seconds=0.2)
    except PlannerError:
        raise
    except Exception as exc:
        raise PlannerError(f"模型调用失败：{exc}") from exc


async def revise_visual_bible(
    current_contract: dict,
    revision_request: str,
    model_config: ModelConfig,
    *,
    llm=None,
) -> ContractBundle:
    """Revise only the visual bible while preserving the approved story contract."""
    creative = (current_contract or {}).get("creative") or {}
    current_visual = (current_contract or {}).get("visual") or {}
    if not creative or not current_visual:
        raise PlannerError("当前故事合同或视觉母版缺失")
    if not str(revision_request or "").strip():
        raise PlannerError("请说明需要修改的视觉方向")
    if not _model_config_usable(model_config):
        raise PlannerError("中书省文本模型未配置，无法修改视觉母版")
    provider = llm or LLMFactory.create(model_config)

    async def request_revision() -> ContractBundle:
        response = await provider.chat(
            [
                LLMMessage(role="system", content=_visual_revision_system_prompt()),
                LLMMessage(
                    role="user",
                    content="\n".join(
                        [
                            f"用户修改意见：{revision_request}",
                            "当前视觉母版：",
                            json.dumps(current_visual, ensure_ascii=False),
                            "故事原文（只用于校准时代与情绪，禁止改写）：",
                            str(creative.get("source_story") or ""),
                        ]
                    ),
                ),
            ],
            response_format={"type": "json_object"},
        )
        raw = (response.content or "").strip()
        if not raw or raw.startswith("[API错误]"):
            detail = raw.removeprefix("[API错误]").strip() or "模型返回空内容"
            raise PlannerError(f"模型调用失败：{detail}")
        parsed = parse_json_object(raw)
        visual = parsed.get("visual") if isinstance(parsed, dict) else None
        if not isinstance(visual, dict):
            raise PlannerError("模型没有返回可解析的视觉母版")
        if _visual_content(visual) == _visual_content(current_visual):
            raise PlannerError("模型没有落实本次视觉修改意见")
        payload = _creative_payload(creative)
        payload["visual"] = visual
        try:
            return build_contract_bundle(
                str(creative.get("source_story") or ""),
                payload,
                source_mode=str(creative.get("source_mode") or "full_story"),
                story_version=int(creative.get("story_version") or 1),
                style_version=int(current_visual.get("style_version") or 1) + 1,
            )
        except ContractValidationError as exc:
            raise PlannerError(f"修改后的视觉母版未通过校验：{exc}") from exc

    try:
        return await retry_async(request_revision, attempts=2, delay_seconds=0.2)
    except PlannerError:
        raise
    except Exception as exc:
        raise PlannerError(f"模型调用失败：{exc}") from exc


def _model_config_usable(config: ModelConfig | None) -> bool:
    if config is None or not str(config.model or "").strip():
        return False
    provider = str(config.provider or "").strip().lower()
    if str(config.api_key or "").strip():
        return True
    if provider == "ollama":
        return True
    api_base = str(config.api_base or "").strip().lower()
    return api_base.startswith("http://localhost") or api_base.startswith("http://127.0.0.1")


def _planner_system_prompt() -> str:
    schema = {
        "title": "作品名",
        "genre": "题材",
        "theme": "主题",
        "protagonist_goal": "主角的可执行目标",
        "main_conflict": "推动故事的主要冲突",
        "causal_chain": ["起因", "升级", "高潮", "结局"],
        "ending": "确认稿中的结局",
        "episodes": [
            {"episode": 1, "summary": "本集发生什么", "evidence_quote": "确认稿中的逐字短句"}
        ],
        "must_keep": ["必须保留的事实"],
        "must_avoid": ["用户明确排除的方向"],
        "visual": {
            "medium": "画面媒介与完成度",
            "era": "时代与技术边界",
            "aspect_ratio": "9:16",
            "palette": ["主色", "辅色", "强调色"],
            "lighting": "统一光线规则",
            "camera_language": "统一镜头语言",
            "character_rules": ["人物一致性规则"],
            "costume_rules": ["服装规则"],
            "prop_rules": ["道具规则"],
            "architecture_rules": ["场景建筑规则"],
            "visual_motifs": ["反复出现的视觉母题"],
            "prohibited_elements": ["禁止出现的元素"],
        },
    }
    return "\n".join(
        [
            "你是 AI 漫剧制片办公室的中书省规划模型。",
            "你的任务是从已经由用户确认的完整故事中提取制片合同和视觉母版候选。",
            "确认稿是最高事实来源：不得改写、续写、补角色、换结局或制造原文不存在的事件。",
            "每集 evidence_quote 必须逐字出现在确认稿中，短而明确。",
            "视觉规则必须服务于故事的时代、地点和情绪，禁止套用与故事无关的通用风格词。",
            "只输出一个 JSON 对象，禁止 Markdown，禁止解释。字段结构如下：",
            json.dumps(schema, ensure_ascii=False),
        ]
    )


def _planner_user_prompt(source_story: str) -> str:
    return "\n".join(
        [
            "请为下面的用户确认稿建立正式制片合同。",
            "[确认稿开始]",
            source_story,
            "[确认稿结束]",
            "再次确认：所有故事判断只能来自上面的确认稿。",
        ]
    )


def _visual_revision_system_prompt() -> str:
    return "\n".join(
        [
            "你是 AI 漫剧制片办公室的视觉母版修订模型。",
            "只修改 visual 对象，禁止改写故事、角色关系、情节和结局。",
            "用户意见必须落实为可检查的媒介、时代、色彩、光线、镜头、人物、服装、道具、建筑或禁用规则。",
            "保留 visual 的全部原字段，只输出 {\"visual\": {...}}，禁止 Markdown 和解释。",
        ]
    )


def _creative_payload(creative: dict) -> dict:
    return {
        "title": creative.get("title", ""),
        "genre": creative.get("genre", ""),
        "theme": creative.get("theme", ""),
        "protagonist_goal": creative.get("protagonist_goal", ""),
        "main_conflict": creative.get("main_conflict", ""),
        "causal_chain": list(creative.get("causal_chain") or []),
        "ending": creative.get("ending", ""),
        "episodes": [
            {
                "episode": item.get("episode"),
                "summary": item.get("summary", ""),
                "evidence_quote": item.get("evidence_quote", ""),
            }
            for item in (creative.get("episodes") or [])
        ],
        "must_keep": list(creative.get("must_keep") or []),
        "must_avoid": list(creative.get("must_avoid") or []),
    }


def _visual_content(visual: dict) -> str:
    ignored = {"style_id", "style_version", "story_id", "story_version"}
    content = {key: value for key, value in visual.items() if key not in ignored}
    return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
