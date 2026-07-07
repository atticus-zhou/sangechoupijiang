"""Two-agent, evidence-bound asset planning for comic production V2."""

from __future__ import annotations

import json

from src.llm.providers import LLMFactory, LLMMessage, ModelConfig
from src.llm.robust_json import parse_json_object

from .asset_manifest import (
    AssetManifest,
    ManifestValidationError,
    NoManifestChangeError,
)
from .contracts import ContractBundle
from .output_schemas import AgentOutputSchemaError, validate_agent_output_schema


class AssetPlanningError(RuntimeError):
    """Raised when planning or review cannot produce a formal manifest."""


async def plan_asset_manifest(
    bundle: ContractBundle,
    planner_config: ModelConfig,
    reviewer_config: ModelConfig,
    *,
    revision_request: str = "",
    previous_manifest: AssetManifest | None = None,
    planner_llm=None,
    reviewer_llm=None,
) -> AssetManifest:
    """Generate a full inventory, then let a second model review its evidence and types."""
    if not _model_config_usable(planner_config):
        raise AssetPlanningError("中书省文本模型未配置，无法拆解资产")
    if not _model_config_usable(reviewer_config):
        raise AssetPlanningError("门下省文本模型未配置，无法审核资产拆解")
    note = str(revision_request or "").strip()
    if previous_manifest is not None and not note:
        raise AssetPlanningError("退回重拆必须包含用户修改意见")
    planner = planner_llm or LLMFactory.create(planner_config)
    reviewer = reviewer_llm or LLMFactory.create(reviewer_config)
    review_feedback: list[str] = []
    last_error = ""

    for _attempt in range(2):
        try:
            response = await planner.chat(
                [
                    LLMMessage(role="system", content=_asset_planner_system_prompt()),
                    LLMMessage(
                        role="user",
                        content=_asset_planner_user_prompt(
                            bundle,
                            revision_request=note,
                            previous_manifest=previous_manifest,
                            review_feedback=review_feedback,
                        ),
                    ),
                ],
                response_format={"type": "json_object"},
            )
            raw = (response.content or "").strip()
            if not raw or raw.startswith("[API错误]"):
                raise AssetPlanningError(
                    f"中书省模型调用失败：{raw.removeprefix('[API错误]').strip() or '返回空内容'}"
                )
            payload = parse_json_object(raw)
            assets = payload.get("assets") if isinstance(payload, dict) else None
            if not isinstance(assets, list) or not assets:
                raise AssetPlanningError("中书省没有返回完整资产数组")
            if previous_manifest is None:
                candidate = validate_agent_output_schema(
                    "comic_production",
                    "asset_manifest",
                    {"assets": assets},
                    context={"contract_bundle": bundle},
                )
            else:
                candidate = validate_agent_output_schema(
                    "comic_production",
                    "asset_manifest_revision",
                    {"assets": assets},
                    context={"previous_manifest": previous_manifest, "revision_request": note},
                )
                _ensure_revision_request_was_applied(previous_manifest, candidate, note)
        except NoManifestChangeError:
            last_error = "退回重拆没有产生变化"
            review_feedback = [last_error, "必须逐条落实用户退回意见并输出完整新清单"]
            continue
        except (ManifestValidationError, AgentOutputSchemaError, AssetPlanningError) as exc:
            last_error = str(exc)
            review_feedback = [last_error]
            continue

        verdict = await _review_manifest(bundle, candidate, reviewer)
        if verdict["status"] == "approved":
            return candidate
        review_feedback = verdict["issues"] or ["门下省未说明具体问题"]
        last_error = "；".join(review_feedback)

    raise AssetPlanningError(last_error or "资产拆解未通过门下省审核")


def _ensure_revision_request_was_applied(previous: AssetManifest, candidate: AssetManifest, note: str) -> None:
    normalized = str(note or "")
    asks_for_prop = any(word in normalized for word in ("缺少道具", "补道具", "补充道具", "增加道具", "新增道具"))
    if not asks_for_prop:
        return
    previous_props = {item.name for item in previous.items if item.asset_type == "prop"}
    candidate_props = {item.name for item in candidate.items if item.asset_type == "prop"}
    if len(candidate_props - previous_props) < 1:
        raise AssetPlanningError("用户退回意见要求补充道具，但新版资产清单没有新增道具；请补充故事中明确出现的道具，或在资产审核问题中解释为什么不能补。")

