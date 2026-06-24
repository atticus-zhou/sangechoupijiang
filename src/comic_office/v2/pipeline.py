"""State machine for the isolated comic-production V2 pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

from .contracts import build_contract_bundle, story_hash


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
        missing = [name for name in fields if name not in payload]
        if missing:
            raise ValueError(f"V2 state missing fields: {', '.join(missing)}")
        return ComicProductionV2State(**{name: payload[name] for name in fields})


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
