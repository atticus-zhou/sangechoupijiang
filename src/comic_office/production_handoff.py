"""Production handoff artifacts for the isolated AI comic production office."""

from __future__ import annotations


def build_production_handoff_artifacts(task_id: str, result: dict) -> list[dict]:
    package = result.get("comic_package") or {}
    title = package.get("title") or "AI comic production"
    metadata = _metadata(package)
    artifacts = [
        _artifact(task_id, "production_brief", f"{title} - 制片任务书", _production_brief(package), "zhongshu", metadata, 1),
        _artifact(task_id, "dispatch_plan", f"{title} - 尚书省派发表", _dispatch_plan(package), "shangshu", metadata, 2),
        _artifact(task_id, "asset_registry", f"{title} - 资产登记表", _asset_registry(package), "hubu", metadata, 3),
        _artifact(task_id, "shot_prompt_handoff", f"{title} - 镜头导演提示词交接台", _shot_prompt_handoff(package), "bingbu", metadata, 4),
    ]
    return artifacts


def _artifact(task_id: str, artifact_type: str, title: str, content: str, created_by: str, metadata: dict, index: int) -> dict:
    return {
        "artifact_id": f"art_{task_id}_{artifact_type}_{index}",
        "task_id": task_id,
        "artifact_type": artifact_type,
        "title": title,
        "uri": "",
        "content": content,
        "metadata": metadata,
        "created_by": created_by,
    }


def _metadata(package: dict) -> dict:
    binding = package.get("script_binding") or {}
    confirmed = package.get("confirmed_script") or {}
    return {
        "office_id": "comic_production",
        "script_hash": binding.get("script_hash") or confirmed.get("script_hash", ""),
        "script_version": binding.get("script_version") or confirmed.get("script_version", 0),
        "script_confirmed": bool(binding.get("confirmed") or confirmed),
    }


def _production_brief(package: dict) -> str:
    confirmed = package.get("confirmed_script") or {}
    return "\n".join([
        "# 制片任务书",
        "",
        f"- 项目：{package.get('title', '')}",
        f"- 剧本版本：v{(package.get('script_binding') or {}).get('script_version', 0)}",
        f"- 剧本哈希：{(package.get('script_binding') or {}).get('script_hash', '')}",
        f"- 故事标题：{confirmed.get('title', package.get('title', ''))}",
        "",
        "## 已锁定故事",
        confirmed.get("story_draft", "") or "故事正文待补齐。",
        "",
        "## 生产要求",
        "- 不再改写故事，只允许拆解、生成、质检和组装。",
        "- 每个镜头必须绑定人物、道具、场景、镜头画面提示词和视频生成提示词。",
        "- 缺失内容必须进入刑部质检记录，而不是静默跳过。",
    ])


def _dispatch_plan(package: dict) -> str:
    rows = [
        "# 尚书省派发表",
        "",
        "| 部门 | 接收内容 | 必须产出 |",
        "| --- | --- | --- |",
        "| 吏部 | 已锁定故事、人物和世界观 | 连续性圣经、版本记录 |",
        "| 户部 | 人物、道具、场景清单 | 资产登记表、资源状态 |",
        "| 兵部 | 剧情节拍和镜头需求 | 镜头提示词交接卡 |",
        "| 工部 | 资产表和镜头提示词交接卡 | 基础资产图、提示词包、Word 画布 |",
        "| 刑部 | 全部产物 | 缺失项、串戏、提示词和画面一致性质检 |",
        "| 礼部 | 平台要求 | Libtv/图生视频交付说明 |",
    ]
    return "\n".join(rows)


def _asset_registry(package: dict) -> str:
    rows = [
        "# 资产登记表",
        "",
        "| 类型 | ID | 名称 | 生图提示词 |",
        "| --- | --- | --- | --- |",
    ]
    for asset_type, key in (("人物", "characters"), ("道具", "props"), ("场景", "scenes")):
        for item in package.get(key, []) or []:
            rows.append(f"| {asset_type} | {item.get('id', '')} | {item.get('name', '')} | {item.get('image_prompt', '')} |")
    return "\n".join(rows)


def _shot_prompt_handoff(package: dict) -> str:
    rows = [
        "# 镜头导演提示词交接台",
        "",
        "| 镜头 | 画面内容 | 参考资产 | 动作链 | 表演意图 | 摄影 | 灯光 | 镜头导演提示词 | 视频生成提示词 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for shot in package.get("shots", []) or []:
        rows.append(
            f"| {shot.get('id', '')} | {shot.get('beat', '')} | {shot.get('reference_assets', '')} | "
            f"{shot.get('action_chain', '')} | {shot.get('performance_intent', '')} | {shot.get('cinematography', '')} | "
            f"{shot.get('lighting', '')} | {shot.get('director_prompt') or shot.get('image_prompt', '')} | {shot.get('video_prompt', '')} |"
        )
    return "\n".join(rows)