async def _review_manifest(bundle: ContractBundle, manifest: AssetManifest, reviewer) -> dict:
    response = await reviewer.chat(
        [
            LLMMessage(role="system", content=_asset_reviewer_system_prompt()),
            LLMMessage(
                role="user",
                content="\n".join(
                    [
                        "[确认故事]",
                        bundle.creative.source_story,
                        "[候选资产清单]",
                        json.dumps(manifest.to_dict(), ensure_ascii=False),
                    ]
                ),
            ),
        ],
        response_format={"type": "json_object"},
    )
    raw = (response.content or "").strip()
    if not raw or raw.startswith("[API错误]"):
        return {"status": "rejected", "issues": ["门下省模型调用失败"]}
    payload = parse_json_object(raw)
    status = str(payload.get("status") or "").strip().lower() if isinstance(payload, dict) else ""
    issues = payload.get("issues") if isinstance(payload, dict) else []
    if not isinstance(issues, list):
        issues = [str(issues)] if issues else []
    return {
        "status": "approved" if status == "approved" and not issues else "rejected",
        "issues": [str(item).strip() for item in issues if str(item).strip()],
    }


def _asset_planner_system_prompt() -> str:
    return "\n".join(
        [
            "你是 AI 漫剧制片办公室的中书省资产规划模型。",
            "输出确认故事中需要保持一致的完整人物、道具、场景清单，不生成图片提示词。",
            "人物必须是会行动、说话、被明确称呼或影响情节的生命角色；禁止把卡片、信件、物品数量词或短语片段当人物。",
            "道具必须是故事明确出现并会被持有、使用、发现或影响情节的实体物件。",
            "场景必须是故事明确发生动作的可复用空间，禁止为了画面丰富凭空添加地点。",
            "每个 name 与 evidence_quote 必须逐字出现在确认故事中，evidence_quote 要足以证明类型和用途。",
            "退回重拆时必须输出修改后的完整清单，禁止只输出新增项。",
            "planned_images 可省略，系统会按人物、道具、场景类型加入生产默认图组。",
            "只输出 JSON：{\"assets\":[{\"asset_type\":\"character|prop|scene\",\"name\":\"\",\"evidence_quote\":\"\",\"scene_ids\":[\"scene_01\"],\"story_purpose\":\"\",\"visual_locks\":[\"\"],\"allowed_changes\":[\"\"]}]}。",
            "禁止 Markdown 和额外解释。",
        ]
    )


def _asset_reviewer_system_prompt() -> str:
    return "\n".join(
        [
            "你是 AI 漫剧制片办公室的门下省资产审核模型。",
            "逐项核查：名称和证据是否来自原文、人物/道具/场景类型是否正确、关键资产是否遗漏、是否凭空增加资产。",
            "特别检查数量词和名词碎片被误判成人物，以及故事明确使用的关键道具被漏掉。",
            "只输出 JSON：{\"status\":\"approved|rejected\",\"issues\":[\"可执行的具体问题\"]}。",
            "存在任何问题时必须 rejected；完全通过时 issues 为空数组。",
        ]
    )


def _asset_planner_user_prompt(
    bundle: ContractBundle,
    *,
    revision_request: str,
    previous_manifest: AssetManifest | None,
    review_feedback: list[str],
) -> str:
    sections = [
        "[确认故事]",
        bundle.creative.source_story,
        "[视觉母版]",
        json.dumps(bundle.visual.__dict__, ensure_ascii=False),
    ]
    if previous_manifest is not None:
        sections.extend(
            [
                "[上一版完整资产清单]",
                json.dumps(previous_manifest.to_dict(), ensure_ascii=False),
                "[用户退回意见]",
                revision_request,
            ]
        )
    if review_feedback:
        sections.extend(["[门下省上一轮问题]", "\n".join(f"- {item}" for item in review_feedback)])
    sections.append("请输出覆盖全部人物、道具和场景的完整新清单。")
    return "\n".join(sections)


def _model_config_usable(config: ModelConfig | None) -> bool:
    if config is None or not str(config.model or "").strip():
        return False
    if str(config.api_key or "").strip() or str(config.provider or "").strip().lower() == "ollama":
        return True
    base = str(config.api_base or "").strip().lower()
    return base.startswith("http://localhost") or base.startswith("http://127.0.0.1")
