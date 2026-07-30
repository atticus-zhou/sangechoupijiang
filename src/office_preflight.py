"""Static office capability preflight checks.

The preflight is intentionally cheap: it does not call model providers. It only
checks whether the configured department models look capable of reaching each
major workflow stage, so the UI can tell users what will block later.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.image_generation import is_image_generation_config
from src.llm.providers import ModelConfig
from src.model_capabilities import summarize_office_capability_contract


AGENT_LABELS = {
    "zhongshu": "中书省",
    "menxia": "门下省",
    "shangshu": "尚书省",
    "ribu": "吏部",
    "libu": "礼部",
    "hubu": "户部",
    "bingbu": "兵部",
    "xingbu": "刑部",
    "gongbu": "工部",
}


@dataclass(frozen=True)
class CapabilityCheck:
    id: str
    title: str
    status: str
    required_agents: tuple[str, ...]
    impact: str
    next_action: str
    office_id: str
    owner_type: str
    owner_label: str
    model_kind: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "office_id": self.office_id,
            "owner_type": self.owner_type,
            "owner_label": self.owner_label,
            "model_kind": self.model_kind,
            "required_agents": list(self.required_agents),
            "impact": self.impact,
            "next_action": self.next_action,
        }


def build_office_preflight(
    office_id: str,
    get_model_config: Callable[[str, str], ModelConfig],
    *,
    base_dir: Path | str = ".",
) -> dict:
    """Return a user-facing static readiness summary for one office."""
    if office_id == "comic":
        office_id = "comic_production"
    if office_id != "comic_production":
        return _generic_preflight(office_id, get_model_config, base_dir=base_dir)
    return _comic_production_preflight(get_model_config, base_dir=base_dir)


def _comic_production_preflight(
    get_model_config: Callable[[str, str], ModelConfig],
    *,
    base_dir: Path | str,
) -> dict:
    office_id = "comic_production"
    model = lambda agent: get_model_config(agent, office_id)
    checks = [
        _requires_text(
            office_id,
            "story_planning",
            "故事确认与视觉母版",
            ("zhongshu",),
            model,
            "缺少中书省文本模型时，无法把确认故事转换成正式生产合同和视觉母版。",
            "先配置中书省文本模型：打开模型页面，选择 AI 漫剧制片办公室，为中书省填入文本模型 API Key 后测试。",
        ),
        _requires_text(
            office_id,
            "asset_planning",
            "资产拆解审核包",
            ("zhongshu", "menxia"),
            model,
            "缺少中书省或门下省文本模型时，人物、道具、场景拆解和审核会被阻塞。",
            "配置中书省和门下省文本模型：打开模型页面，分别填入可用的文本模型 API Key。",
        ),
        _requires_text_any(
            office_id,
            "prompt_planning",
            "专属提示词与镜头卡",
            ("zhongshu", "bingbu"),
            model,
            "缺少可用文本模型时，无法生成资产提示词和视频提示词。",
            "配置兵部文本模型；如果暂时没有，也要保证中书省文本模型可用作兜底。工部只在生图阶段填图片生成模型。",
        ),
        _requires_image(
            office_id,
            "image_generation",
            "基础资产图片生成",
            ("gongbu",),
            model,
            "缺少工部生图模型时，可以先完成故事、资产拆解和提示词，但不能生成图片。",
            "打开模型页面，为工部生图模型填入 API Key，例如 Seedream、MiniMax Image 或 Qwen Image。",
        ),
        _requires_vision(
            office_id,
            "visual_review",
            "跨图一致性质检",
            ("xingbu",),
            model,
            "缺少刑部视觉模型时，可以生成图片，但不能自动检查人物、道具、场景和画风一致性。",
            "打开模型页面，为刑部视觉模型填入 API Key，例如千问 VL、GPT 多模态或 Gemini 多模态。",
        ),
        _requires_writable_output(office_id, base_dir),
    ]
    return _summarize(office_id, checks)


def _generic_preflight(
    office_id: str,
    get_model_config: Callable[[str, str], ModelConfig],
    *,
    base_dir: Path | str,
) -> dict:
    model = lambda agent: get_model_config(agent, office_id)
    checks = [
        _requires_text(
            office_id,
            "text_workflow",
            "文本规划与交付",
            ("zhongshu", "menxia", "gongbu"),
            model,
            "缺少核心文本模型时，办公室无法完成规划、审核和交付。",
            "先配置中书省、门下省和工部文本模型。",
        ),
        _requires_writable_output(office_id, base_dir),
    ]
    return _summarize(office_id, checks)


def _summarize(office_id: str, checks: list[CapabilityCheck]) -> dict:
    blocking = [check for check in checks if check.status == "blocked"]
    missing = [check for check in checks if check.status == "missing"]
    if blocking:
        status = "blocked"
        summary = "核心能力未配置，暂时不建议开始工作。"
        next_action = blocking[0].next_action
    elif missing:
        status = "partial"
        summary = "可以先完成故事、视觉母版、资产拆解和提示词；图片生成或自动质检需要补齐模型。"
        next_action = missing[0].next_action
    else:
        status = "ready"
        summary = "当前办公室的关键能力已具备。"
        next_action = "可以开始工作。"
    return {
        "office_id": office_id,
        "status": status,
        "summary": summary,
        "next_action": next_action,
        "model_capability_contract": summarize_office_capability_contract(office_id),
        "blocking_reasons": [_blocking_reason(check) for check in blocking],
        "capabilities": [check.to_dict() for check in checks],
    }


def _blocking_reason(check: CapabilityCheck) -> str:
    if check.model_kind:
        return f"{check.owner_label}{check.model_kind}"
    return check.title


def _owner_label(agents: tuple[str, ...]) -> str:
    if not agents:
        return "本地系统"
    return "、".join(AGENT_LABELS.get(agent, agent) for agent in agents)


def _requires_text(
    office_id: str,
    check_id: str,
    title: str,
    agents: tuple[str, ...],
    model: Callable[[str], ModelConfig],
    impact: str,
    next_action: str,
) -> CapabilityCheck:
    missing = [agent for agent in agents if not _is_text_ready(model(agent))]
    return CapabilityCheck(
        id=check_id,
        title=title,
        status="ok" if not missing else "blocked",
        required_agents=agents,
        impact=impact,
        next_action="已具备。" if not missing else next_action,
        office_id=office_id,
        owner_type="department",
        owner_label=_owner_label(tuple(missing or agents)),
        model_kind="文本模型",
    )


def _requires_text_any(
    office_id: str,
    check_id: str,
    title: str,
    agents: tuple[str, ...],
    model: Callable[[str], ModelConfig],
    impact: str,
    next_action: str,
) -> CapabilityCheck:
    configs = [model(agent) for agent in agents]
    ready = any(_is_text_ready(config) for config in configs)
    return CapabilityCheck(
        id=check_id,
        title=title,
        status="ok" if ready else "blocked",
        required_agents=agents,
        impact=impact,
        next_action="已具备。" if ready else next_action,
        office_id=office_id,
        owner_type="department",
        owner_label=_owner_label(agents),
        model_kind="文本模型",
    )


def _requires_image(
    office_id: str,
    check_id: str,
    title: str,
    agents: tuple[str, ...],
    model: Callable[[str], ModelConfig],
    impact: str,
    next_action: str,
) -> CapabilityCheck:
    ready = any(_has_access(cfg) and is_image_generation_config(cfg) for cfg in (model(agent) for agent in agents))
    return CapabilityCheck(
        id=check_id,
        title=title,
        status="ok" if ready else "missing",
        required_agents=agents,
        impact=impact,
        next_action="已具备。" if ready else next_action,
        office_id=office_id,
        owner_type="department",
        owner_label=_owner_label(agents),
        model_kind="生图模型",
    )


def _requires_vision(
    office_id: str,
    check_id: str,
    title: str,
    agents: tuple[str, ...],
    model: Callable[[str], ModelConfig],
    impact: str,
    next_action: str,
) -> CapabilityCheck:
    ready = any(_is_vision_ready(model(agent)) for agent in agents)
    return CapabilityCheck(
        id=check_id,
        title=title,
        status="ok" if ready else "missing",
        required_agents=agents,
        impact=impact,
        next_action="已具备。" if ready else next_action,
        office_id=office_id,
        owner_type="department",
        owner_label=_owner_label(agents),
        model_kind="视觉模型",
    )


def _requires_writable_output(office_id: str, base_dir: Path | str) -> CapabilityCheck:
    output_dir = Path(base_dir) / "output"
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / ".preflight_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        status = "ok"
        next_action = "已具备。"
    except OSError:
        status = "blocked"
        next_action = "检查 output 目录权限，确保可以写入生成图片和 Word 文件。"
    return CapabilityCheck(
        id="local_output",
        title="本地输出目录",
        status=status,
        required_agents=(),
        impact="输出目录不可写时，图片、证据、Word 画布和导出包无法保存。",
        next_action=next_action,
        office_id=office_id,
        owner_type="config",
        owner_label="output 目录",
        model_kind="",
    )


def _is_text_ready(config: ModelConfig) -> bool:
    return _has_access(config) and not is_image_generation_config(config)


def _is_vision_ready(config: ModelConfig) -> bool:
    model = (config.model or "").lower()
    return _has_access(config) and not is_image_generation_config(config) and (
        "vl" in model or "vision" in model or "multimodal" in model
    )


def _has_access(config: ModelConfig) -> bool:
    api_base = config.api_base or ""
    return (
        bool(config.api_key)
        or config.provider.lower() == "ollama"
        or api_base.startswith("http://localhost")
        or api_base.startswith("http://127.0.0.1")
    )
