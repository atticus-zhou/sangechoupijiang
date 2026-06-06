"""Build AI comic office artifacts from a pre-production package."""

from __future__ import annotations

from src.comic_office.workflow import format_confirmed_script, format_creative_brief, format_script_preview


def build_comic_artifacts(task_id: str, result: dict) -> list[dict]:
    package = result.get("comic_package", {}) or {}
    title = package.get("title") or result.get("plan", {}).get("title") or "AI comic"
    artifact_meta = _artifact_metadata(package)
    artifacts = [
        _artifact("creative_brief", f"{title} - 创作锁定稿", _creative_brief_content(package), "zhongshu", artifact_meta),
        _artifact("script_preview", f"{title} - 内阁剧本预审", _script_preview_content(package), "cabinet", artifact_meta),
        _artifact("story_draft", f"{title} - 完整故事稿", _story_draft_content(package), "zhongshu", artifact_meta),
        _artifact("confirmed_script", f"{title} - 确认版剧本", _confirmed_script_content(package), "shangshu", artifact_meta),
        _artifact("cabinet_review", f"{title} - 内阁意见", _cabinet_review_content(package), "cabinet", artifact_meta),
        _artifact("script", f"{title} - 剧本方向", _script_content(package), "zhongshu", artifact_meta),
        _artifact("style_bible", f"{title} - 风格圣经", _style_content(package), "gongbu", artifact_meta),
        _artifact("asset_review_package", f"{title} - 资产拆解审核包", _asset_review_package(package), "menxia", {**artifact_meta, "requires_human_review": True, "review_status": "pending"}),
        _artifact("character_sheet", f"{title} - 人物图设定", _table_for(package.get("characters", [])), "hubu", artifact_meta),
        _artifact("prop_sheet", f"{title} - 道具图设定", _table_for(package.get("props", [])), "hubu", artifact_meta),
        _artifact("scene_sheet", f"{title} - 场景图设定", _table_for(package.get("scenes", [])), "hubu", artifact_meta),
        _artifact("storyboard_table", f"{title} - 分镜表", _storyboard_table(package), "bingbu", artifact_meta),
        _artifact("camera_plan", f"{title} - 运镜方案", _camera_plan(package), "bingbu", artifact_meta),
        _artifact("prompt_package", f"{title} - 提示词包", _prompt_package(package), "gongbu", artifact_meta),
        _artifact("production_canvas", f"{title} - 制片画布", _production_canvas(package), "gongbu", artifact_meta),
        _artifact("word_canvas", f"{title} - Word画布交付", _word_canvas_note(package), "gongbu", artifact_meta),
        _artifact("consistency_checklist", f"{title} - 一致性检查清单", _consistency_checklist(package), "xingbu", artifact_meta),
    ]
    for index, artifact in enumerate(artifacts, start=1):
        artifact["artifact_id"] = f"art_{task_id}_{artifact['artifact_type']}_{index}"
        artifact["task_id"] = task_id
    return artifacts


def _artifact(artifact_type: str, title: str, content: str, created_by: str, extra_metadata: dict | None = None) -> dict:
    return {
        "artifact_type": artifact_type,
        "title": title,
        "uri": "",
        "content": content,
        "metadata": {"office_id": "comic", **(extra_metadata or {})},
        "created_by": created_by,
    }


def _artifact_metadata(package: dict) -> dict:
    script_binding = package.get("script_binding", {}) or {}
    confirmed_script = package.get("confirmed_script", {}) or {}
    return {
        "script_hash": script_binding.get("script_hash", ""),
        "script_version": script_binding.get("script_version", 0),
        "script_confirmed": bool(script_binding.get("confirmed")),
        "script_source_type": script_binding.get("source_type", ""),
        "confirmed_script_artifact_id": confirmed_script.get("artifact_id", ""),
    }


def _creative_brief_content(package: dict) -> str:
    return "\n".join([
        f"# {package.get('title', 'AI漫剧')} 创作锁定稿",
        "",
        format_creative_brief(package.get("creative_brief", {}) or {}),
        "",
        "## 用户确认/补充",
        package.get("user_answers") or "暂无。建议先补充后再进入剧本预审。",
    ])


def _script_preview_content(package: dict) -> str:
    return format_script_preview(package.get("script_preview", {}) or {})


def _story_draft_content(package: dict) -> str:
    script = package.get("confirmed_script", {}) or package.get("script_preview", {}) or {}
    return "\n".join([
        f"# {package.get('title', 'AI漫剧')} 完整故事稿",
        "",
        script.get("story_draft") or "当前剧本尚未生成完整故事稿，请先回到内阁讨论并确认故事。",
    ])


def _cabinet_review_content(package: dict) -> str:
    lines = ["# 内阁意见", ""]
    for item in (package.get("script_preview", {}) or {}).get("cabinet_review", []) or []:
        lines.append(f"## {item.get('role', '')}")
        lines.append(f"- 职责：{item.get('responsibility', '')}")
        lines.append(f"- 结论：{item.get('verdict', '')}")
        lines.append(f"- 理由：{item.get('reason', '')}")
        lines.append("")
    return "\n".join(lines)


