"""Deterministic quality checks for comic V2 production prompts."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


def audit_prompt_package(package: dict[str, Any] | None) -> dict[str, Any]:
    """Return a reviewer-friendly audit for asset and shot prompts."""
    package = package or {}
    prompts = list(package.get("prompts") or [])
    shots = list(package.get("shots") or [])
    asset_issues = _asset_prompt_issues(prompts)
    template_issues = _asset_template_copy_issues(prompts)
    shot_issues = _shot_prompt_issues(shots)
    issue_count = len(asset_issues) + len(template_issues) + len(shot_issues)
    total = len(prompts) + len(shots)
    passed = max(0, total - issue_count)
    prompt_ids_with_issues = _prompt_ids_with_issues(asset_issues + template_issues)
    return {
        "status": "ready" if total and not issue_count else ("waiting" if not total else "needs_review"),
        "summary": _summary(total, passed, issue_count),
        "recovery": _recovery(issue_count),
        "asset_prompt_count": len(prompts),
        "shot_prompt_count": len(shots),
        "clean_asset_prompt_count": max(0, len(prompts) - len(prompt_ids_with_issues)),
        "director_prompt_count": len(shots) - len(shot_issues),
        "issue_count": issue_count,
        "issues": asset_issues + template_issues + shot_issues,
        "checks": [
            "人物和道具资产保持纯白或近白色干净背景",
            "场景资产保持空场景空间参考",
            "基础资产提示词必须继承视觉母版的媒介、时代、光线和调色方向",
            "不同资产的提示词必须有专属内容，不能复制模板只替换名称",
            "镜头视频提示词包含原文依据、镜头形式、参考资产、故事目的、动作链、动作表演、摄影、灯光、台词、声音和连续性要求",
            "镜头提示词绑定首帧参考图片和机器可读资产引用链",
            "负面提示词单独成段，并用“禁止”表达",
        ],
    }


def _prompt_ids_with_issues(issues: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for issue in issues:
        raw = str(issue.get("id") or "")
        for part in raw.split("~"):
            ids.add(part.split(":", 1)[0])
    ids.discard("")
    return ids


def _summary(total: int, passed: int, issue_count: int) -> str:
    if not total:
        return "等待生成提示词包。"
    if issue_count:
        return f"提示词质量需要复核：{passed}/{total} 项通过，{issue_count} 项需要修改。"
    return f"提示词质量已达标：{passed}/{total} 项可交给下游生产。"


def _recovery(issue_count: int) -> dict[str, Any]:
    if issue_count:
        return {
            "recoverable": True,
            "department": "兵部 / 刑部",
            "impact": "提示词还不适合直接进入生图、视频生成或 Word 交付，继续生产可能导致资产不干净、镜头不连贯或下游无法复用。",
            "next_action": "回到提示词规划阶段重新生成专属提示词；如果问题来自资产定义，先退回资产拆解补充人物、道具、场景或视觉锁定。",
            "primary_action": "regenerate_prompts",
            "secondary_action": "revise_assets",
        }
    return {
        "recoverable": False,
        "department": "兵部 / 刑部",
        "impact": "提示词已满足基础交接标准，可以继续生成基础资产图或组装交付。",
        "next_action": "继续当前生产步骤。",
        "primary_action": "",
        "secondary_action": "",
    }


def _asset_prompt_issues(prompts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for prompt in prompts:
        object_id = str(prompt.get("object_id") or "")
        image_kind = str(prompt.get("image_kind") or "")
        generator = str(prompt.get("generator_prompt") or "")
        negative_items = [str(item) for item in (prompt.get("negative_prompt") or [])]
        negative_text = "；".join(negative_items)
        combined = f"{generator}；{negative_text}"
        production_role = str(prompt.get("production_role") or "")
        clean_background_required = prompt.get("clean_background_required")
        usage_contract = [str(item) for item in (prompt.get("usage_contract") or [])]
        reference_policy = str(prompt.get("reference_policy") or "")
        contract_text = "；".join(usage_contract)
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
        if not production_role:
            add("缺少 production_role，系统无法判断这张基础图是身份照、状态图还是空间参考。")
        if not usage_contract:
            add("缺少 usage_contract，用户和下游无法判断这张图是基础资产参考还是剧情镜头。")
        if usage_contract and ("基础资产" not in contract_text or "不负责讲述剧情" not in contract_text):
            add("usage_contract 必须明确基础资产只做一致性参考，不负责讲述剧情。")
        if not reference_policy:
            add("缺少 reference_policy，后续镜头不知道应该如何继承这张资产。")

        if object_id.startswith("character_"):
            if clean_background_required is not True:
                add("人物资产必须标记 clean_background_required=true。")
            if production_role and not production_role.startswith("clean_character_"):
                add("人物资产 production_role 必须是 clean_character_*。")
            if "纯白或近白色干净背景" not in generator:
                add("人物资产必须要求纯白或近白色干净背景。")
            if image_kind == "three_view" and "三视图" not in generator:
                add("人物 three_view 必须明确三视图。")
            if image_kind == "expression_sheet" and "表情表" not in generator:
                add("人物 expression_sheet 必须明确表情表。")
            if "禁止剧情动作" not in negative_text or "禁止剧情场景" not in negative_text:
                add("人物资产负面提示词必须禁止剧情动作和剧情场景。")
            if usage_contract and "角色" not in contract_text:
                add("人物资产 usage_contract 必须说明锁定角色身份。")

        if object_id.startswith("prop_"):
            if clean_background_required is not True:
                add("道具资产必须标记 clean_background_required=true。")
            if production_role and not production_role.startswith("clean_prop_"):
                add("道具资产 production_role 必须是 clean_prop_*。")
            if "纯白或近白色干净背景" not in generator:
                add("道具资产必须要求纯白或近白色干净背景。")
            if image_kind == "turnaround" and not any(token in generator for token in ("多角度", "转面")):
                add("道具 turnaround 必须说明多角度或转面参考。")
            if "禁止人物手持或人物入镜" not in negative_text or "禁止剧情现场" not in negative_text:
                add("道具资产负面提示词必须禁止人物入镜和剧情现场。")
            if usage_contract and "道具" not in contract_text:
                add("道具资产 usage_contract 必须说明锁定道具身份。")

        if object_id.startswith("scene_"):
            if clean_background_required is not False:
                add("场景资产必须标记 clean_background_required=false，避免被误做成白底静物图。")
            if production_role and not production_role.startswith("scene_"):
                add("场景资产 production_role 必须是 scene_*。")
            if image_kind == "wide" and "广角空间图" not in generator:
                add("场景 wide 必须明确广角空间图。")
            if image_kind == "top_down" and "俯视" not in generator:
                add("场景 top_down 必须明确俯视空间参考。")
            if "只展示空场景" not in generator:
                add("场景资产必须保持空场景，不画剧情事件。")
            if "禁止人物和人物互动" not in negative_text or "禁止剧情事件" not in negative_text:
                add("场景资产负面提示词必须禁止人物互动和剧情事件。")
            if usage_contract and "空场景" not in contract_text:
                add("场景资产 usage_contract 必须说明锁定空场景空间参考。")
    return issues


def _asset_template_copy_issues(prompts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[tuple[str, str, str, str]] = []
    for prompt in prompts:
        object_id = str(prompt.get("object_id") or "")
        object_name = str(prompt.get("object_name") or prompt.get("name") or "")
        image_kind = str(prompt.get("image_kind") or "")
        asset_type = _asset_type(object_id)
        body = _normalize_prompt(str(prompt.get("generator_prompt") or ""), object_id, object_name)
        normalized.append((object_id, image_kind, asset_type, body))

    issues: list[dict[str, Any]] = []
    for index, left in enumerate(normalized):
        for right in normalized[index + 1:]:
            left_id, left_kind, left_type, left_body = left
            right_id, right_kind, right_type, right_body = right
            if not left_id or not right_id or left_id == right_id:
                continue
            if left_type != right_type or left_kind != right_kind:
                continue
            if min(len(left_body), len(right_body)) < 60:
                continue
            ratio = SequenceMatcher(None, left_body, right_body).ratio()
            if ratio >= 0.92:
                issues.append({
                    "scope": "asset_prompt",
                    "id": f"{left_id}~{right_id}:{left_kind}",
                    "message": f"不同资产的 {left_kind or '基础图'} 提示词相似度 {ratio:.2f}，疑似复制模板后只替换名称，请重写专属视觉细节。",
                })
    return issues


def _asset_type(object_id: str) -> str:
    if object_id.startswith("character_"):
        return "character"
    if object_id.startswith("prop_"):
        return "prop"
    if object_id.startswith("scene_"):
        return "scene"
    return ""


def _normalize_prompt(text: str, object_id: str, object_name: str) -> str:
    value = str(text or "")
    for token in (object_id, object_name):
        if token:
            value = value.replace(token, "")
    sentences = re.split(r"[。；\n]+", value)
    filtered = [
        sentence
        for sentence in sentences
        if sentence.strip()
        and not any(marker in sentence for marker in ("风格身份", "画面比例", "资产ID", "资产名称"))
    ]
    return re.sub(r"[\s，,:：、]+", "", "。".join(filtered))


def _shot_prompt_issues(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    required_markers = ("原文依据", "镜头形式", "首帧参考", "参考资产", "故事目的", "动作链", "动作表演", "摄影", "灯光", "台词", "声音", "连续性要求")
    for shot in shots:
        shot_id = str(shot.get("shot_id") or "shot_prompt")
        generator = str(shot.get("generator_prompt") or "")
        negative_items = [str(item) for item in (shot.get("negative_prompt") or [])]
        first_frame = shot.get("first_frame_reference_image") or {}
        reference_chain = list(shot.get("reference_asset_chain") or [])
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
        if "严格继承参考资产" not in generator and "连续性要求" not in generator:
            add("镜头提示词必须明确继承参考资产身份。")
        for reference in reference_chain:
            name = str(reference.get("name") or "")
            if name and name not in generator:
                add(f"镜头提示词必须在参考资产段写明资产名称：{name}。")
        if not first_frame.get("image_id") or not first_frame.get("file") or not first_frame.get("asset_id"):
            add("镜头提示词必须绑定首帧参考图片的 image_id、file 和 asset_id。")
        if not reference_chain:
            add("镜头提示词必须提供机器可读 reference_asset_chain。")
        for reference in reference_chain:
            if not reference.get("asset_id") or not reference.get("asset_type") or not reference.get("name"):
                add("reference_asset_chain 每项都必须包含 asset_id、asset_type 和 name。")
        if "禁止资产身份漂移" not in negative_text or "禁止动作顺序混乱" not in negative_text:
            add("镜头负面提示词必须覆盖资产身份漂移和动作顺序混乱。")
    return issues
