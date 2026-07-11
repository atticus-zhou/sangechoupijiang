"""Deterministic quality checks for comic V2 production prompts."""

from __future__ import annotations

from typing import Any


def audit_prompt_package(package: dict[str, Any] | None) -> dict[str, Any]:
    """Return a reviewer-friendly audit for asset and shot prompts."""
    package = package or {}
    prompts = list(package.get("prompts") or [])
    shots = list(package.get("shots") or [])
    asset_issues = _asset_prompt_issues(prompts)
    shot_issues = _shot_prompt_issues(shots)
    issue_count = len(asset_issues) + len(shot_issues)
    total = len(prompts) + len(shots)
    passed = total - issue_count
    return {
        "status": "ready" if total and not issue_count else ("waiting" if not total else "needs_review"),
        "summary": _summary(total, passed, issue_count),
        "asset_prompt_count": len(prompts),
        "shot_prompt_count": len(shots),
        "clean_asset_prompt_count": len(prompts) - len(asset_issues),
        "director_prompt_count": len(shots) - len(shot_issues),
        "issue_count": issue_count,
        "issues": asset_issues + shot_issues,
        "checks": [
            "人物和道具资产保持纯白或近白色干净背景",
            "场景资产保持空场景空间参考",
            "镜头视频提示词包含首帧参考、故事目的、动作链、表演意图、摄影和灯光",
            "负面提示词单独成段，并用“禁止”表达",
        ],
    }


def _summary(total: int, passed: int, issue_count: int) -> str:
    if not total:
        return "等待生成提示词包。"
    if issue_count:
        return f"提示词质量需要复核：{passed}/{total} 项通过，{issue_count} 项需要修改。"
    return f"提示词质量已达标：{passed}/{total} 项可交给下游生产。"


def _asset_prompt_issues(prompts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for prompt in prompts:
        object_id = str(prompt.get("object_id") or "")
        image_kind = str(prompt.get("image_kind") or "")
        generator = str(prompt.get("generator_prompt") or "")
        negative_items = [str(item) for item in (prompt.get("negative_prompt") or [])]
        negative_text = "；".join(negative_items)
        combined = f"{generator}；{negative_text}"
        label = f"{object_id}:{image_kind}" if image_kind else object_id or "asset_prompt"

        def add(message: str) -> None:
            issues.append({"scope": "asset_prompt", "id": label, "message": message})

        if "不要" in combined:
            add("提示词中仍有“不要”，请改成负面提示词里的“禁止”。")
        if not generator or not negative_items:
            add("缺少生成提示词或独立负面提示词。")
        if negative_items and not all(item.startswith("禁止") for item in negative_items):
            add("负面提示词每一项都应该用“禁止”开头。")
        if "资产ID" not in generator or "风格身份" not in generator:
            add("缺少资产 ID 或风格身份，后续一致性追溯会变弱。")

        if object_id.startswith("character_"):
            if "纯白或近白色干净背景" not in generator:
                add("人物资产必须要求纯白或近白色干净背景。")
            if image_kind == "three_view" and "三视图" not in generator:
                add("人物 three_view 必须明确三视图。")
            if image_kind == "expression_sheet" and "表情表" not in generator:
                add("人物 expression_sheet 必须明确表情表。")
            if "禁止剧情动作" not in negative_text or "禁止剧情场景" not in negative_text:
                add("人物资产负面提示词必须禁止剧情动作和剧情场景。")

        if object_id.startswith("prop_"):
            if "纯白或近白色干净背景" not in generator:
                add("道具资产必须要求纯白或近白色干净背景。")
            if image_kind == "turnaround" and not any(token in generator for token in ("多角度", "转面")):
                add("道具 turnaround 必须说明多角度或转面参考。")
            if "禁止人物手持或人物入镜" not in negative_text or "禁止剧情现场" not in negative_text:
                add("道具资产负面提示词必须禁止人物入镜和剧情现场。")

        if object_id.startswith("scene_"):
            if image_kind == "wide" and "广角空间图" not in generator:
                add("场景 wide 必须明确广角空间图。")
            if image_kind == "top_down" and "俯视" not in generator:
                add("场景 top_down 必须明确俯视空间参考。")
            if "只展示空场景" not in generator:
                add("场景资产必须保持空场景，不画剧情事件。")
            if "禁止人物和人物互动" not in negative_text or "禁止剧情事件" not in negative_text:
                add("场景资产负面提示词必须禁止人物互动和剧情事件。")
    return issues


def _shot_prompt_issues(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    required_markers = ("首帧参考", "故事目的", "动作链", "表演意图", "摄影", "灯光")
    for shot in shots:
        shot_id = str(shot.get("shot_id") or "shot_prompt")
        generator = str(shot.get("generator_prompt") or "")
        negative_items = [str(item) for item in (shot.get("negative_prompt") or [])]
        negative_text = "；".join(negative_items)
        combined = f"{generator}；{negative_text}"

        def add(message: str) -> None:
            issues.append({"scope": "shot_prompt", "id": shot_id, "message": message})

        if "不要" in combined:
            add("镜头提示词中仍有“不要”，请改成负面提示词里的“禁止”。")
        missing = [marker for marker in required_markers if marker not in generator]
        if missing:
            add("镜头提示词缺少导演字段：" + "、".join(missing))
        if not negative_items:
            add("镜头缺少独立负面提示词。")
        if negative_items and not all(item.startswith("禁止") for item in negative_items):
            add("镜头负面提示词每一项都应该用“禁止”开头。")
        if "严格继承参考资产" not in generator:
            add("镜头提示词必须明确继承参考资产身份。")
        if "禁止资产身份漂移" not in negative_text or "禁止动作顺序混乱" not in negative_text:
            add("镜头负面提示词必须覆盖资产身份漂移和动作顺序混乱。")
    return issues