def _confirmed_script_content(package: dict) -> str:
    confirmed = package.get("confirmed_script", {}) or {}
    if not confirmed:
        return "\n".join([
            "# 确认版剧本缺失",
            "",
            "当前任务未附带确认版剧本。正常生产前应先由用户确认剧本，再进入资产生成。",
        ])
    return format_confirmed_script(confirmed)


def _script_content(package: dict) -> str:
    script = package.get("confirmed_script", {}) or package.get("script_preview", {}) or {}
    lines = [
        f"# {package.get('title', 'AI漫剧')} 剧本方向",
        "",
        f"- 题材：{package.get('genre', '')}",
        f"- 长度：{package.get('length', '')}",
        f"- 平台：{package.get('platform', '')}",
        "",
        "## 故事逻辑",
        f"- 为什么发生：{script.get('why_it_happens', '')}",
        f"- 如何发生：{script.get('how_it_happens', '')}",
        "",
        "## 剧本节拍",
    ]
    for beat in package.get("script_beats", []) or []:
        lines.append(f"- {beat.get('id')}: {beat.get('name')} - {beat.get('content')}")
    lines.append("")
    lines.append("## 分集节奏")
    for ep in package.get("episodes", []) or []:
        lines.append(f"- 第{ep.get('episode')}集：{ep.get('purpose')} / 钩子：{ep.get('ending_hook')}")
    return "\n".join(lines)


def _style_content(package: dict) -> str:
    style = package.get("visual_style", "")
    return "\n".join([
        f"# {package.get('title', 'AI漫剧')} 风格圣经",
        "",
        f"- 锁定画风：{style}",
        "- 画幅：默认竖屏优先，除非用户修改平台要求。",
        "- 色彩连续性：人物图、道具图、场景图和分镜图必须保持同一主色调体系。",
        "- 光线连续性：重复出现的场景必须保持同一主光方向。",
        "- 重生成规则：如果生成图破坏脸型、服装、色彩、道具状态或场景布局，先调整提示词/参考图再继续。",
    ])


def _asset_review_package(package: dict) -> str:
    lines = [
        f"# {package.get('title', 'AI漫剧')} 资产拆解审核包",
        "",
        "这个产物用于人在正式生图前审核：人物、道具、场景、剧情节拍和分镜输入是否贴合故事。",
        "",
        "## 审核结论",
        "- 状态：待审核",
        "- 通过后：尚书省再派发给户部/兵部/工部继续生产。",
        "- 不通过：回到中书省/门下省修改拆解，不应直接消耗生图额度。",
        "",
        "## 人物",
    ]
    for item in package.get("characters", []) or []:
        lines.append(f"- {item.get('id', '')}｜{item.get('name', '')}｜{item.get('role', '')}｜{item.get('image_prompt', '')}")
        lines.extend(_asset_spec_lines(item))
    lines.append("")
    lines.append("## 道具")
    for item in package.get("props", []) or []:
        lines.append(f"- {item.get('id', '')}｜{item.get('name', '')}｜{item.get('image_prompt', '')}")
        lines.extend(_asset_spec_lines(item))
    lines.append("")
    lines.append("## 场景")
    for item in package.get("scenes", []) or []:
        lines.append(f"- {item.get('id', '')}｜{item.get('name', '')}｜{item.get('image_prompt', '')}")
        lines.extend(_asset_spec_lines(item))
    lines.append("")
    lines.append("## 剧情节拍")
    for beat in package.get("script_beats", []) or []:
        lines.append(f"- {beat.get('id', '')}｜{beat.get('name', '')}｜{beat.get('content', '')}")
    lines.append("")
    lines.append("## 分镜输入")
    for shot in package.get("shots", []) or []:
        lines.append(
            f"- {shot.get('id', '')}｜{shot.get('beat', '')}｜人物：{', '.join(shot.get('characters', []))}｜"
            f"场景：{shot.get('scene', '')}｜道具：{', '.join(shot.get('props', []))}"
        )
    return "\n".join(lines)


def _asset_spec_lines(item: dict) -> list[str]:
    lines: list[str] = []
    for spec in item.get("asset_specs", []) or []:
        lines.append(
            f"  - {spec.get('label', spec.get('kind', 'asset'))}｜图片：{spec.get('image_ref', '')}｜验收：{spec.get('acceptance', '')}"
        )
        lines.append(f"    提示词：{spec.get('prompt', '')}")
    return lines


