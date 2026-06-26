"""State machine for the isolated comic-production V2 pipeline."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from .asset_manifest import AssetManifest
from .contracts import ContractBundle, build_contract_bundle, story_hash, validate_contract_bundle
from .production import ImageProductionResult, PromptPackage
from .word_canvas import DocumentAudit


@dataclass(frozen=True)
class ComicProductionV2State:
    pipeline_version: int
    workspace_id: str
    office_id: str
    status: str
    stage: str
    story_id: str
    story_version: int
    style_id: str
    style_version: int
    current_agent: str
    current_object: str
    completed: int
    total: int
    blocking_reason: str
    next_action: str
    can_generate_images: bool
    assets_status: str
    shots_status: str
    document_status: str
    contract: dict[str, Any]
    asset_manifest: dict[str, Any] = field(default_factory=dict)
    prompt_package: dict[str, Any] = field(default_factory=dict)
    image_production: dict[str, Any] = field(default_factory=dict)
    delivery: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_status(self, **changes: Any) -> "ComicProductionV2State":
        return replace(self, **changes)

    def replace_story(self, source_story: str) -> "ComicProductionV2State":
        """Invalidate every derived object when the confirmed story changes."""
        digest = story_hash(source_story)
        return replace(
            self,
            status="active",
            stage="story_confirmed",
            story_id=f"story_{digest[:12]}",
            story_version=self.story_version + 1,
            style_id="",
            style_version=self.style_version + 1,
            current_agent="中书省",
            current_object="故事合同与视觉母版",
            completed=0,
            blocking_reason="故事发生变化，旧视觉母版和全部下游资产已经失效。",
            next_action="重新生成并确认视觉母版。",
            can_generate_images=False,
            assets_status="stale",
            shots_status="stale",
            document_status="stale",
            contract={
                "status": "planning_required",
                "creative": {
                    "story_id": f"story_{digest[:12]}",
                    "story_version": self.story_version + 1,
                    "source_hash": digest,
                    "source_story": source_story,
                },
            },
            asset_manifest={},
            prompt_package={},
            image_production={},
            delivery={},
        )


class ComicProductionV2:
    """Factory and serializer for V2 pipeline states."""

    @staticmethod
    def start(
        source_story: str,
        planner_payload: dict[str, Any],
        *,
        workspace_id: str,
    ) -> ComicProductionV2State:
        bundle = build_contract_bundle(source_story, planner_payload)
        return ComicProductionV2.from_bundle(bundle, workspace_id=workspace_id)

    @staticmethod
    def from_bundle(
        bundle: ContractBundle,
        *,
        workspace_id: str,
    ) -> ComicProductionV2State:
        validate_contract_bundle(bundle)
        return ComicProductionV2State(
            pipeline_version=2,
            workspace_id=workspace_id,
            office_id="comic_production",
            status="active",
            stage="visual_bible_review",
            story_id=bundle.creative.story_id,
            story_version=bundle.creative.story_version,
            style_id=bundle.visual.style_id,
            style_version=bundle.visual.style_version,
            current_agent="中书省",
            current_object="故事合同与视觉母版",
            completed=1,
            total=4,
            blocking_reason="等待用户确认视觉母版，尚未进入资产拆解。",
            next_action="确认视觉母版，或退回修改视觉方向。",
            can_generate_images=False,
            assets_status="not_started",
            shots_status="not_started",
            document_status="not_started",
            contract=bundle.to_dict(),
        )

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> ComicProductionV2State:
        if not isinstance(payload, dict) or int(payload.get("pipeline_version") or 0) != 2:
            raise ValueError("not a comic production V2 state")
        fields = ComicProductionV2State.__dataclass_fields__
        normalized = dict(payload)
        normalized.setdefault("asset_manifest", {})
        normalized.setdefault("prompt_package", {})
        normalized.setdefault("image_production", {})
        normalized.setdefault("delivery", {})
        missing = [name for name in fields if name not in normalized]
        if missing:
            raise ValueError(f"V2 state missing fields: {', '.join(missing)}")
        return ComicProductionV2State(**{name: normalized[name] for name in fields})

    @staticmethod
    def approve_visual_bible(state: ComicProductionV2State) -> ComicProductionV2State:
        if state.stage != "visual_bible_review":
            raise ValueError("当前阶段不能确认视觉母版")
        contract = copy.deepcopy(state.contract)
        contract["status"] = "visual_bible_approved"
        return state.with_status(
            stage="asset_planning",
            current_agent="尚书省",
            current_object="资产拆解任务",
            completed=2,
            blocking_reason="",
            next_action="调用中书省生成带原文证据的人物、道具和场景清单。",
            can_generate_images=False,
            contract=contract,
        )

    @staticmethod
    def replace_visual_bible(
        state: ComicProductionV2State,
        revised_bundle: ContractBundle,
    ) -> ComicProductionV2State:
        validate_contract_bundle(revised_bundle)
        if revised_bundle.creative.story_id != state.story_id:
            raise ValueError("修改后的视觉母版属于另一份故事")
        if revised_bundle.creative.story_version != state.story_version:
            raise ValueError("修改后的视觉母版属于另一版故事")
        if revised_bundle.visual.style_version <= state.style_version:
            raise ValueError("视觉母版版本必须递增")
        contract = revised_bundle.to_dict()
        contract["status"] = "visual_bible_review"
        return state.with_status(
            status="active",
            stage="visual_bible_review",
            style_id=revised_bundle.visual.style_id,
            style_version=revised_bundle.visual.style_version,
            current_agent="中书省",
            current_object="修改后的视觉母版",
            completed=1,
            blocking_reason="视觉母版已按退回意见生成新版本，等待用户重新确认。",
            next_action="检查修改是否落实；确认后再进入资产拆解。",
            can_generate_images=False,
            assets_status="stale",
            shots_status="stale",
            document_status="stale",
            contract=contract,
            asset_manifest={},
            prompt_package={},
            image_production={},
            delivery={},
        )

    @staticmethod
    def attach_asset_manifest(
        state: ComicProductionV2State,
        manifest: AssetManifest,
    ) -> ComicProductionV2State:
        if state.stage not in {"asset_planning", "asset_review"}:
            raise ValueError("当前阶段不能写入资产拆解包")
        if manifest.story_id != state.story_id or manifest.story_version != state.story_version:
            raise ValueError("资产拆解包属于另一版故事")
        if manifest.style_id != state.style_id or manifest.style_version != state.style_version:
            raise ValueError("资产拆解包属于另一版视觉母版")
        return state.with_status(
            status="waiting_for_human",
            stage="asset_review",
            current_agent="门下省",
            current_object=f"资产拆解包 v{manifest.version}",
            completed=3,
            blocking_reason="等待用户确认人物、道具和场景清单。",
            next_action="确认资产拆解包，或写明遗漏、误判和多余项后退回重拆。",
            can_generate_images=False,
            assets_status="awaiting_user_review",
            asset_manifest=manifest.to_dict(),
            prompt_package={},
            image_production={},
            delivery={},
        )

    @staticmethod
    def approve_asset_manifest(state: ComicProductionV2State) -> ComicProductionV2State:
        if state.stage != "asset_review" or not state.asset_manifest:
            raise ValueError("当前没有可确认的资产拆解包")
        manifest = copy.deepcopy(state.asset_manifest)
        manifest["review_status"] = "approved"
        return state.with_status(
            status="active",
            stage="prompt_planning",
            current_agent="工部",
            current_object="逐项资产提示词",
            completed=4,
            blocking_reason="",
            next_action="为每张人物、道具和场景基础图生成专属提示词。",
            can_generate_images=False,
            assets_status="approved",
            asset_manifest=manifest,
        )

    @staticmethod
    def attach_prompt_package(
        state: ComicProductionV2State,
        package: PromptPackage,
    ) -> ComicProductionV2State:
        if state.stage != "prompt_planning" or state.assets_status != "approved":
            raise ValueError("资产未确认，不能写入提示词包")
        manifest = state.asset_manifest or {}
        if package.story_id != state.story_id or package.story_version != state.story_version:
            raise ValueError("提示词包属于另一版故事")
        if package.style_id != state.style_id or package.style_version != state.style_version:
            raise ValueError("提示词包属于另一版视觉母版")
        if package.manifest_id != manifest.get("manifest_id") or package.manifest_version != manifest.get("version"):
            raise ValueError("提示词包属于另一版资产清单")
        return state.with_status(
            status="active",
            stage="image_generation",
            current_agent="工部",
            current_object="基础资产图片",
            completed=5,
            blocking_reason="",
            next_action="生成基础资产图，并由刑部按参考链逐张质检。",
            can_generate_images=True,
            shots_status="ready",
            prompt_package=package.to_dict(),
            image_production={},
            delivery={},
        )

    @staticmethod
    def attach_image_production(
        state: ComicProductionV2State,
        result: ImageProductionResult,
    ) -> ComicProductionV2State:
        if state.stage not in {"image_generation", "visual_review"}:
            raise ValueError("当前阶段不能写入图片生产结果")
        if result.production_ready:
            return state.with_status(
                status="active",
                stage="document_generation",
                current_agent="礼部",
                current_object="页面式 Word 制片画布",
                completed=6,
                blocking_reason="",
                next_action="组装通过质检的资产图与镜头提示词卡，并执行文档审计。",
                can_generate_images=False,
                image_production=result.to_dict(),
            )
        return state.with_status(
            status="waiting_for_human",
            stage="visual_review",
            current_agent="刑部",
            current_object="未通过的资产图片",
            blocking_reason="部分图片未通过跨图一致性质检，需要人工决定重试或放行。",
            next_action="查看失败原因并重试；确需保留时填写人工放行理由。",
            can_generate_images=False,
            image_production=result.to_dict(),
        )

    @staticmethod
    def override_visual_review(
        state: ComicProductionV2State,
        reason: str,
    ) -> ComicProductionV2State:
        note = str(reason or "").strip()
        if state.stage != "visual_review":
            raise ValueError("当前没有待人工处理的视觉质检")
        if not note:
            raise ValueError("人工放行必须填写具体理由")
        production = copy.deepcopy(state.image_production)
        production["human_override"] = {
            "status": "approved_with_risk",
            "reason": note,
        }
        return state.with_status(
            status="active",
            stage="document_generation",
            current_agent="礼部",
            current_object="带人工风险说明的 Word 制片画布",
            completed=6,
            blocking_reason="",
            next_action="将人工放行理由写入交付文档，并继续文档审计。",
            can_generate_images=False,
            image_production=production,
        )

    @staticmethod
    def attach_delivery(
        state: ComicProductionV2State,
        path: str,
        audit: DocumentAudit,
        *,
        uri: str = "",
    ) -> ComicProductionV2State:
        if state.stage != "document_generation":
            raise ValueError("当前阶段不能写入交付文档")
        if not str(path or "").strip():
            raise ValueError("交付文档路径为空")
        if not audit.handoff_ready:
            raise ValueError("Word 文档审计未通过")
        return state.with_status(
            status="completed",
            stage="ready_for_handoff",
            current_agent="礼部",
            current_object="最终 Word 制片画布",
            completed=7,
            total=7,
            blocking_reason="",
            next_action="下载 Word 制片画布，交给下游视频生成或剪辑平台。",
            can_generate_images=False,
            document_status="ready",
            delivery={
                "path": str(path),
                "uri": str(uri or ""),
                "audit": asdict(audit),
            },
        )


def not_started_state(workspace_id: str) -> dict[str, Any]:
    return {
        "pipeline_version": 2,
        "workspace_id": workspace_id,
        "office_id": "comic_production",
        "status": "not_started",
        "stage": "story_confirmed",
        "current_agent": "中书省",
        "current_object": "已确认故事",
        "completed": 0,
        "total": 4,
        "blocking_reason": "尚未生成正式故事合同与视觉母版。",
        "next_action": "生成故事合同与视觉母版。",
        "can_generate_images": False,
        "assets_status": "not_started",
        "shots_status": "not_started",
        "document_status": "not_started",
    }