def _table_for(items: list[dict]) -> str:
    rows = ["| ID | 锚点 | 名称 | 锁定/连续性规则 | 生图提示词 |", "| --- | --- | --- | --- | --- |"]
    for item in items or []:
        rule = item.get("visual_lock") or item.get("continuity_rule") or ""
        rows.append(
            f"| {item.get('id', '')} | {item.get('anchor_id', '')} | {item.get('name', '')} | "
            f"{rule} | {item.get('image_prompt', '')} |"
        )
    return "\n".join(rows)


def _storyboard_table(package: dict) -> str:
    rows = [
        "| 镜头 | 锚点 | 剧情节拍 | Beat ID | 场景 | 人物 | 道具 | 景别 | 对应图片 | 生图提示词 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for shot in package.get("shots", []) or []:
        binding = shot.get("binding", {}) or {}
        rows.append(
            f"| {shot.get('id', '')} | {binding.get('anchor_id', '')} | {shot.get('beat', '')} | {binding.get('beat_id', '')} | {shot.get('scene', '')} | "
            f"{', '.join(shot.get('characters', []))} | {', '.join(shot.get('props', []))} | "
            f"{shot.get('framing', '')} | {shot.get('image_ref', '')} | {shot.get('image_prompt', '')} |"
        )
    return "\n".join(rows)


def _camera_plan(package: dict) -> str:
    rows = ["| 镜头 | 运镜方式 | 视频生成提示词 |", "| --- | --- | --- |"]
    for shot in package.get("shots", []) or []:
        rows.append(f"| {shot.get('id', '')} | {shot.get('camera_movement', '')} | {shot.get('video_prompt', '')} |")
    return "\n".join(rows)


def _prompt_package(package: dict) -> str:
    lines = ["# 提示词包", "", "## 资产提示词"]
    for group in ("characters", "props", "scenes"):
        labels = {"characters": "人物图", "props": "道具图", "scenes": "场景图"}
        lines.append(f"\n### {labels.get(group, group)}")
        for item in package.get(group, []) or []:
            lines.append(f"- {item.get('id')}: {item.get('image_prompt')}")
            for spec in item.get("asset_specs", []) or []:
                lines.append(f"  - {spec.get('label', spec.get('kind', 'asset'))}: {spec.get('prompt')}")
    global_negative = package.get("global_negative_prompt") or ""
    if global_negative:
        lines.extend(["", "## 全局负面提示词", global_negative])
    lines.append("\n## 分镜图提示词")
    for shot in package.get("shots", []) or []:
        lines.append(f"- {shot.get('id')} 对应图片 {shot.get('image_ref')}: {shot.get('image_prompt')}")
        lines.append(f"  视频提示词：{shot.get('video_prompt')}")
    return "\n".join(lines)


def _production_canvas(package: dict) -> str:
    rows = [
        f"# {package.get('title', 'AI漫剧')} 制片画布",
        "",
        "| 镜头 | 脚本版本 | 对应图片 | 画面内容 | 人物 | 场景 | 道具 | 分镜图提示词 | 视频/运镜提示词 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for shot in package.get("shots", []) or []:
        binding = shot.get("binding", {}) or {}
        rows.append(
            f"| {shot.get('id', '')} | v{binding.get('script_version', 0)} / {binding.get('beat_id', '')} | 对应图片：{shot.get('image_ref', '')} | {shot.get('beat', '')} | "
            f"{', '.join(shot.get('characters', []))} | {shot.get('scene', '')} | {', '.join(shot.get('props', []))} | "
            f"{shot.get('image_prompt', '')} | {shot.get('video_prompt', '')} |"
        )
    return "\n".join(rows)


def _word_canvas_note(package: dict) -> str:
    return "\n".join([
        "# Word画布交付",
        "",
        "正式任务完成后，系统会生成 .docx 文件。",
        "Word 中会用画布式表格展示：镜头、对应图片、人物、场景、道具、分镜图提示词、视频/运镜提示词和负面提示词。",
        "如果此资产没有下载链接，说明文档生成库不可用或任务尚未完成。",
    ])


def _consistency_checklist(package: dict) -> str:
    script_binding = package.get("script_binding", {}) or {}
    return "\n".join([
        "# 一致性检查清单",
        "",
        f"- 当前脚本版本：v{script_binding.get('script_version', 0)} / {script_binding.get('script_hash', '')}",
        f"- 当前脚本状态：{'已确认' if script_binding.get('confirmed') else '未确认，仅预审稿'}",
        "- 人物脸型必须匹配已锁定的人物图设定。",
        "- 发型、服装、年龄感和色彩点缀不能漂移。",
        "- 道具必须保持同一形状、破损状态和归属关系。",
        "- 重复场景必须保持同一空间布局和关键背景物。",
        "- 分镜图必须使用分镜表中指定的人物、道具、场景和 beat 锚点。",
        "- 运镜方案必须和镜头景别兼容。",
        "- 剧本一旦变更，必须按 script_hash 重新判断哪些人物、场景、镜头需要局部返工。",
        "- 未通过检查的图片必须先重生成，再扩展下一批镜头。",
    ])
