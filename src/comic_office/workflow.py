"""AI comic office workflow helpers.

The comic office is a pre-production studio:

1. Lock the creative direction with the user.
2. Let a small cabinet review the script logic before asset production.
3. Produce script, assets, storyboards, prompts, and a Word delivery canvas.
"""

from __future__ import annotations

import hashlib
import json
import re

from src.llm.providers import LLMFactory, LLMMessage, ModelConfig
from src.llm.robust_json import parse_json_object, retry_async
from src.comic_office.memory import build_core_memory_vault, build_memory_context_prompt


DEFAULT_STYLE = "竖屏AI漫剧，电影感分镜，角色形象保持一致"

CABINET_ROLES = [
    ("首辅/制片人", "判断项目是否值得进入生产，控制交付边界和观众吸引力。"),
    ("编剧顾问", "检查故事为什么发生、如何发生、冲突是否成立。"),
    ("导演顾问", "检查分镜和运镜是否能把故事拍出来。"),
    ("美术顾问", "检查画风、人物、场景和道具是否能保持统一。"),
    ("连续性顾问", "检查前后剧情、人物动机和视觉设定是否打架。"),
]

CABINET_ROLE_MODEL_KEYS = {
    "首辅/制片人": "shangshu",
    "编剧顾问": "zhongshu",
    "导演顾问": "gongbu",
    "美术顾问": "gongbu",
    "连续性顾问": "xingbu",
}


def build_comic_brief(
    idea: str,
    genre: str = "",
    length: str = "",
    platform: str = "",
    visual_style: str = "",
    extra: str = "",
) -> dict:
    """Create the first conversational turn before full production."""
    core = (idea or "").strip()
    inferred_genre = (genre or "").strip() or _infer_genre(core + "\n" + extra)
    brief = {
        "core_idea": core,
        "story_promise": _story_promise(core, inferred_genre),
        "genre": inferred_genre,
        "length": (length or "").strip() or "待确认",
        "platform": (platform or "").strip() or "待确认",
        "visual_style": (visual_style or "").strip() or DEFAULT_STYLE,
        "tone": _infer_tone(core + "\n" + extra, inferred_genre),
        "main_conflict": _main_conflict(core, inferred_genre),
        "must_keep": (extra or "").strip() or "保留用户灵感中的核心人物、冲突、情绪方向和关键视觉元素。",
        "risk_of_drift": [
            "不要只拿灵感当关键词扩写，必须围绕核心冲突推进。",
            "人物、道具、场景和分镜都必须能回扣剧本。",
            "用户确认前不进入批量生图和分镜生产。",
        ],
        "clarifying_questions": _clarifying_questions(inferred_genre, length, platform, visual_style),
    }
    return {
        "status": "needs_user_confirmation",
        "creative_brief": brief,
        "preview": format_creative_brief(brief),
    }


def build_comic_script_preview(
    idea: str,
    genre: str = "",
    length: str = "",
    platform: str = "",
    visual_style: str = "",
    extra: str = "",
    creative_brief: dict | None = None,
    user_answers: str = "",
) -> dict:
    """Build the cabinet-reviewed script preview before asset production."""
    title = _clean_title(idea or (creative_brief or {}).get("core_idea", "未命名漫剧"))
    resolved_genre = (genre or (creative_brief or {}).get("genre") or _infer_genre(title + "\n" + extra)).strip()
    resolved_length = (length or (creative_brief or {}).get("length") or "3集，每集约60秒").strip()
    resolved_platform = (platform or (creative_brief or {}).get("platform") or "竖屏短视频平台").strip()
    resolved_style = (visual_style or (creative_brief or {}).get("visual_style") or DEFAULT_STYLE).strip()
    brief = creative_brief or build_comic_brief(title, resolved_genre, resolved_length, resolved_platform, resolved_style, extra)["creative_brief"]
    episode_count = _episode_count(resolved_length, default=3)
    why = _why_it_happens(title, resolved_genre, user_answers, brief)
    how = _how_it_happens(title, resolved_genre, user_answers, brief)
    outline = _episode_outline(title, resolved_genre, episode_count, why, how, user_answers)
    story_draft = _story_draft(
        title=title,
        genre=resolved_genre,
        why=why,
        how=how,
        outline=outline,
        protagonist_arc=_protagonist_arc(resolved_genre, user_answers),
        user_answers=user_answers,
        brief=brief,
    )
    preview = {
        "title": title,
        "genre": resolved_genre,
        "length": resolved_length,
        "platform": resolved_platform,
        "visual_style": resolved_style,
        "user_answers": user_answers,
        "logline": f"{title}：{brief.get('story_promise') or _story_promise(title, resolved_genre)}",
        "why_it_happens": why,
        "how_it_happens": how,
        "protagonist_arc": _protagonist_arc(resolved_genre, user_answers),
        "story_draft": story_draft,
        "episode_outline": outline,
        "key_turns": _key_turns(outline),
        "cabinet_review": _cabinet_review(title, resolved_genre, outline, resolved_style),
        "risks_before_production": [
            "如果用户不认同故事起因，后续角色和分镜会全部跑偏。",
            "如果结尾钩子不成立，短剧追看动力会不足。",
            "如果人物目标不可视化，生图和运镜会变成漂亮但无意义的画面。",
        ],
        "production_gate": "用户确认本预览稿后，三省六部才开始拆人物、场景、道具、分镜、图片和Word画布。",
    }
    return {
        "status": "script_needs_confirmation",
        "script_preview": preview,
        "preview": format_script_preview(preview),
    }


def build_comic_request(
    idea: str,
    genre: str = "",
    length: str = "",
    platform: str = "",
    visual_style: str = "",
    extra: str = "",
    creative_brief: dict | None = None,
    user_answers: str = "",
    script_preview: dict | None = None,
    confirmed_script: dict | None = None,
    script_notes: str = "",
) -> str:
    """Build a normalized comic-office request from UI fields."""
    parts = [
        f"Idea: {idea.strip()}",
        f"Genre: {genre.strip() or '自动判断'}",
        f"Length: {length.strip() or '短篇'}",
        f"Platform: {platform.strip() or '竖屏短视频平台'}",
        f"Visual style: {visual_style.strip() or DEFAULT_STYLE}",
        "Required output: 中文剧本方向、内阁剧本预审、人物/道具/场景拆解、风格圣经、分镜表、运镜方案、提示词包、制片画布和一致性检查清单。",
    ]
    if extra.strip():
        parts.append(f"Extra requirements: {extra.strip()}")
    if creative_brief:
        parts.append("Creative brief:")
        parts.append(format_creative_brief(creative_brief))
    if user_answers.strip():
        parts.append(f"User answers: {user_answers.strip()}")
    if script_preview:
        parts.append("Script preview:")
        parts.append(format_script_preview(script_preview))
    if confirmed_script:
        parts.append("Confirmed script:")
        parts.append(format_confirmed_script(confirmed_script))
    if script_notes.strip():
        parts.append(f"Script notes: {script_notes.strip()}")
    return "\n".join(parts)


def build_comic_result(task_id: str, user_request: str) -> dict:
    """Create a usable comic pre-production package."""
    spec = parse_comic_request(user_request)
    title = spec["title"]
    genre = spec["genre"]
    length = spec["length"]
    platform = spec["platform"]
    visual_style = spec["visual_style"]
    creative_brief = spec["creative_brief"] or build_comic_brief(
        idea=title,
        genre=genre,
        length=length,
        platform=platform,
        visual_style=visual_style,
        extra=spec["extra"],
    )["creative_brief"]
    script_preview = spec["script_preview"] or build_comic_script_preview(
        idea=title,
        genre=genre,
        length=length,
        platform=platform,
        visual_style=visual_style,
        extra=spec["extra"],
        creative_brief=creative_brief,
        user_answers=spec["user_answers"],
    )["script_preview"]
    if spec.get("full_script"):
        script_preview = _script_preview_from_full_script(
            title=title,
            full_script=spec["full_script"],
            genre=genre,
            platform=platform,
            visual_style=visual_style,
        )
    confirmed_script = spec["confirmed_script"] or {}
    script_source = confirmed_script or script_preview
    if confirmed_script:
        script_preview = {**script_preview, **confirmed_script}
    script_beats = _script_beats_from_preview(script_source)
    characters = _characters_for(title, genre, creative_brief, spec["user_answers"], script_source)
    props = _props_for(genre, script_source)
    scenes = _scenes_for(genre, script_source)
    _enrich_production_assets(title, visual_style, characters, props, scenes)
    episodes = _episodes_from_preview(script_source)
    shots = _shot_plan(characters, props, scenes, visual_style, script_beats)
    global_negative_prompt = "脸型变化、服装不一致、多余手指、背景扭曲、随机logo、不可读文字、画风漂移、画面标签、编号文字"
    script_binding = _script_binding_summary(task_id, script_source, bool(confirmed_script))
    consistency_bindings = _build_consistency_bindings(
        title=title,
        creative_brief=creative_brief,
        script_source=script_source,
        script_binding=script_binding,
        characters=characters,
        props=props,
        scenes=scenes,
        shots=shots,
        episodes=episodes,
        script_beats=script_beats,
    )

    final_report = _format_package_overview(
        title=title,
        genre=genre,
        length=length,
        platform=platform,
        visual_style=visual_style,
        creative_brief=creative_brief,
        script_preview=script_source,
        characters=characters,
        props=props,
        scenes=scenes,
        episodes=episodes,
        shots=shots,
    )
    return {
        "status": "completed",
        "task_id": task_id,
        "plan": {"title": f"{title} - AI漫剧前期制作包"},
        "final_report": final_report,
        "comic_package": {
            "title": title,
            "genre": genre,
            "length": length,
            "platform": platform,
            "visual_style": visual_style,
            "creative_brief": creative_brief,
            "script_preview": script_preview,
            "confirmed_script": confirmed_script,
            "script_notes": spec["script_notes"],
            "user_answers": spec["user_answers"],
            "script_binding": script_binding,
            "consistency_bindings": consistency_bindings,
            "script_beats": script_beats,
            "global_negative_prompt": global_negative_prompt,
            "characters": characters,
            "props": props,
            "scenes": scenes,
            "episodes": episodes,
            "shots": shots,
        },
    }


def parse_comic_request(user_request: str) -> dict:
    """Extract stable fields from a normalized or free-form comic request."""
    text = user_request or ""
    fields = {
        "idea": _line_value(text, "Idea") or _line_value(text, "创意") or _first_sentence(text),
        "genre": _line_value(text, "Genre") or _line_value(text, "题材"),
        "length": _line_value(text, "Length") or _line_value(text, "长度"),
        "platform": _line_value(text, "Platform") or _line_value(text, "平台"),
        "visual_style": _line_value(text, "Visual style") or _line_value(text, "风格"),
        "extra": _line_value(text, "Extra requirements") or _line_value(text, "创作指令"),
        "input_mode": _line_value(text, "Input mode"),
        "full_script": _section_after(
            text,
            "Full script",
            stop_markers=("Creative brief:", "User answers:", "Script preview:", "Confirmed script:", "Script notes:"),
        ),
        "user_answers": _section_after(
            text,
            "User answers",
            stop_markers=("Script preview:", "Confirmed script:", "Script notes:"),
        ),
        "script_notes": _section_after(text, "Script notes"),
    }
    title = fields["idea"] or "未命名漫剧"
    return {
        "title": _clean_title(title),
        "genre": fields["genre"] or _infer_genre(text),
        "length": fields["length"] or "3集，每集约60秒",
        "platform": fields["platform"] or "竖屏短视频平台",
        "visual_style": fields["visual_style"] or DEFAULT_STYLE,
        "extra": fields["extra"],
        "user_answers": fields["user_answers"],
        "script_notes": fields["script_notes"],
        "input_mode": fields["input_mode"] or ("full_script" if fields["full_script"] else "idea"),
        "full_script": fields["full_script"],
        "creative_brief": _parse_creative_brief(text),
        "script_preview": _parse_script_preview(text),
        "confirmed_script": _parse_confirmed_script(text),
    }


def _script_preview_from_full_script(
    title: str,
    full_script: str,
    genre: str,
    platform: str,
    visual_style: str,
) -> dict:
    """Turn a user-provided script into the same structure as an idea draft."""
    script_text = (full_script or "").strip()
    sentences = _story_sentences(script_text, limit=8)
    key_turns = [sentence for sentence in sentences[1:4] if sentence]
    if not key_turns and script_text:
        key_turns = [script_text[:120]]
    return {
        "title": title,
        "status": "ready_to_confirm",
        "logline": sentences[0] if sentences else title,
        "story_promise": f"以用户提供的完整剧本为准，拆解人物、道具、场景、分镜和提示词资产。",
        "main_conflict": _extract_conflict_from_text(script_text) or "按用户剧本中的主要矛盾推进。",
        "why_it_happens": sentences[0] if sentences else "用户已提供完整剧本。",
        "how_it_happens": "从完整剧本文本中提取人物行动、关键转折、场景变化和视觉资产。",
        "protagonist_arc": _extract_arc_from_text(script_text) or "按完整剧本中的人物变化执行。",
        "story_draft": script_text,
        "episode_outline": _episode_outline_from_full_script(script_text),
        "key_turns": key_turns,
        "platform": platform,
        "visual_style": visual_style,
        "genre": genre,
        "production_gate": "用户已提供完整剧本，可直接进入资产拆解审核。",
    }


def _extract_conflict_from_text(text: str) -> str:
    for sentence in _story_sentences(text, limit=12):
        if any(token in sentence for token in ("冲突", "阻止", "反对", "追杀", "陷害", "背叛", "危机", "死亡", "失去")):
            return sentence
    return ""


def _extract_arc_from_text(text: str) -> str:
    for sentence in reversed(_story_sentences(text, limit=12)):
        if any(token in sentence for token in ("决定", "明白", "改变", "成长", "放弃", "选择", "拒绝", "承认")):
            return sentence
    return ""


def _episode_outline_from_full_script(text: str) -> list[dict]:
    sentences = _story_sentences(text, limit=9)
    if not sentences:
        return []
    chunks = [sentences[i:i + 3] for i in range(0, min(len(sentences), 9), 3)]
    outline = []
    for index, chunk in enumerate(chunks, start=1):
        outline.append({
            "episode": index,
            "title": _short_story_label(chunk[0]),
            "cause": chunk[0],
            "action": chunk[1] if len(chunk) > 1 else chunk[0],
            "turn": chunk[2] if len(chunk) > 2 else (chunk[-1] if chunk else ""),
            "hook": chunk[-1] if chunk else "",
        })
    return outline


def format_creative_brief(brief: dict) -> str:
    questions = brief.get("clarifying_questions") or []
    lines = [
        f"- 核心灵感：{brief.get('core_idea', '')}",
        f"- 故事承诺：{brief.get('story_promise', '')}",
        f"- 题材：{brief.get('genre', '')}",
        f"- 情绪：{brief.get('tone', '')}",
        f"- 主冲突：{brief.get('main_conflict', '')}",
        f"- 必须保留：{brief.get('must_keep', '')}",
        "",
        "需要你确认的问题：",
    ]
    lines.extend([f"{idx}. {question}" for idx, question in enumerate(questions, start=1)])
    return "\n".join(lines)


def format_script_preview(script: dict) -> str:
    lines = [
        f"# {script.get('title', '未命名漫剧')} (故事提案)",
        "",
        f"- 一句话故事：{script.get('logline', '')}",
        f"- 核心动力：{script.get('why_it_happens', '')}",
        f"- 故事走向：{script.get('how_it_happens', '')}",
        f"- 主角变化：{script.get('protagonist_arc', '')}",
        "",
        "## 完整故事稿",
        script.get("story_draft", ""),
        "",
        "## 关键转折",
    ]
    for turn in script.get("key_turns", []) or []:
        lines.append(f"- {turn}")
    return "\n".join(lines)


def format_confirmed_script(script: dict) -> str:
    lines = [
        f"# {script.get('title', '未命名漫剧')} 确认版剧本",
        "",
        f"- 状态：{script.get('status', '已确认')}",
        f"- 剧本版本：{script.get('script_version', 1)}",
        f"- 剧本哈希：{script.get('script_hash', '')}",
        f"- 故事承诺：{script.get('story_promise', '')}",
        f"- 主冲突：{script.get('main_conflict', '')}",
        f"- 一句话故事：{script.get('logline', '')}",
        f"- 为什么发生：{script.get('why_it_happens', '')}",
        f"- 如何发生：{script.get('how_it_happens', '')}",
        f"- 主角变化：{script.get('protagonist_arc', '')}",
        f"- 平台：{script.get('platform', '')}",
        f"- 视觉风格：{script.get('visual_style', '')}",
        "",
        "## 完整故事稿",
        script.get("story_draft", ""),
        "",
        "## 每集确认大纲",
    ]
    for ep in script.get("episode_outline", []) or []:
        lines.append(
            f"{ep.get('episode')}. {ep.get('title')}｜起因：{ep.get('cause')}｜行动：{ep.get('action')}｜转折：{ep.get('turn')}｜钩子：{ep.get('hook')}"
        )
    lines.extend(["", "## 关键转折"])
    for turn in script.get("key_turns", []) or []:
        lines.append(f"- {turn}")
    lines.extend(["", "## 内阁共识"])
    for item in script.get("cabinet_consensus", []) or []:
        lines.append(f"- {item.get('role', '')}：{item.get('verdict', '')}｜{item.get('comment', '')}")
    lines.extend([
        "",
        "## 用户最终要求",
        script.get("confirmation_notes") or "用户认可当前剧本方向，未追加新的最终修改说明。",
        "",
        f"生产闸门：{script.get('production_gate', '已确认，可进入人物/场景/分镜/提示词生产。')}",
    ])
    return "\n".join(lines)


def build_confirmed_script(session: dict, confirmation_notes: str = "") -> dict:
    creative_brief = (session or {}).get("creative_brief") or {}
    script_preview = (session or {}).get("script_preview") or {}
    if not creative_brief or not script_preview:
        return {}
    answers = "\n".join((session or {}).get("user_notes") or []).strip()
    confirmed = {
        "title": script_preview.get("title") or _clean_title(creative_brief.get("core_idea", "")),
        "status": "confirmed",
        "genre": creative_brief.get("genre", ""),
        "length": creative_brief.get("length", ""),
        "platform": creative_brief.get("platform", ""),
        "visual_style": creative_brief.get("visual_style", ""),
        "story_promise": creative_brief.get("story_promise", ""),
        "main_conflict": creative_brief.get("main_conflict", ""),
        "logline": script_preview.get("logline", ""),
        "why_it_happens": script_preview.get("why_it_happens", ""),
        "how_it_happens": script_preview.get("how_it_happens", ""),
        "protagonist_arc": script_preview.get("protagonist_arc", ""),
        "story_draft": script_preview.get("story_draft", ""),
        "episode_outline": _confirmed_episode_outline(script_preview),
        "key_turns": _clean_key_turns(script_preview.get("key_turns") or []),
        "user_alignment": answers,
        "cabinet_consensus": [
            {
                "role": item.get("role", ""),
                "verdict": item.get("verdict", ""),
                "comment": item.get("comment") or item.get("reason", ""),
            }
            for item in (session or {}).get("cabinet_roles") or []
        ],
        "confirmation_notes": (confirmation_notes or "").strip(),
        "production_gate": "已确认，可进入人物/场景/道具/分镜/提示词/图片生产。",
    }
    confirmed["script_version"] = 1
    confirmed["script_hash"] = _stable_script_hash(confirmed)
    return confirmed


def validate_confirmed_script_session(session: dict) -> list[str]:
    creative_brief = (session or {}).get("creative_brief") or {}
    script_preview = (session or {}).get("script_preview") or {}
    combined = "\n".join(filter(None, [
        creative_brief.get("core_idea", ""),
        creative_brief.get("main_conflict", ""),
        script_preview.get("why_it_happens", ""),
        script_preview.get("how_it_happens", ""),
        script_preview.get("protagonist_arc", ""),
        "\n".join((session or {}).get("user_notes") or []),
    ]))
    issues = []
    has_protagonist_anchor = bool(
        _has_story_anchor(combined, "protagonist")
        or (script_preview.get("story_draft") and script_preview.get("protagonist_arc"))
    )
    has_conflict_anchor = bool(
        _has_story_anchor(combined, "conflict")
        or creative_brief.get("main_conflict")
        or script_preview.get("why_it_happens")
        or script_preview.get("how_it_happens")
    )
    if not has_protagonist_anchor:
        issues.append("缺少明确的主角锚点")
    if not has_conflict_anchor:
        issues.append("缺少明确的核心冲突")
    confirmed_outline = _confirmed_episode_outline(script_preview)
    outline_hooks = " ".join(str(item.get("hook", "")) for item in confirmed_outline)
    ending_source = "\n".join(filter(None, [
        combined,
        " ".join(script_preview.get("key_turns") or []),
        outline_hooks,
        _first_hook(script_preview),
    ]))
    has_production_ending = bool(
        (session or {}).get("ready_to_produce")
        and script_preview.get("story_draft")
        and confirmed_outline
    )
    if not _has_story_anchor(ending_source, "ending") and not has_production_ending:
        issues.append("缺少明确的结尾或钩子方向")
    if not creative_brief.get("visual_style"):
        issues.append("缺少视觉风格")
    if not creative_brief.get("platform"):
        issues.append("缺少目标平台")
    if not _confirmed_episode_outline(script_preview):
        issues.append("缺少分集大纲")
    return issues


def _confirmed_episode_outline(script_preview: dict) -> list[dict]:
    outline = list((script_preview or {}).get("episode_outline") or [])
    if outline:
        return outline
    story_draft = (script_preview or {}).get("story_draft", "").strip()
    logline = (script_preview or {}).get("logline", "").strip()
    if not story_draft and not logline:
        return []
    key_turns = list((script_preview or {}).get("key_turns") or [])
    first_turn = key_turns[0] if key_turns else ((script_preview or {}).get("protagonist_arc", "").strip() or "主角完成关键选择")
    hook = key_turns[-1] if key_turns else "结尾留下下一步生产需要延续的画面钩子"
    return [
        {
            "episode": 1,
            "title": "确认故事",
            "cause": logline or story_draft[:80],
            "action": "围绕完整故事稿拆分人物、场景、道具和关键画面",
            "turn": first_turn,
            "hook": hook,
        }
    ]


def start_comic_cabinet_session(
    idea: str,
    genre: str = "",
    length: str = "",
    platform: str = "",
    visual_style: str = "",
    extra: str = "",
) -> dict:
    """Start a multi-turn cabinet discussion before production."""
    session = {
        "idea": (idea or "").strip(),
        "genre": (genre or "").strip(),
        "length": (length or "").strip(),
        "platform": (platform or "").strip(),
        "visual_style": (visual_style or "").strip(),
        "extra": (extra or "").strip(),
        "messages": [],
        "user_notes": [],
        "turn_count": 0,
    }
    return advance_comic_cabinet_session(session, "")


async def start_comic_cabinet_session_llm(
    idea: str,
    genre: str = "",
    length: str = "",
    platform: str = "",
    visual_style: str = "",
    extra: str = "",
    role_model_configs: dict[str, ModelConfig] | None = None,
) -> dict:
    """Start a cabinet discussion with per-role LLM prompts when available."""
    session = {
        "idea": (idea or "").strip(),
        "genre": (genre or "").strip(),
        "length": (length or "").strip(),
        "platform": (platform or "").strip(),
        "visual_style": (visual_style or "").strip(),
        "extra": (extra or "").strip(),
        "messages": [],
        "user_notes": [],
        "turn_count": 0,
    }
    return await advance_comic_cabinet_session_llm(session, "", role_model_configs=role_model_configs)


def advance_comic_cabinet_session(session: dict, user_message: str = "") -> dict:
    """Advance the cabinet discussion and keep refining the story draft."""
    session = {
        "idea": (session or {}).get("idea", ""),
        "genre": (session or {}).get("genre", ""),
        "length": (session or {}).get("length", ""),
        "platform": (session or {}).get("platform", ""),
        "visual_style": (session or {}).get("visual_style", ""),
        "extra": (session or {}).get("extra", ""),
        "messages": list((session or {}).get("messages") or []),
        "user_notes": list((session or {}).get("user_notes") or []),
        "turn_count": int((session or {}).get("turn_count") or 0),
    }
    note = (user_message or "").strip()
    if note:
        session["messages"].append({"role": "user", "content": note})
        session["user_notes"].append(note)
        session["turn_count"] += 1

    aggregated_answers = "\n".join(session["user_notes"]).strip()
    extra_text = "\n".join(filter(None, [session["extra"], aggregated_answers])).strip()
    brief_payload = build_comic_brief(
        idea=session["idea"],
        genre=session["genre"],
        length=session["length"],
        platform=session["platform"],
        visual_style=session["visual_style"],
        extra=extra_text,
    )
    creative_brief = brief_payload["creative_brief"]
    script_payload = build_comic_script_preview(
        idea=session["idea"],
        genre=session["genre"],
        length=session["length"],
        platform=session["platform"],
        visual_style=session["visual_style"],
        extra=session["extra"],
        creative_brief=creative_brief,
        user_answers=aggregated_answers,
    )
    script_preview = script_payload["script_preview"]

    story_state = _cabinet_story_state(
        idea=session["idea"],
        extra=session["extra"],
        answers=aggregated_answers,
        creative_brief=creative_brief,
        script_preview=script_preview,
    )
    # 对于仅作内部逻辑计算而不调用 LLM 的 advance 流程，不再向 messages 注入任何假数据
    session["creative_brief"] = creative_brief
    session["script_preview"] = script_preview
    session["story_state"] = story_state
    session["cabinet_roles"] = []
    session["stage"] = story_state["stage"]
    session["ready_to_produce"] = story_state["ready_to_produce"]
    session["summary"] = _cabinet_summary_block(story_state, creative_brief)

    return {
        "status": "script_ready" if story_state["ready_to_produce"] else "needs_more_discussion",
        "stage": story_state["stage"],
        "ready_to_produce": story_state["ready_to_produce"],
        "assistant_message": "",
        "cabinet_roles": [],
        "creative_brief": creative_brief,
        "script_preview": script_preview,
        "session": session,
        "preview": "",
    }


async def advance_comic_cabinet_session_llm(
    session: dict,
    user_message: str = "",
    role_model_configs: dict[str, ModelConfig] | None = None,
) -> dict:
    """Advance the cabinet discussion with real per-role prompts when models are available."""
    result = advance_comic_cabinet_session(session, user_message)
    
    # 我们不再并发调用 5 个内阁顾问了，只保留“主创对话官”一个 Agent 来推进对话和剧本生成。
    # 为了兼容原有的状态结构，我们构造一个空的 cabinet_roles 数组。
    cabinet_roles = []
    result["cabinet_roles"] = cabinet_roles
    result["session"]["cabinet_roles"] = cabinet_roles
    result["session"]["llm_cabinet"] = True

    story_payload = await _cabinet_story_writer_llm(
        session=result["session"],
        creative_brief=result["creative_brief"],
        script_preview=result["script_preview"],
        cabinet_roles=cabinet_roles,
        role_model_configs=role_model_configs or {},
    )
    if story_payload:
        result = _apply_llm_story_payload(result, story_payload)
        # 显式覆盖 assistant_message 避免被旧逻辑冲掉
        if "assistant_message" in story_payload:
            result["assistant_message"] = story_payload["assistant_message"]
    else:
        # 当模型没有正常返回时，直接抛出异常，不再走兜底逻辑
        raise RuntimeError("AI 编剧模型未返回结果，请检查 API 配置或重试。")

    # 在这里手动把大模型的回复加进 messages，因为之前我们去掉了强制的 fallback append
    result["session"]["messages"].append({
        "role": "assistant",
        "content": result["assistant_message"],
        "cabinet_roles": [],
        "generated_by": "llm",
    })
    
    result["preview"] = _format_cabinet_turn(
        result["session"],
        result["assistant_message"],
        result["creative_brief"],
        result["script_preview"],
    )
    return result


async def _cabinet_story_writer_llm(
    session: dict,
    creative_brief: dict,
    script_preview: dict,
    cabinet_roles: list[dict],
    role_model_configs: dict[str, ModelConfig],
) -> dict:
    cfg = (role_model_configs or {}).get("编剧顾问") or (role_model_configs or {}).get("首辅/制片人")
    if not _model_config_usable(cfg):
        return {}
    llm = LLMFactory.create(cfg)
    try:
        response = await retry_async(
            lambda: llm.chat(
                [
                    LLMMessage(role="system", content=_story_writer_system_prompt()),
                    LLMMessage(role="user", content=_story_writer_user_prompt(session, creative_brief, script_preview, cabinet_roles)),
                ],
                response_format={"type": "json_object"},
            ),
            attempts=2,
            delay_seconds=0.2,
        )
    except Exception as e:
        print(f"DEBUG LLM Exception in _cabinet_story_writer_llm: {e}")
        raise RuntimeError(f"AI 编剧模型调用失败: {e}")
    
    parsed = _parse_story_writer_json(response.content)
    if not parsed:
        raise RuntimeError("AI 编剧模型返回的格式无法解析，请重试。")
        
    if parsed:
        parsed["model"] = response.model or f"{cfg.provider}/{cfg.model}"
    return parsed


def _apply_llm_story_payload(result: dict, payload: dict) -> dict:
    story = payload.get("story") or {}
    if not story.get("story_draft"):
        return result
    script = dict(result.get("script_preview") or {})
    for key in (
        "title",
        "genre",
        "logline",
        "why_it_happens",
        "how_it_happens",
        "protagonist_arc",
        "story_draft",
        "episode_outline",
        "key_turns",
    ):
        if story.get(key):
            script[key] = story[key]
    script.setdefault("production_gate", result.get("script_preview", {}).get("production_gate", "用户确认故事后再进入制片包生产。"))
    result["script_preview"] = script
    result["session"]["script_preview"] = script
    if isinstance(script.get("key_turns"), str):
        script["key_turns"] = _clean_key_turns(script.get("key_turns"))
    questions = [str(q).strip() for q in (story.get("questions") or payload.get("questions") or []) if str(q).strip()]
    result["session"].setdefault("story_state", {})["questions"] = questions[:2]
    if questions:
        result["session"]["story_state"]["missing"] = []
        result["session"]["story_state"]["stage"] = "drafting"
        result["session"]["stage"] = "drafting"
    result["assistant_message"] = payload.get("assistant_message") or "我先按你的想法写出一版故事稿，你可以直接说哪里不对，我继续改。"
    result["session"]["llm_story"] = True
    result["session"]["llm_story_model"] = payload.get("model", "")
    if result["session"].get("messages") and result["session"]["messages"][-1].get("role") == "assistant":
        result["session"]["messages"][-1]["content"] = result["assistant_message"]
        result["session"]["messages"][-1]["generated_story_by"] = "llm"
    result["preview"] = _format_cabinet_turn(result["session"], result["assistant_message"], result["creative_brief"], script)
    return result


def _format_cabinet_turn(session: dict, assistant_message: str, creative_brief: dict, script_preview: dict) -> str:
    history = session.get("messages", [])[-6:]
    lines = ["# 主创对话", ""]
    for item in history:
        if item.get("role") == "user":
            lines.append("## 你")
            lines.append(item.get("content", ""))
            lines.append("")
        else:
            lines.append("## 主创对话官")
            lines.append(item.get("content", ""))
            lines.append("")
    lines.extend([
        "## 当前故事提案",
        format_script_preview(script_preview),
    ])
    return "\n".join(lines)


def _cabinet_story_state(
    idea: str,
    extra: str,
    answers: str,
    creative_brief: dict,
    script_preview: dict,
) -> dict:
    combined = "\n".join(filter(None, [idea, extra, answers]))
    protagonist = _has_story_anchor(combined, "protagonist")
    conflict = _has_story_anchor(combined, "conflict")
    ending = _has_story_anchor(combined, "ending")
    style = bool((creative_brief.get("visual_style") or "").strip())
    missing = []
    if not protagonist:
        missing.append("主角身份和观众应该先代入谁")
    if not conflict:
        missing.append("核心对手或阻碍是什么")
    if not ending:
        missing.append("结尾要落在反转、爽点、治愈还是悬念")
    if not style:
        missing.append("视觉风格和平台节奏")
    completeness = (4 - len(missing)) / 4.0
    if len(missing) <= 1 and answers.strip():
        stage = "ready_to_confirm"
    elif answers.strip():
        stage = "drafting"
    else:
        stage = "discovering"
    questions = _cabinet_follow_up_questions(missing, script_preview, creative_brief)
    return {
        "missing": missing,
        "questions": questions,
        "completeness": round(completeness, 2),
        "stage": stage,
        "ready_to_produce": stage == "ready_to_confirm",
    }


def _cabinet_role_reviews(
    story_state: dict,
    creative_brief: dict,
    script_preview: dict,
    turn_count: int,
) -> list[dict]:
    ready = story_state["ready_to_produce"]
    questions = story_state.get("questions", [])
    first_question = questions[0] if questions else ""
    second_question = questions[1] if len(questions) > 1 else first_question
    third_question = questions[2] if len(questions) > 2 else first_question
    return [
        {
            "role": "首辅/制片人",
            "focus": "项目是否已经可以进入生产，观众会不会愿意看下去",
            "verdict": "可进入确认" if ready else "继续打磨",
            "comment": (
                f"这版的故事承诺已经比较明确：{creative_brief.get('story_promise', '')}。"
                if ready
                else f"现在最该先锁的是项目卖点和主冲突，当前主冲突是：{creative_brief.get('main_conflict', '')}。"
            ),
            "question": "" if ready else first_question,
        },
        {
            "role": "编剧顾问",
            "focus": "故事为什么发生、人物为什么行动、结尾为什么成立",
            "verdict": "因果成立" if ready else "因果待补",
            "comment": (
                f"我先认可这条因果线：{script_preview.get('why_it_happens', '')}，推进路径也基本顺。"
                if ready
                else f"现在的起因是“{script_preview.get('why_it_happens', '')}”，但还需要更明确的人物动机和代价。"
            ),
            "question": second_question,
        },
        {
            "role": "导演顾问",
            "focus": "第一集钩子够不够强，观众有没有继续看下去的动力",
            "verdict": "节奏可拍" if ready else "钩子待加强",
            "comment": (
                f"第一集钩子“{_first_hook(script_preview)}”已经有抓力，能支撑往下拆分镜。"
                if ready
                else f"目前第一集钩子是“{_first_hook(script_preview)}”，我建议再狠一点、更可视化一点。"
            ),
            "question": third_question,
        },
        {
            "role": "美术顾问",
            "focus": "画风、人物、场景是否能稳定延续到后面所有镜头",
            "verdict": "视觉方向稳定" if ready else "视觉锚点不足",
            "comment": (
                f"视觉方向目前可用：{creative_brief.get('visual_style', '')}，后面能顺着做人物和场景设定。"
                if ready
                else f"风格方向先抓到了：{creative_brief.get('visual_style', '')}，但还缺能一眼记住的视觉锚点。"
            ),
            "question": "如果只保留一个最想拍的镜头，你最想保留哪一幕？",
        },
        {
            "role": "连续性顾问",
            "focus": "人物设定、冲突规则、结尾钩子前后会不会打架",
            "verdict": "基本闭环" if ready else "设定仍需锁死",
            "comment": (
                f"人物变化线目前能闭环到结尾：{script_preview.get('protagonist_arc', '')}。"
                if ready
                else f"我担心后面跑偏的地方在于：{'; '.join(story_state.get('missing', [])[:2]) or '人物动机和结尾锚点'}。"
            ),
            "question": "你最不希望这部漫剧变成哪种样子？我可以提前帮你避开。",
        },
    ]


async def _cabinet_role_reviews_llm(
    story_state: dict,
    creative_brief: dict,
    script_preview: dict,
    turn_count: int,
    role_model_configs: dict[str, ModelConfig],
    fallback_roles: list[dict] | None = None,
) -> list[dict]:
    usable = {
        role: cfg
        for role, cfg in (role_model_configs or {}).items()
        if _model_config_usable(cfg)
    }
    if not usable:
        return []

    tasks = []
    for role, focus in CABINET_ROLES:
        cfg = usable.get(role)
        if not cfg:
            continue
        tasks.append(_run_one_cabinet_role_llm(role, focus, cfg, story_state, creative_brief, script_preview, turn_count))
    if not tasks:
        return []
    results = await _gather_cabinet_role_reviews(tasks)
    parsed = [item for item in results if item]
    if not parsed:
        return []
    parsed_by_role = {item.get("role", ""): item for item in parsed}
    fallback_by_role = {item.get("role", ""): item for item in (fallback_roles or [])}
    merged = []
    for role, focus in CABINET_ROLES:
        if role in parsed_by_role:
            merged.append(parsed_by_role[role])
            continue
        fallback = dict(fallback_by_role.get(role) or {})
        if not fallback:
            fallback = {
                "role": role,
                "focus": focus,
                "verdict": "规则补位",
                "comment": "这个角色的模型暂时没有返回可用结果，系统先用规则评审补位，避免卡住整轮讨论。",
                "question": "",
            }
        fallback["generated_by"] = "rule_fallback"
        fallback["fallback_reason"] = "role_model_unavailable_or_invalid"
        merged.append(fallback)
    return merged


async def _gather_cabinet_role_reviews(tasks) -> list[dict]:
    import asyncio
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [item for item in results if isinstance(item, dict)]


async def _run_one_cabinet_role_llm(
    role: str,
    focus: str,
    config: ModelConfig,
    story_state: dict,
    creative_brief: dict,
    script_preview: dict,
    turn_count: int,
) -> dict | None:
    system = _cabinet_role_system_prompt(role, focus)
    user = _cabinet_role_user_prompt(story_state, creative_brief, script_preview, turn_count)
    llm = LLMFactory.create(config)
    try:
        response = await retry_async(
            lambda: llm.chat(
                [
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user", content=user),
                ],
                response_format={"type": "json_object"},
            ),
            attempts=2,
            delay_seconds=0.2,
        )
    except Exception as e:
        print(f"DEBUG LLM Exception in _run_one_cabinet_role_llm for {role}: {e}")
        return None
    parsed = _parse_cabinet_role_json(response.content)
    if not parsed:
        return None
    return {
        "role": role,
        "focus": focus,
        "verdict": parsed.get("verdict", ""),
        "comment": parsed.get("comment", ""),
        "question": parsed.get("question", ""),
        "model": response.model or f"{config.provider}/{config.model}",
        "generated_by": "llm",
    }


def _cabinet_role_system_prompt(role: str, focus: str) -> str:
    return "\n".join([
        f"你现在是 AI 漫剧办公室里的“{role}”。",
        f"你的职责：{focus}",
        "你不是通用助手，你只从自己的专业视角发言。",
        "请基于当前故事材料给出简短、明确、能推进决策的判断。",
        "输出必须是 JSON 对象，字段固定为：verdict, comment, question。",
        "要求：",
        "1. verdict 要短，像“继续打磨”“可进入确认”“钩子待加强”这种。",
        "2. comment 要具体，不要重复用户原话，不要空泛鼓励。",
        "3. question 只问一个你最在意的问题；如果已基本成型，也可以让问题变成确认式追问。",
        "4. 不要输出 Markdown，不要解释 JSON 以外的内容。",
    ])


def _story_writer_system_prompt() -> str:
    return "\n".join([
        "你现在是 AI 漫剧办公室的“主创对话官”。你的任务是像一位懂故事的编剧助手一样，和用户自然对话，把模糊的灵感变成可生产的剧本。",
        "你的输出必须是一个 JSON 对象，包含 assistant_message 和 story 两个字段。",
        "assistant_message：这是你说给用户听的话。必须自然、口语化。在理解用户灵感后，你每轮最多只问 1 个最关键的问题（最多 2 个）。不要像填表一样连问一堆，不要生硬地罗列问题。",
        "story：这是你后台生成的故事提案，包含 title, genre, logline, why_it_happens, how_it_happens, protagonist_arc, story_draft, episode_outline, key_turns, questions。",
        "story_draft 要用中文自然段写完整故事，至少包含开端、发展、高潮、结尾。",
        "如果用户灵感不足，优先在 assistant_message 里追问；如果已经成型，生成一版完整故事稿让用户确认。",
    ])


def _story_writer_user_prompt(session: dict, creative_brief: dict, script_preview: dict, cabinet_roles: list[dict]) -> str:
    memory_context = build_memory_context_prompt(build_core_memory_vault({
        **session,
        "creative_brief": creative_brief,
        "script_preview": script_preview,
    }))
    return "\n".join([
        memory_context,
        "",
        "请基于下面材料，写出你给用户的回复 (assistant_message) 和当前的故事提案 (story)。",
        "",
        f"用户初始灵感：{session.get('idea', '')}",
        f"题材：{session.get('genre', '') or creative_brief.get('genre', '')}",
        f"风格：{session.get('visual_style', '') or creative_brief.get('visual_style', '')}",
        f"补充要求：{session.get('extra', '')}",
        f"用户后续对话：{' / '.join(session.get('user_notes') or [])}",
        "",
        "当前的剧本草案（仅供参考，请根据你们的聊天进度更新）：",
        format_script_preview(script_preview),
    ])


def _cabinet_role_user_prompt(
    story_state: dict,
    creative_brief: dict,
    script_preview: dict,
    turn_count: int,
) -> str:
    return "\n".join([
        "请评审下面这部 AI 漫剧的当前讨论结果。",
        f"当前阶段：{story_state.get('stage', '')}",
        f"讨论轮数：{turn_count}",
        f"完整度：{story_state.get('completeness', 0)}",
        f"待补问题：{'；'.join(story_state.get('missing', [])) or '无'}",
        "",
        "[锁定稿]",
        format_creative_brief(creative_brief),
        "",
        "[当前剧本草案]",
        format_script_preview(script_preview),
    ])


def _parse_cabinet_role_json(content: str) -> dict:
    raw = (content or "").strip()
    if not raw or raw.startswith("[API错误]"):
        return {}
    data = parse_json_object(raw)
    if not isinstance(data, dict):
        return {}
    return {
        "verdict": str(data.get("verdict", "")).strip(),
        "comment": str(data.get("comment", "")).strip(),
        "question": str(data.get("question", "")).strip(),
    }


def _parse_story_writer_json(content: str) -> dict:
    raw = (content or "").strip()
    if not raw or raw.startswith("[API错误]"):
        return {}
    data = parse_json_object(raw)
    if not isinstance(data, dict):
        return {}
    story = data.get("story") or {}
    if not isinstance(story, dict):
        return {}
    episodes = story.get("episode_outline") or []
    if not isinstance(episodes, list):
        episodes = []
    normalized_episodes = []
    for index, ep in enumerate(episodes, start=1):
        if not isinstance(ep, dict):
            continue
        normalized_episodes.append({
            "episode": int(ep.get("episode") or index),
            "title": str(ep.get("title", "")).strip() or f"第{index}集",
            "cause": str(ep.get("cause", "")).strip(),
            "action": str(ep.get("action", "")).strip(),
            "turn": str(ep.get("turn", "")).strip(),
            "hook": str(ep.get("hook", "")).strip(),
        })
    normalized_story = {
        "title": str(story.get("title", "")).strip(),
        "genre": str(story.get("genre", "")).strip(),
        "logline": str(story.get("logline", "")).strip(),
        "why_it_happens": str(story.get("why_it_happens", "")).strip(),
        "how_it_happens": str(story.get("how_it_happens", "")).strip(),
        "protagonist_arc": str(story.get("protagonist_arc", "")).strip(),
        "story_draft": str(story.get("story_draft", "")).strip(),
        "episode_outline": normalized_episodes,
        "key_turns": _clean_key_turns(story.get("key_turns") or []),
        "questions": [str(item).strip() for item in (story.get("questions") or []) if str(item).strip()],
    }
    if not normalized_story["story_draft"]:
        return {}
    return {
        "assistant_message": str(data.get("assistant_message", "")).strip(),
        "story": normalized_story,
    }


def _model_config_usable(config: ModelConfig | None) -> bool:
    if not config:
        return False
    provider = (config.provider or "").lower()
    model = (config.model or "").lower()
    if "seedream" in model or "image" in model:
        return False
    if provider == "ollama":
        return True
    return bool(config.api_key)


def _cabinet_chair_summary(
    story_state: dict,
    creative_brief: dict,
    script_preview: dict,
    cabinet_roles: list[dict],
) -> str:
    if story_state["ready_to_produce"]:
        return "我觉得这个故事已经基本成型了。你可以看看右侧的故事提案，如果没有问题，可以直接点击“确认故事，进入生产”，或者告诉我哪里还需要修改。"
    
    questions = story_state.get("questions") or ["你觉得我们接下来应该怎么发展？"]
    return questions[0]


def _cabinet_summary_block(story_state: dict, creative_brief: dict) -> str:
    return "\n".join([
        f"阶段：{story_state.get('stage', '')}",
        f"完整度：{story_state.get('completeness', 0)}",
        f"故事承诺：{creative_brief.get('story_promise', '')}",
        f"主冲突：{creative_brief.get('main_conflict', '')}",
    ])


def _cabinet_follow_up_questions(missing: list[str], script_preview: dict, creative_brief: dict) -> list[str]:
    questions = []
    for item in missing:
        if "主角" in item:
            questions.append("这个故事里，你最想让观众心疼或代入谁？")
        elif "对手" in item or "阻碍" in item:
            questions.append("主角在做这件事的时候，最大的阻碍是什么？是什么在阻止他？")
        elif "结尾" in item:
            questions.append("故事最后，你想给观众一种什么样的感觉？是反转、爽感、还是治愈？")
        elif "视觉风格" in item:
            questions.append("你希望这个漫剧的画面风格偏向哪种？比如偏日漫、国风还是美漫？")
    if not questions:
        questions.append("你觉得这个故事哪里还需要再调整一下吗？")
    return questions


def _has_story_anchor(text: str, anchor: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    if anchor == "protagonist":
        keywords = ("主角", "女主", "男主", "主人公", "她是", "他是", "我是")
    elif anchor == "conflict":
        keywords = ("反派", "对手", "阻止", "陷害", "追杀", "危机", "秘密", "误会", "冲突", "倒计时")
    else:
        keywords = ("结尾", "最后", "最终", "收尾", "反转", "钩子", "悬念", "爽点", "治愈")
    return any(keyword in text for keyword in keywords)


def _first_hook(script_preview: dict) -> str:
    outline = script_preview.get("episode_outline") or []
    if not outline:
        return "待补充"
    return outline[0].get("hook") or "待补充"


def _line_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}\s*[:：]\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _section_after(text: str, key: str, stop_markers: tuple[str, ...] = ()) -> str:
    match = re.search(rf"^{re.escape(key)}\s*[:：]\s*(.+)$", text, re.MULTILINE | re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    value = match.group(1).strip()
    for marker in stop_markers:
        if marker in value:
            value = value.split(marker, 1)[0].strip()
    return value


def _markdown_section(text: str, heading: str, stop_headings: tuple[str, ...] = ()) -> str:
    match = re.search(rf"^##\s*{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        return ""
    value = text[match.end():].strip()
    for marker in stop_headings:
        split_marker = f"## {marker}"
        if split_marker in value:
            value = value.split(split_marker, 1)[0].strip()
    return value


def _parse_creative_brief(text: str) -> dict:
    if "Creative brief:" not in text:
        return {}
    section = text.split("Creative brief:", 1)[1].split("Script preview:", 1)[0].split("User answers:", 1)[0]
    labels = {
        "核心灵感": "core_idea",
        "故事承诺": "story_promise",
        "题材": "genre",
        "情绪": "tone",
        "主冲突": "main_conflict",
        "必须保留": "must_keep",
    }
    parsed = {}
    for label, key in labels.items():
        match = re.search(rf"[-*]\s*{label}\s*[:：]\s*(.+)", section)
        if match:
            parsed[key] = match.group(1).strip()
    questions = re.findall(r"\d+[.、]\s*(.+)", section)
    if questions:
        parsed["clarifying_questions"] = [q.strip() for q in questions]
    return parsed


def _parse_script_preview(text: str) -> dict:
    if "Script preview:" not in text:
        return {}
    section = text.split("Script preview:", 1)[1].split("Confirmed script:", 1)[0].split("Script notes:", 1)[0]
    title_match = re.search(r"#\s*(.+?)\s*内阁剧本预审", section)
    labels = {
        "一句话故事": "logline",
        "为什么发生": "why_it_happens",
        "如何发生": "how_it_happens",
        "主角变化": "protagonist_arc",
        "生产闸门": "production_gate",
    }
    parsed = {"title": title_match.group(1).strip() if title_match else ""}
    for label, key in labels.items():
        match = re.search(rf"[-*]?\s*{label}\s*[:：]\s*(.+)", section)
        if match:
            parsed[key] = match.group(1).strip()
    story_draft = _markdown_section(section, "完整故事稿", ("每集大纲", "关键转折", "内阁意见", "生产闸门"))
    if story_draft:
        parsed["story_draft"] = story_draft
    episodes = []
    for match in re.finditer(r"^(\d+)[.、]\s*(.+?)｜起因：(.+?)｜行动：(.+?)｜转折：(.+?)｜钩子：(.+)$", section, re.MULTILINE):
        episodes.append({
            "episode": int(match.group(1)),
            "title": match.group(2).strip(),
            "cause": match.group(3).strip(),
            "action": match.group(4).strip(),
            "turn": match.group(5).strip(),
            "hook": match.group(6).strip(),
        })
    if episodes:
        parsed["episode_outline"] = episodes
    
    # 解析动态的关键转折列表，而不是死板的模板
    turns = re.findall(r"^- (.+)$", section.split("## 关键转折", 1)[1].split("## 内阁意见", 1)[0], re.MULTILINE) if "## 关键转折" in section else []
    if turns:
        parsed["key_turns"] = [item.strip() for item in turns]
        
    return parsed if parsed.get("why_it_happens") or episodes else {}


def _parse_confirmed_script(text: str) -> dict:
    if "Confirmed script:" not in text:
        return {}
    section = text.split("Confirmed script:", 1)[1].split("Script notes:", 1)[0]
    title_match = re.search(r"#\s*(.+?)\s*确认版剧本", section)
    labels = {
        "状态": "status",
        "剧本版本": "script_version",
        "剧本哈希": "script_hash",
        "故事承诺": "story_promise",
        "主冲突": "main_conflict",
        "一句话故事": "logline",
        "为什么发生": "why_it_happens",
        "如何发生": "how_it_happens",
        "主角变化": "protagonist_arc",
        "平台": "platform",
        "视觉风格": "visual_style",
        "生产闸门": "production_gate",
    }
    parsed = {"title": title_match.group(1).strip() if title_match else ""}
    for label, key in labels.items():
        match = re.search(rf"[-*]?\s*{label}\s*[:：]\s*(.+)", section)
        if match:
            value = match.group(1).strip()
            parsed[key] = int(value) if key == "script_version" and value.isdigit() else value
    story_draft = _markdown_section(section, "完整故事稿", ("每集确认大纲", "每集大纲", "关键转折", "内阁共识", "用户最终要求", "生产闸门"))
    if story_draft:
        parsed["story_draft"] = story_draft
    episodes = []
    for match in re.finditer(r"^(\d+)[.、]\s*(.+?)｜起因：(.+?)｜行动：(.+?)｜转折：(.+?)｜钩子：(.+)$", section, re.MULTILINE):
        episodes.append({
            "episode": int(match.group(1)),
            "title": match.group(2).strip(),
            "cause": match.group(3).strip(),
            "action": match.group(4).strip(),
            "turn": match.group(5).strip(),
            "hook": match.group(6).strip(),
        })
    if episodes:
        parsed["episode_outline"] = episodes
    turns = re.findall(r"^- (.+)$", section.split("## 关键转折", 1)[1].split("## 内阁共识", 1)[0], re.MULTILINE) if "## 关键转折" in section and "## 内阁共识" in section else []
    if turns:
        parsed["key_turns"] = [item.strip() for item in turns]
    return parsed if parsed.get("why_it_happens") or episodes else {}


def _first_sentence(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return re.split(r"[。.!?？\n]", clean)[0].strip()


def _clean_title(text: str) -> str:
    text = re.sub(r"^(我要|我想|请帮我|帮我|做一个|制作一个)\s*", "", text.strip(), flags=re.IGNORECASE)
    text = text.strip(" ：:，,。.")
    return text[:60] or "未命名漫剧"


def _infer_genre(text: str) -> str:
    lowered = text.lower()
    if _is_crisis_family_story(text):
        return "现实情绪危机"
    if _is_domestic_life_story(text):
        return "家庭生活剧"
    if any(word in text for word in ("悬疑", "推理", "凶案", "侦探")):
        return "悬疑推理"
    if any(word in text for word in ("爽文", "逆袭", "复仇", "重生")):
        return "逆袭复仇爽剧"
    if any(word in text for word in ("古风", "仙侠", "宫廷", "玄幻")):
        return "古风幻想"
    if any(word in text for word in ("科幻", "机器人", "未来")) or "sci" in lowered:
        return "科幻漫剧"
    if any(word in text for word in ("恋爱", "甜宠", "虐恋")):
        return "情感恋爱"
    return "剧情向竖屏漫剧"


def _is_crisis_family_story(text: str) -> bool:
    text = text or ""
    crisis_words = ("跳楼", "天台", "轻生", "自杀", "崩溃", "撑不下去")
    family_words = ("母亲", "妈妈", "父亲", "爸爸", "家长", "孩子", "学生")
    return any(word in text for word in crisis_words) and any(word in text for word in family_words)


def _is_domestic_life_story(text: str) -> bool:
    text = text or ""
    domestic_words = ("家庭", "家人", "母亲", "父亲", "妈妈", "爸爸", "女儿", "儿子", "聚餐", "餐桌", "团圆")
    warm_words = ("幸福", "美满", "温情", "生活流", "和解", "委屈", "亲情")
    return any(word in text for word in domestic_words) and any(word in text for word in warm_words)


def _genre_has(genre: str, *terms: str) -> bool:
    lowered = (genre or "").lower()
    return any(term in genre or term.lower() in lowered for term in terms)


def _story_promise(idea: str, genre: str) -> str:
    if _is_crisis_family_story(idea + "\n" + genre):
        return "用一次极端危机逼出亲子之间长期被忽视的痛点，重点不是猎奇，而是倾听、救援和修复。"
    if _is_domestic_life_story(idea + "\n" + genre):
        return "用一场看似普通的家庭聚餐，让亲人之间没说出口的委屈、理解和和解慢慢浮出来。"
    if _genre_has(genre, "悬疑", "suspense", "detective", "mystery"):
        return "用一个视觉谜题牵引观众，让真相逐层反转。"
    if _genre_has(genre, "复仇", "爽", "revenge"):
        return "让主角从被压迫走向主动反击，每集都有可见爽点。"
    if _genre_has(genre, "科幻", "science", "sci-fi", "future"):
        return "用强设定制造时间压力，让人物选择推动情节。"
    if _genre_has(genre, "幻想", "古风", "fantasy", "costume"):
        return "用世界规则和身份秘密制造连续追看欲。"
    return f"围绕“{idea[:28]}”建立清晰人物目标、冲突和反转。"


def _infer_tone(text: str, genre: str) -> str:
    if _is_crisis_family_story(text + "\n" + genre):
        return "克制、痛感、现实向，避免猎奇，用希望收束"
    if _is_domestic_life_story(text + "\n" + genre):
        return "温情、克制、生活流，靠细节和沉默推动情绪"
    if any(word in text for word in ("搞笑", "轻喜", "喜剧")):
        return "轻喜剧，节奏快，反差强"
    if any(word in text for word in ("虐", "遗憾", "悲")):
        return "情绪浓烈，带痛感和人物拉扯"
    if _genre_has(genre, "悬疑", "suspense", "detective", "mystery"):
        return "紧张、克制、逐步揭露"
    if _genre_has(genre, "复仇", "爽", "revenge"):
        return "压抑开局，反击释放"
    return "戏剧化但不夸张，重视可视化动作"


def _main_conflict(idea: str, genre: str) -> str:
    if _is_crisis_family_story(idea + "\n" + genre):
        return "学生被长期压力和误解推到崩溃边缘，母亲必须从责备转向真正倾听，和救援者一起把孩子拉回现实。"
    if _is_domestic_life_story(idea + "\n" + genre):
        return "一家人表面维持幸福体面，真正的阻碍是每个人都怕破坏气氛，所以把委屈藏在餐桌礼貌里。"
    if _genre_has(genre, "复仇", "revenge"):
        return "主角被误解或压迫，必须找到证据并完成反击。"
    if _genre_has(genre, "悬疑", "suspense", "detective", "mystery"):
        return "主角发现异常线索，但真相和自身身份都不稳定。"
    if _genre_has(genre, "科幻", "science", "sci-fi", "future"):
        return "主角面对倒计时和陌生规则，必须用有限信息完成拯救。"
    return f"主角想完成一个目标，但“{idea[:20]}”带来的规则或对手不断阻碍。"


def _clarifying_questions(genre: str, length: str, platform: str, visual_style: str) -> list[str]:
    return [
        "主角是谁？你希望观众先同情 TA、佩服 TA，还是怀疑 TA？",
        "故事最后更想要反转、爽感、治愈，还是开放式悬念？",
        f"剧集长度是否锁定为“{length or '未定'}”？如果不是，请说明集数和每集时长。",
        f"目标平台是否锁定为“{platform or '未定'}”？这会影响节奏和画幅。",
        f"画风是否锁定为“{visual_style or DEFAULT_STYLE}”？有没有绝对不能出现的风格？",
        "有没有必须出现的人物、道具、场景，或者必须避开的内容？",
    ]


def _episode_count(length: str, default: int = 3) -> int:
    match = re.search(r"(\d+)\s*(?:episodes|集)", length or "", re.IGNORECASE)
    return max(1, min(30, int(match.group(1)))) if match else default


def _why_it_happens(title: str, genre: str, user_answers: str, brief: dict) -> str:
    if _is_crisis_family_story(title + "\n" + genre + "\n" + user_answers):
        pressure = user_answers or "学生长期被成绩、误解和孤独压垮，母亲直到危机发生才意识到自己从未真正听见孩子。"
        return f"{pressure} 危机发生在天台边缘，逼迫所有人停止说教，先把孩子的生命和情绪接住。"
    if _is_domestic_life_story(title + "\n" + genre + "\n" + user_answers):
        return "一次家庭聚餐把分散很久的家人重新放到同一张桌子上，表面的热闹让每个人更清楚地看见自己没有说出口的委屈。"
    if user_answers:
        return f"故事起因遵守用户补充：{user_answers}。外部事件把主角推入选择，迫使TA面对“{title}”的核心问题。"
    if _genre_has(genre, "悬疑", "suspense", "detective", "mystery"):
        return f"主角偶然接触到一个无法解释的证据，这个证据与“{title}”相关，也威胁到主角自身身份。"
    if _genre_has(genre, "科幻", "science", "sci-fi", "future"):
        return f"一次技术或时空异常打破日常秩序，主角必须在倒计时内理解规则并救回重要之人。"
    if _genre_has(genre, "复仇", "revenge"):
        return "主角被公开羞辱或背叛，旧伤被重新揭开，因此必须主动夺回解释权。"
    return f"主角原本想维持普通生活，但“{title}”让TA无法继续逃避。"


def _how_it_happens(title: str, genre: str, user_answers: str, brief: dict) -> str:
    if _is_crisis_family_story(title + "\n" + genre + "\n" + user_answers):
        return "通过母亲赶到天台、试图劝阻、说错话后崩溃、第一次放下控制欲倾听、救援人员介入和孩子重新回应来推进。"
    if _is_domestic_life_story(title + "\n" + genre + "\n" + user_answers):
        return "通过餐桌上的座位、夹菜、沉默、旧照片、没接住的话和饭后的收拾动作推进，让冲突从礼貌表面慢慢露出来。"
    if _genre_has(genre, "悬疑", "suspense", "detective", "mystery"):
        return "通过线索、误导、证物和人物关系反复翻转来推进，每一集都用一个可见物件揭开新信息。"
    if _genre_has(genre, "科幻", "science", "sci-fi", "future"):
        return "通过规则发现、失败代价、倒计时压迫和关键道具使用来推进。"
    if _genre_has(genre, "复仇", "revenge"):
        return "通过压迫开局、证据积累、公开反击和身份反转来推进。"
    return "通过目标、阻碍、选择、后果四步推进，尽量用画面动作代替旁白解释。"


def _protagonist_arc(genre: str, user_answers: str) -> str:
    if _is_crisis_family_story(genre + "\n" + user_answers):
        return "学生从彻底失望到被听见，母亲从责备和控制转向承认错误、陪伴和求助。"
    if _is_domestic_life_story(genre + "\n" + user_answers):
        return "从假装一切都好，到承认彼此都有委屈，再到愿意用更诚实的方式重新坐到一起。"
    base = "从被动卷入，到主动选择，再到用自己的行动改变结局。"
    if user_answers:
        return f"{base} 人物设定优先遵守：{user_answers[:80]}"
    return base


def _story_draft(
    *,
    title: str,
    genre: str,
    why: str,
    how: str,
    outline: list[dict],
    protagonist_arc: str,
    user_answers: str,
    brief: dict,
) -> str:
    # 完全移除硬编码的完整故事稿，让大模型根据对话动态生成
    return ""





def _ensure_sentence(text: str) -> str:
    clean = (text or "").strip()
    if not clean:
        return ""
    return clean if clean.endswith(("。", "！", "？")) else f"{clean}。"


def _story_clean_reason(why: str, title: str) -> str:
    clean = (why or "").strip()
    clean = re.sub(r"^故事起因遵守用户补充[:：]\s*", "", clean)
    if "危机发生在天台边缘" in clean:
        clean = "长期积累的成绩压力、误解和孤独在这一天集中爆发，危机发生在天台边缘，所有人都必须先停止说教，把孩子的生命和情绪接住"
    if "外部事件把主角推入选择" in clean:
        clean = f"一场异常事件把主角推入选择，迫使主角面对“{title}”背后的核心问题"
    clean = clean.replace("。。", "。").strip("。")
    clean = clean.replace("TA", "主角")
    if clean:
        return clean
    return f"一件和“{title}”有关的异常事件突然发生"


def _story_clean_method(how: str) -> str:
    clean = (how or "").strip()
    if not clean:
        return "故事通过目标、阻碍、选择和后果一步步推进。"
    return clean if clean.endswith(("。", "！", "？")) else f"{clean}。"


def _story_clean_arc(arc: str) -> str:
    clean = (arc or "").strip().replace(" 人物设定优先遵守：", " ")
    if "主角是" in clean and "从被动卷入" in clean:
        clean = "从被动卷入，到主动选择，再到用自己的行动改变结局。"
    clean = clean.replace("TA", "主角")
    return clean if clean.endswith(("。", "！", "？")) else f"{clean}。"


def _story_protagonist(user_answers: str, genre: str) -> str:
    if _is_crisis_family_story(genre + "\n" + user_answers):
        return "学生"
    if "女侦探" in user_answers:
        return "女侦探"
    if "女大学生" in user_answers:
        return "女大学生"
    if "女孩" in user_answers:
        return "女孩"
    if "外卖员" in user_answers:
        return "外卖员"
    if _genre_has(genre, "悬疑", "suspense", "detective", "mystery"):
        return "侦探型主角"
    return "主角"


def _story_antagonist(user_answers: str, genre: str) -> str:
    if _is_crisis_family_story(genre + "\n" + user_answers):
        return "长期压力和误解"
    if "反派" in user_answers:
        return "反派"
    if "对手" in user_answers:
        return "对手"
    if "操控" in user_answers:
        return "操控者"
    if _genre_has(genre, "悬疑", "suspense", "detective", "mystery"):
        return "隐藏的操控者"
    return "阻碍者"


def _story_key_object(title: str, genre: str) -> str:
    if _is_crisis_family_story(title + "\n" + genre):
        return "天台上的风和母亲颤抖的声音"
    if "信" in title:
        return "那封信"
    if "漫画" in title:
        return "漫画世界的入口"
    if "未来" in title:
        return "未来城市的倒计时信号"
    if _genre_has(genre, "悬疑", "suspense", "detective", "mystery"):
        return "关键证物"
    return "关键道具"


def _episode_outline(title: str, genre: str, count: int, why: str, how: str, user_answers: str) -> list[dict]:
    # 完全移除硬编码的模板，依赖 LLM 动态生成
    return []


def _key_turns(outline: list[dict]) -> list[str]:
    return [f"第{ep['episode']}集：{ep['turn']}" for ep in outline[:5]]


def _cabinet_review(title: str, genre: str, outline: list[dict], visual_style: str) -> list[dict]:
    reviews = []
    for role, responsibility in CABINET_ROLES:
        if role.startswith("首辅"):
            verdict = "可以进入剧本确认，但必须由用户认可起因和结尾钩子。"
            reason = "故事方向已经有核心冲突，风险在于用户是否接受这个起因。"
        elif role.startswith("编剧"):
            verdict = "通过预审。"
            reason = "已经写明为什么发生、如何发生和每集转折。"
        elif role.startswith("导演"):
            verdict = "可拍。"
            reason = "每集都有可转化为画面的行动、证据或对峙。"
        elif role.startswith("美术"):
            verdict = "可进入视觉设定。"
            reason = f"画风锁定为“{visual_style}”，后续需固定角色和场景参考。"
        else:
            verdict = "需要后续持续检查。"
            reason = "人物动机、关键道具和场景状态需要在制片画布中绑定编号。"
        reviews.append({"role": role, "responsibility": responsibility, "verdict": verdict, "reason": reason})
    return reviews


def _script_beats_from_preview(script: dict) -> list[dict]:
    beats = []
    for ep in script.get("episode_outline", []) or []:
        beats.append({
            "id": f"beat_{int(ep.get('episode', len(beats) + 1)):02d}",
            "name": ep.get("title", "剧情节拍"),
            "content": f"起因：{ep.get('cause', '')}；行动：{ep.get('action', '')}；转折：{ep.get('turn', '')}；钩子：{ep.get('hook', '')}",
        })
    if not beats:
        beats = [
            {"id": "beat_01", "name": "异常发生", "content": script.get("why_it_happens", "")},
            {"id": "beat_02", "name": "行动推进", "content": script.get("how_it_happens", "")},
            {"id": "beat_03", "name": "结尾钩子", "content": "用视觉问题收尾。"},
        ]
    while len(beats) < 6:
        beats.append({
            "id": f"beat_{len(beats) + 1:02d}",
            "name": "补充分镜节拍",
            "content": "补足视觉动作、人物反应和结尾钩子。",
        })
    return beats[:6]


def _episodes_from_preview(script: dict) -> list[dict]:
    return [
        {
            "episode": ep.get("episode"),
            "purpose": f"{ep.get('title')}：{ep.get('action')}",
            "ending_hook": ep.get("hook", "用视觉问题收尾。"),
        }
        for ep in script.get("episode_outline", []) or []
    ]


def _enrich_production_assets(
    title: str,
    visual_style: str,
    characters: list[dict],
    props: list[dict],
    scenes: list[dict],
) -> None:
    """Attach production-grade asset specs before storyboard/image generation."""
    style = _premium_visual_style(visual_style)
    for item in characters or []:
        name = item.get("name", "")
        role = item.get("role", "")
        lock = item.get("visual_lock", "")
        item["image_prompt"] = (
            f"{title}，{style}，商业级人物设定图，{name}，{role}，半身肖像和全身站姿结合，"
            f"面部结构精致，眼神有戏，服装材质和主色清楚，适合后续角色一致性参考，"
            f"柔和电影布光，干净背景，不要文字，不要标签，不要编号。连续性要求：{lock}"
        )
        item.setdefault("asset_specs", [
            {
                "kind": "character_three_view",
                "label": "人物三视图",
                "image_ref": f"{item.get('id', 'character')}_three_view.png",
                "prompt": (
                    f"{title}，{style}，商业级角色设定三视图，{name}，{role}，正面、侧面、背面，"
                    f"统一脸型骨相、统一发型轮廓、统一服装主色和材质，完整站姿，角色可用于后续视频生成参考，"
                    f"细腻面部结构，清晰服装褶皱，专业设定稿排版，柔和电影布光，"
                    f"不要文字，不要编号，不要水印。连续性要求：{lock}"
                ),
                "acceptance": "正面、侧面、背面必须像同一个角色；服装、发型、年龄感稳定。",
            },
            {
                "kind": "character_expression_sheet",
                "label": "人物表情表",
                "image_ref": f"{item.get('id', 'character')}_expressions.png",
                "prompt": (
                    f"{title}，{style}，商业级角色表情表，{name}，{role}，中性、震惊、愤怒、悲伤、克制、决绝，"
                    f"六个半身表情，同一脸型和发型，同一服装，同一年龄感，眼神和嘴角情绪清晰，"
                    f"干净背景，适合做角色一致性参考，不要文字，不要编号，不要水印。"
                ),
                "acceptance": "六个表情可区分，但脸型、发型、服装不能漂移。",
            },
        ])
    for item in props or []:
        name = item.get("name", "")
        rule = item.get("continuity_rule", "")
        item["image_prompt"] = (
            f"{title}，{style}，商业级关键道具设定图，{name}，单独展示，材质纹理清晰，"
            f"颜色、磨损、尺寸和形状稳定，边缘干净，适合后续分镜重复引用，"
            f"工作室柔光，干净背景，不要文字，不要标签，不要编号。连续性要求：{rule}"
        )
        item.setdefault("asset_specs", [
            {
                "kind": "prop_turnaround",
                "label": "道具多角度设定",
                "image_ref": f"{item.get('id', 'prop')}_turnaround.png",
                "prompt": (
                    f"{title}，{style}，商业级关键道具设定图，{name}，正面、侧面、细节特写，"
                    f"材质纹理清晰，颜色和磨损稳定，比例真实，边缘干净，能被后续分镜反复识别，"
                    f"柔和工作室布光，干净背景，不要文字，不要编号，不要水印。连续性要求：{rule}"
                ),
                "acceptance": "道具形状、颜色、材质稳定，后续镜头能一眼认出。",
            },
            {
                "kind": "prop_usage_sheet",
                "label": "道具使用状态",
                "image_ref": f"{item.get('id', 'prop')}_usage.png",
                "prompt": (
                    f"{title}，{style}，{name}在剧情中的使用状态参考，静置、被握住、特写、关键变化前后对比，"
                    f"保持同一物件的材质、体积、颜色和破损状态，镜头有电影质感，细节清晰，不要文字，不要编号，不要水印。"
                ),
                "acceptance": "使用前后仍然是同一个道具，关键变化服务剧情。",
            },
        ])
    for item in scenes or []:
        name = item.get("name", "")
        rule = item.get("continuity_rule", "")
        item["image_prompt"] = (
            f"{title}，{style}，商业级场景概念图，{name}，竖屏漫剧背景，无人物，"
            f"空间透视清楚，光线方向明确，环境细节真实可信，远中近景层次分明，"
            f"电影氛围和色彩统一，适合后续分镜复用，不要文字，不要标签，不要编号。连续性要求：{rule}"
        )
        item.setdefault("asset_specs", [
            {
                "kind": "scene_layout",
                "label": "场景空间设定",
                "image_ref": f"{item.get('id', 'scene')}_layout.png",
                "prompt": (
                    f"{title}，{style}，商业级场景空间设定图，{name}，建立镜头，主要入口、人物站位区、关键道具位置，"
                    f"空间层次清楚，远中近景分明，光线方向明确，色调稳定，环境细节真实可信，电影级氛围，"
                    f"不要文字，不要编号，不要水印。连续性要求：{rule}"
                ),
                "acceptance": "空间结构、光线方向和关键道具位置清楚，能支撑后续分镜。",
            },
            {
                "kind": "scene_camera_angles",
                "label": "场景常用机位",
                "image_ref": f"{item.get('id', 'scene')}_camera_angles.png",
                "prompt": (
                    f"{title}，{style}，{name}常用镜头角度，远景、中景、低角度、特写背景，"
                    f"同一空间连续，光线与陈设一致，镜头语言清楚，适合导演分镜参考，电影构图，不要文字，不要编号，不要水印。"
                ),
                "acceptance": "多个机位看起来属于同一个空间，不应像不同地点。",
            },
        ])


def _premium_visual_style(visual_style: str) -> str:
    style = (visual_style or DEFAULT_STYLE).strip()
    return (
        f"{style}，高质量AI漫剧视觉，电影级构图，细腻线稿与精致上色，"
        "人物五官稳定，服装材质清晰，真实光影层次，背景有空间深度，"
        "画面干净，高分辨率，非廉价插画感，非塑料质感，非低清截图"
    )


def _characters_for(title: str, genre: str, brief: dict, user_answers: str, script: dict) -> list[dict]:
    protagonist_role = "主动追查真相的人" if _genre_has(genre, "悬疑", "suspense", "detective", "mystery") else "被低估但会反击的主角"
    if user_answers:
        protagonist_role = f"{protagonist_role}；遵守用户补充：{user_answers[:40]}"
    antagonist_role = "隐藏在暗处的操控者" if _genre_has(genre, "悬疑", "suspense", "detective", "mystery") else "制造压力的对手"
    return [
        {
            "id": "char_01",
            "name": "主角",
            "role": protagonist_role,
            "visual_lock": "所有镜头保持同一脸型、同一发型、同一主服装配色。",
            "personality": script.get("protagonist_arc", "冷静、有行动力，情绪变化通过动作和眼神体现。"),
            "image_prompt": f"{title} 主角设定图，{protagonist_role}，清晰正脸参考，全身站姿，中性表情，角色三视图，制作设定稿",
        },
        {
            "id": "char_02",
            "name": "对手",
            "role": antagonist_role,
            "visual_lock": "轮廓锐利，固定标志性配饰，表情语言保持克制压迫感。",
            "personality": "话不多但能制造压迫，推动主冲突升级。",
            "image_prompt": f"{title} 对手角色设定图，{antagonist_role}，全身与半身肖像，角色参考表",
        },
        {
            "id": "char_03",
            "name": "见证者/助推者",
            "role": "情绪见证者和剧情加速器",
            "visual_lock": "轮廓柔和，固定暖色点缀，年龄感和发长保持一致。",
            "personality": "敏感、观察力强，会揭示关键细节。",
            "image_prompt": f"{title} 助推角色设定图，暖色视觉点缀，AI漫剧角色参考表",
        },
    ]


def _story_asset_text(script: dict | None) -> str:
    if not script:
        return ""
    outline = script.get("episode_outline") or []
    outline_text = "\n".join(
        " ".join(str(ep.get(key, "")) for key in ("title", "cause", "action", "turn", "hook"))
        for ep in outline
    )
    return "\n".join(filter(None, [
        script.get("title", ""),
        script.get("logline", ""),
        script.get("story_promise", ""),
        script.get("main_conflict", ""),
        script.get("why_it_happens", ""),
        script.get("how_it_happens", ""),
        script.get("protagonist_arc", ""),
        script.get("story_draft", ""),
        outline_text,
    ]))


def _story_asset_names(script: dict | None, asset_type: str) -> list[str]:
    text = _story_asset_text(script)
    if not text:
        return []
    story_specific = _story_specific_asset_names(text, asset_type)
    story_specific = _story_specific_asset_names(text, asset_type)
    if asset_type == "props":
        candidates = [
            ("纸人", "纸人新娘"),
            ("红盖头", "红盖头"),
            ("相机", "相机闪光灯"),
            ("照片", "异常照片"),
            ("信", "关键来信"),
            ("手机", "带消息的手机"),
            ("合同", "关键合同"),
            ("钥匙", "断裂钥匙"),
            ("灯笼", "红灯笼"),
            ("剑", "古剑"),
        ]
    else:
        candidates = [
            ("山村", "山村婚礼堂屋"),
            ("婚礼", "山村婚礼堂屋"),
            ("祠堂", "幽暗祠堂"),
            ("地下", "祠堂地下暗室"),
            ("堂屋", "山村婚礼堂屋"),
            ("办公室", "现代办公室"),
            ("夜街", "狭窄夜街"),
            ("停车场", "地下停车场"),
            ("宫", "夜色宫廊"),
            ("庭院", "雨中庭院"),
        ]
    names = []
    names.extend(story_specific)
    for keyword, name in candidates:
        if keyword in text and name not in names:
            names.append(name)
    return names


def _story_specific_asset_names(text: str, asset_type: str) -> list[str]:
    if asset_type == "props":
        candidates = [
            ("粉笔", "粉笔"),
            ("黑板", "倒计时黑板"),
            ("练习册", "最后一本练习册"),
            ("书包", "旧书包"),
            ("同学录", "同学录"),
            ("笔", "转动的笔"),
        ]
    else:
        candidates = [
            ("教室", "高三晚自习教室"),
            ("晚自习", "高三晚自习教室"),
            ("靠窗", "教室靠窗座位"),
            ("讲台", "教室讲台"),
            ("教学楼", "夜晚教学楼"),
            ("校门", "夜晚校门"),
        ]
    names: list[str] = []
    for keyword, name in candidates:
        if keyword in text and name not in names:
            names.append(name)
    return names


def _props_for(genre: str, script: dict | None = None) -> list[dict]:
    story_props = _story_asset_names(script, "props")
    if story_props:
        fallback_names = [name for _, name in _default_props_for_genre(genre) if name not in story_props]
        names = (story_props + fallback_names)[:3]
        base = [(f"prop_{index:02d}", name) for index, name in enumerate(names, start=1)]
    else:
        base = _default_props_for_genre(genre)
    return [
        {
            "id": prop_id,
            "name": name,
            "continuity_rule": "首次出现后，形状、颜色、破损状态和归属关系必须保持一致。",
            "image_prompt": f"{name}，单独道具设定图，干净背景，制作参考图",
        }
        for prop_id, name in base
    ]


def _default_props_for_genre(genre: str) -> list[tuple[str, str]]:
    if _genre_has(genre, "恐怖", "惊悚", "horror", "thriller"):
        return [("prop_01", "关键证物"), ("prop_02", "仪式道具"), ("prop_03", "异常照片")]
    elif _genre_has(genre, "悬疑", "suspense", "detective", "mystery"):
        return [("prop_01", "证物信封"), ("prop_02", "旧手机"), ("prop_03", "断裂钥匙")]
    elif _genre_has(genre, "古风", "幻想", "fantasy", "costume"):
        return [("prop_01", "玉佩信物"), ("prop_02", "密封书信"), ("prop_03", "古剑")]
    elif _genre_has(genre, "科幻", "science", "sci-fi", "future"):
        return [("prop_01", "倒计时终端"), ("prop_02", "身份芯片"), ("prop_03", "城市通行器")]
    return [("prop_01", "关键合同"), ("prop_02", "带消息的手机"), ("prop_03", "象征性信物")]


def _scenes_for(genre: str, script: dict | None = None) -> list[dict]:
    story_scenes = _story_asset_names(script, "scenes")
    if story_scenes:
        fallback_names = [name for _, name in _default_scenes_for_genre(genre) if name not in story_scenes]
        names = (story_scenes + fallback_names)[:3]
        base = [(f"scene_{index:02d}", name) for index, name in enumerate(names, start=1)]
    else:
        base = _default_scenes_for_genre(genre)
    return [
        {
            "id": scene_id,
            "name": name,
            "continuity_rule": "空间布局、主光方向和关键背景物必须保持一致。",
            "image_prompt": f"{name}，环境概念图，竖屏漫剧背景，无人物",
        }
        for scene_id, name in base
    ]


def _default_scenes_for_genre(genre: str) -> list[tuple[str, str]]:
    if _genre_has(genre, "古风", "幻想", "fantasy", "costume"):
        return [("scene_01", "夜色宫廊"), ("scene_02", "雨中庭院"), ("scene_03", "秘密档案室")]
    elif _genre_has(genre, "恐怖", "惊悚", "horror", "thriller"):
        return [("scene_01", "阴冷堂屋"), ("scene_02", "幽暗祠堂"), ("scene_03", "封闭地下室")]
    elif _genre_has(genre, "悬疑", "suspense", "detective", "mystery"):
        return [("scene_01", "昏暗公寓"), ("scene_02", "地下停车场"), ("scene_03", "档案室")]
    elif _genre_has(genre, "科幻", "science", "sci-fi", "future"):
        return [("scene_01", "未来城市路口"), ("scene_02", "高架交通站"), ("scene_03", "废弃控制室")]
    return [("scene_01", "现代办公室"), ("scene_02", "狭窄夜街"), ("scene_03", "私密对峙房间")]


def _shot_plan(
    characters: list[dict],
    props: list[dict],
    scenes: list[dict],
    visual_style: str,
    beats: list[dict],
) -> list[dict]:
    shot_specs = [
        ("shot_001", beats[0]["name"], "特写", "缓慢推进", characters[:1], props[:1], scenes[:1]),
        ("shot_002", beats[1]["name"], "中景", "手持跟拍", characters[:2], props[1:2], scenes[:1]),
        ("shot_003", beats[2]["name"], "超近特写", "固定机位", characters[:1], [], scenes[1:2]),
        ("shot_004", beats[3]["name"], "插入镜头", "快速转焦", [], props[2:3], scenes[1:2]),
        ("shot_005", beats[4]["name"], "低角度双人镜头", "缓慢环绕", characters[:2], props[:1], scenes[2:3]),
        ("shot_006", beats[5]["name"], "远景", "缓慢拉远", characters, props[:1], scenes[2:3]),
    ]
    result = []
    for index, (shot_id, beat, framing, movement, shot_chars, shot_props, shot_scenes) in enumerate(shot_specs, start=1):
        char_names = "、".join(c["name"] for c in shot_chars) or "无可见人物"
        prop_names = "、".join(p["name"] for p in shot_props) or "无关键道具"
        scene_name = shot_scenes[0]["name"] if shot_scenes else "中性背景"
        result.append({
            "id": shot_id,
            "order": index,
            "beat": beat,
            "framing": framing,
            "camera_movement": movement,
            "characters": [c["id"] for c in shot_chars],
            "props": [p["id"] for p in shot_props],
            "scene": shot_scenes[0]["id"] if shot_scenes else "",
            "image_ref": f"{shot_id}_storyboard.png",
            "image_prompt": (
                f"{visual_style}，{framing}，{beat}，场景：{scene_name}，人物：{char_names}，"
                f"道具：{prop_names}，电影感竖屏漫剧分镜图"
            ),
            "video_prompt": f"{movement}，保持{framing}构图，人物动作服务于“{beat}”，竖屏短剧节奏。",
            "negative_prompt": "脸型变化、服装不一致、多余手指、背景扭曲、随机logo、不可读文字、画风漂移",
        })
    return result


def _script_binding_summary(task_id: str, script: dict, confirmed: bool) -> dict:
    script_hash = script.get("script_hash") or _stable_script_hash(script)
    version = int(script.get("script_version") or (1 if confirmed else 0))
    return {
        "script_id": f"script_{task_id}",
        "script_hash": script_hash,
        "script_version": version,
        "confirmed": confirmed,
        "source_type": "confirmed_script" if confirmed else "script_preview",
        "title": script.get("title", "未命名漫剧"),
    }


def _stable_script_hash(script: dict) -> str:
    payload = json.dumps(script or {}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _build_consistency_bindings(
    title: str,
    creative_brief: dict,
    script_source: dict,
    script_binding: dict,
    characters: list[dict],
    props: list[dict],
    scenes: list[dict],
    shots: list[dict],
    episodes: list[dict],
    script_beats: list[dict],
) -> dict:
    beat_map = {beat.get("name", ""): beat for beat in script_beats}
    episode_map = {int(ep.get("episode") or 0): ep for ep in script_source.get("episode_outline", []) or []}

    for index, character in enumerate(characters, start=1):
        binding = {
            "anchor_id": f"character:{character.get('id', index)}",
            "script_hash": script_binding["script_hash"],
            "script_version": script_binding["script_version"],
            "source_fields": ["protagonist_arc", "main_conflict", "story_promise"],
            "continuity_traits": [
                character.get("visual_lock", ""),
                character.get("personality", ""),
            ],
        }
        character["anchor_id"] = binding["anchor_id"]
        character["binding"] = binding
        anchor_text = f"角色锚点：{binding['anchor_id']}；剧本版本：v{binding['script_version']}；核心连续性：{character.get('visual_lock', '')}"
        character["image_prompt"] = f"{character.get('image_prompt', '')}，{anchor_text}".strip("，")

    for prop in props:
        binding = {
            "anchor_id": f"prop:{prop.get('id', '')}",
            "script_hash": script_binding["script_hash"],
            "script_version": script_binding["script_version"],
            "source_fields": ["main_conflict", "episode_outline"],
            "continuity_traits": [prop.get("continuity_rule", "")],
        }
        prop["anchor_id"] = binding["anchor_id"]
        prop["binding"] = binding
        prop["image_prompt"] = (
            f"{prop.get('image_prompt', '')}，道具锚点：{binding['anchor_id']}，连续性：{prop.get('continuity_rule', '')}"
        ).strip("，")

    for index, scene in enumerate(scenes, start=1):
        episode = episode_map.get(index, {})
        story_function = episode.get("title") or episodes[index - 1].get("purpose", "") if index - 1 < len(episodes) else ""
        binding = {
            "anchor_id": f"scene:{scene.get('id', '')}",
            "script_hash": script_binding["script_hash"],
            "script_version": script_binding["script_version"],
            "source_fields": ["episode_outline", "visual_style"],
            "story_function": story_function,
            "continuity_traits": [scene.get("continuity_rule", "")],
        }
        scene["anchor_id"] = binding["anchor_id"]
        scene["binding"] = binding
        if story_function:
            scene["image_prompt"] = f"{scene.get('image_prompt', '')}，剧情用途：{story_function}".strip("，")

    for shot in shots:
        beat = beat_map.get(shot.get("beat", ""), {})
        binding = {
            "anchor_id": f"shot:{shot.get('id', '')}",
            "script_hash": script_binding["script_hash"],
            "script_version": script_binding["script_version"],
            "beat_id": beat.get("id", ""),
            "beat_name": shot.get("beat", ""),
            "beat_content": beat.get("content", ""),
            "scene_id": shot.get("scene", ""),
            "character_ids": list(shot.get("characters", []) or []),
            "prop_ids": list(shot.get("props", []) or []),
            "source_type": script_binding["source_type"],
        }
        shot["binding"] = binding
        continuity_tail = (
            f"镜头锚点：{binding['anchor_id']}；节拍：{binding['beat_id']}；"
            f"场景：{binding['scene_id'] or 'none'}；人物：{'、'.join(binding['character_ids']) or 'none'}；"
            f"道具：{'、'.join(binding['prop_ids']) or 'none'}；剧本哈希：{binding['script_hash']}"
        )
        shot["image_prompt"] = f"{shot.get('image_prompt', '')}，{continuity_tail}".strip("，")
        shot["video_prompt"] = (
            f"{shot.get('video_prompt', '')} 保持镜头锚点 {binding['anchor_id']} 与剧本版本 v{binding['script_version']} 一致。"
        ).strip()

    return {
        "script": {
            **script_binding,
            "story_promise": creative_brief.get("story_promise", ""),
            "main_conflict": creative_brief.get("main_conflict", ""),
            "visual_style": creative_brief.get("visual_style", ""),
            "episode_count": len(script_source.get("episode_outline", []) or []),
        },
        "characters": [
            {
                "id": item.get("id", ""),
                "anchor_id": item.get("anchor_id", ""),
                "source_fields": item.get("binding", {}).get("source_fields", []),
            }
            for item in characters
        ],
        "props": [
            {
                "id": item.get("id", ""),
                "anchor_id": item.get("anchor_id", ""),
                "source_fields": item.get("binding", {}).get("source_fields", []),
            }
            for item in props
        ],
        "scenes": [
            {
                "id": item.get("id", ""),
                "anchor_id": item.get("anchor_id", ""),
                "story_function": item.get("binding", {}).get("story_function", ""),
            }
            for item in scenes
        ],
        "shots": [
            {
                "id": item.get("id", ""),
                "anchor_id": item.get("binding", {}).get("anchor_id", ""),
                "beat_id": item.get("binding", {}).get("beat_id", ""),
                "scene_id": item.get("binding", {}).get("scene_id", ""),
            }
            for item in shots
        ],
        "production_rule": "所有下游资产必须继承同一个 script_hash/script_version；剧本一旦变更，需按锚点局部返工。",
        "scope": f"{title} 漫剧资产一致性绑定",
    }


def _format_package_overview(**data) -> str:
    title = data["title"]
    lines = [
        f"# {title} - AI漫剧前期制作包",
        "",
        "## 完整故事稿",
        data["script_preview"].get("story_draft", ""),
        "",
        "## 内阁剧本预审",
        format_script_preview(data["script_preview"]),
        "",
        "## 创作锁定稿",
        format_creative_brief(data["creative_brief"]),
        "",
        "## 交付边界",
        "- 本办公室交付剧本、内阁意见、人物图、道具图、场景图、分镜图、运镜方案、提示词和Word制片画布。",
        "- 最终视频生成、配音、剪辑和发布不属于本办公室交付范围。",
        "",
        "## 一致性闭环",
        "先锁定剧本和风格，再拆资产，再生成分镜和提示词。每张图都必须能回扣剧本、角色、场景和道具编号。",
        "",
        "## 分镜数量",
        f"- {len(data['shots'])} 个镜头",
    ]
    return "\n".join(lines)


# ---- AI comic production v2 helpers ----
# These override the older template-heavy helpers above. The goal is to keep the
# production package story-driven: confirmed story text must feed characters,
# props, scenes, storyboard beats, prompts, and the final canvas.


def _normal_label_value(section: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        match = re.search(rf"[-*]?\s*{re.escape(label)}\s*[:：]\s*(.+)", section)
        if match:
            return match.group(1).strip()
    return ""


def _clean_key_turns(value) -> list[str]:
    if isinstance(value, str):
        items = [value.strip()]
    else:
        items = [str(item).strip() for item in (value or []) if str(item).strip()]
    if len(items) > 3 and all(len(item) <= 2 for item in items):
        joined = "".join(items).strip()
        return [joined] if joined else []
    return [item for item in items if item]


def _markdown_section_any(text: str, headings: tuple[str, ...], stop_headings: tuple[str, ...] = ()) -> str:
    for heading in headings:
        value = _markdown_section(text, heading, stop_headings)
        if value:
            return value
    return ""


def _story_sentences(text: str, limit: int = 6) -> list[str]:
    clean = re.sub(r"\s+", "", text or "")
    if not clean:
        return []
    parts = [item.strip() for item in re.split(r"[。！？!?]\s*", clean) if item.strip()]
    if len(parts) < 2:
        parts = [item.strip() for item in re.split(r"[，,；;]\s*", clean) if item.strip()]
    return [part[:80] for part in parts if len(part) >= 4][:limit]


def _short_story_label(text: str) -> str:
    text = re.sub(r"\s+", "", text or "")
    return text[:14] or "关键剧情"


def _normal_episode_outline(section: str) -> list[dict]:
    episodes = []
    pattern = re.compile(
        r"^(\d+)[.、]\s*(.+?)[｜|]\s*起因[:：](.+?)[｜|]\s*行动[:：](.+?)[｜|]\s*转折[:：](.+?)[｜|]\s*钩子[:：](.+)$",
        re.MULTILINE,
    )
    for match in pattern.finditer(section):
        episodes.append({
            "episode": int(match.group(1)),
            "title": match.group(2).strip(),
            "cause": match.group(3).strip(),
            "action": match.group(4).strip(),
            "turn": match.group(5).strip(),
            "hook": match.group(6).strip(),
        })
    return episodes


def _parse_confirmed_script(text: str) -> dict:
    if "Confirmed script:" not in text:
        return {}
    section = text.split("Confirmed script:", 1)[1].split("Script notes:", 1)[0]
    title_match = re.search(r"#\s*(.+?)\s*(?:\u786e\u8ba4\u7248\u5267\u672c)", section)
    parsed = {"title": title_match.group(1).strip() if title_match else ""}
    parsed["status"] = _normal_label_value(section, ("\u72b6\u6001",)) or "confirmed"
    version = _normal_label_value(section, ("\u5267\u672c\u7248\u672c",))
    if version.isdigit():
        parsed["script_version"] = int(version)
    parsed["script_hash"] = _normal_label_value(section, ("\u5267\u672c\u54c8\u5e0c",))
    parsed["story_promise"] = _normal_label_value(section, ("\u6545\u4e8b\u627f\u8bfa",))
    parsed["main_conflict"] = _normal_label_value(section, ("\u4e3b\u51b2\u7a81",))
    parsed["logline"] = _normal_label_value(section, ("\u4e00\u53e5\u8bdd\u6545\u4e8b",))
    parsed["why_it_happens"] = _normal_label_value(section, ("\u4e3a\u4ec0\u4e48\u53d1\u751f",))
    parsed["how_it_happens"] = _normal_label_value(section, ("\u5982\u4f55\u53d1\u751f",))
    parsed["protagonist_arc"] = _normal_label_value(section, ("\u4e3b\u89d2\u53d8\u5316",))
    parsed["platform"] = _normal_label_value(section, ("\u5e73\u53f0",))
    parsed["visual_style"] = _normal_label_value(section, ("\u89c6\u89c9\u98ce\u683c",))
    story_draft = _markdown_section_any(
        section,
        ("\u5b8c\u6574\u6545\u4e8b\u7a3f",),
        ("\u6bcf\u96c6\u786e\u8ba4\u5927\u7eb2", "\u6bcf\u96c6\u5927\u7eb2", "\u5173\u952e\u8f6c\u6298", "\u5185\u9601\u5171\u8bc6", "\u7528\u6237\u6700\u7ec8\u8981\u6c42", "\u751f\u4ea7\u95f8\u95e8"),
    )
    if story_draft:
        parsed["story_draft"] = story_draft
    episodes = _normal_episode_outline(section)
    if episodes:
        parsed["episode_outline"] = episodes
    if "\n## \u5173\u952e\u8f6c\u6298" in section:
        turn_section = section.split("## \u5173\u952e\u8f6c\u6298", 1)[1].split("##", 1)[0]
        turns = [item.strip() for item in re.findall(r"^- (.+)$", turn_section, re.MULTILINE)]
        if turns:
            parsed["key_turns"] = _clean_key_turns(turns)
    if parsed.get("episode_outline"):
        parsed["episode_outline"] = _repair_episode_outline(
            parsed["episode_outline"],
            parsed.get("key_turns") or [],
            parsed.get("story_draft", "") or parsed.get("logline", ""),
        )
    return parsed if any(parsed.get(key) for key in ("story_draft", "story_promise", "main_conflict", "logline", "why_it_happens")) else {}


def _repair_episode_outline(outline: list[dict], key_turns, story_text: str = "") -> list[dict]:
    turns = _clean_key_turns(key_turns)
    fallback_turn = turns[0] if turns else ""
    fallback_hook = turns[-1] if turns else ((_story_sentences(story_text, limit=8) or [""])[-1])
    repaired = []
    for item in outline or []:
        ep = dict(item)
        if len(str(ep.get("turn", "")).strip()) <= 2 and fallback_turn:
            ep["turn"] = fallback_turn
        if len(str(ep.get("hook", "")).strip()) <= 2 and fallback_hook:
            ep["hook"] = fallback_hook
        repaired.append(ep)
    return repaired


def _confirmed_episode_outline(script_preview: dict) -> list[dict]:
    outline = list((script_preview or {}).get("episode_outline") or [])
    if outline:
        return _repair_episode_outline(outline, (script_preview or {}).get("key_turns") or [], (script_preview or {}).get("story_draft", ""))
    story_draft = (script_preview or {}).get("story_draft", "").strip()
    logline = (script_preview or {}).get("logline", "").strip()
    if not story_draft and not logline:
        return []
    key_turns = _clean_key_turns((script_preview or {}).get("key_turns") or [])
    sentences = _story_sentences(story_draft or logline, limit=3)
    return [{
        "episode": 1,
        "title": _short_story_label(sentences[0] if sentences else logline or story_draft),
        "cause": logline or (sentences[0] if sentences else story_draft[:80]),
        "action": sentences[1] if len(sentences) > 1 else "围绕完整故事稿拆分人物、场景、道具和关键画面",
        "turn": key_turns[0] if key_turns else (sentences[1] if len(sentences) > 1 else ""),
        "hook": key_turns[-1] if key_turns else (sentences[-1] if sentences else "结尾留下下一步需要延续的画面钩子"),
    }]


def _script_beats_from_preview(script: dict) -> list[dict]:
    beats = []
    for ep in script.get("episode_outline", []) or []:
        action = ep.get("action") or ep.get("cause") or ep.get("title") or ""
        beats.append({
            "id": f"beat_{int(ep.get('episode', len(beats) + 1)):02d}",
            "name": _short_story_label(action),
            "content": f"起因：{ep.get('cause', '')}；行动：{ep.get('action', '')}；转折：{ep.get('turn', '')}；钩子：{ep.get('hook', '')}",
        })
    story_text = "\n".join(filter(None, [
        script.get("story_draft", ""),
        script.get("how_it_happens", ""),
        script.get("why_it_happens", ""),
    ]))
    for sentence in _story_sentences(story_text, limit=8):
        if len(beats) >= 6:
            break
        if sentence not in " ".join(item["name"] for item in beats):
            beats.append({
                "id": f"beat_{len(beats) + 1:02d}",
                "name": _short_story_label(sentence),
                "content": sentence,
            })
    while len(beats) < 6 and beats:
        source = beats[-1]["content"] or beats[-1]["name"]
        beats.append({
            "id": f"beat_{len(beats) + 1:02d}",
            "name": _short_story_label(source),
            "content": source,
        })
    if not beats:
        beats = [{"id": "beat_01", "name": "关键剧情", "content": script.get("logline", "") or "待补充完整故事稿"}]
    return beats[:6]


def _detected_story_characters(script: dict) -> list[tuple[str, str]]:
    text = _story_asset_text(script)
    pairs: list[tuple[str, str]] = []
    generic_names = _probable_chinese_names(text)
    if "辅助阿衡" in text or "阿衡" in text or "辅助" in text:
        pairs.append(("辅助阿衡", "被长期忽视却照顾所有人的队伍辅助"))
    for name, role in [
        ("大师兄", "队伍中习惯接受照顾的核心战力"),
        ("二师姐", "外冷内热、依赖辅助准备伤药的队友"),
        ("小师弟", "常丢聚气丹、最晚意识到失去的人"),
        ("贵人", "制造死亡事件却漠视生命的权势者"),
        ("护卫", "直接造成辅助死亡的执行者"),
    ]:
        if name in text:
            pairs.append((name, role))
    if not pairs:
        for name in generic_names:
            pairs.append((name, "故事主角或关键行动者"))
    return pairs[:4]


def _probable_chinese_names(text: str) -> list[str]:
    blocked = {
        "高三", "最后", "晚自", "教室", "窗外", "黑板", "讲台", "粉笔", "书包", "练习",
        "同学", "教学", "校门", "未来", "故事", "主角", "视觉", "平台", "自然", "灯光",
        "在黑", "角落", "指向", "走向", "独自", "下课", "一起", "一个", "最后",
        "毕业", "季散", "高考", "前夜", "迷茫", "熟悉", "陌生", "接受", "未知",
    }
    common_surnames = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程邢裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘斜厉戎祖武符刘景詹龙叶幸司韶黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧利师巩聂关荆"
    action_names = _action_context_names(text, common_surnames)
    if action_names:
        return action_names[:3]
    surname_names: list[str] = []
    invalid_names = {"解释", "关系", "线索", "关键", "故事", "人物", "身份", "主角", "对手", "镜头", "场景"}
    bad_name_second_chars = set("会的了在是和与被将能要有不中后前着过到这那更最就很还把给对从向，。、；：")
    reliable_surnames = set("赵钱孙李周吴郑王冯陈蒋沈韩杨朱秦许何吕张孔曹严华金魏陶姜谢邹喻苏潘葛范彭鲁韦马方任袁柳史唐薛雷贺倪汤罗毕郝安常于傅齐康伍余元顾孟平黄萧尹姚汪祁毛米贝明戴宋庞熊纪舒项祝董梁杜阮席季贾路江童颜郭梅盛林钟徐邱骆高夏蔡田胡凌万管卢莫房应宗丁宣邓杭洪包左石崔吉龚程邢裴陆荣曲家封储段富焦巴山谷车侯全班秋仲伊宫宁仇甘武刘景詹龙叶司黎白怀从索赖卓蒙池乔双党谭申燕温庄柴阎古易慎戈廖居衡满弘文欧聂辛简饶丰关查荆游权盖益桓")
    for index in range(max(0, len(text or "") - 1)):
        name = (text or "")[index:index + 2]
        if not name or name[0] not in common_surnames:
            continue
        if name[0] not in reliable_surnames:
            continue
        if name in invalid_names:
            continue
        if len(name) > 1 and name[1] in bad_name_second_chars:
            continue
        if name not in blocked and name not in surname_names:
            surname_names.append(name)
    if surname_names:
        return surname_names[:3]
    return []


def _action_context_names(text: str, common_surnames: str) -> list[str]:
    names: list[str] = []
    invalid_names = {"解释", "关系", "线索", "关键", "故事", "人物", "身份", "主角", "对手", "镜头", "场景"}
    bad_name_second_chars = set("会的了在是和与被将能要有不中后前着过到这那更最就很还把给对从向，。、；：")
    for match in re.finditer(r"([\u4e00-\u9fff]{2,3})(?:坐在|拒绝|留到|走到|拿起|画了|画下|回到|走出|回头|加快|决定|没有加入)", text or ""):
        raw = match.group(1)
        name = raw[:2] if raw[:1] in common_surnames else raw[-2:]
        if name[:1] not in common_surnames:
            continue
        if name in invalid_names:
            continue
        if len(name) > 1 and name[1] in bad_name_second_chars:
            continue
        if name and name not in names:
            names.append(name)
    return names


def _characters_for(title: str, genre: str, brief: dict, user_answers: str, script: dict) -> list[dict]:
    detected = _detected_story_characters(script)
    if not detected:
        detected = [("主角", "推动故事行动的人"), ("对手", "制造压力和阻碍的人"), ("见证者/助推者", "情绪见证者和剧情加速器")]
    result = []
    for index, (name, role) in enumerate(detected, start=1):
        result.append({
            "id": f"char_{index:02d}",
            "name": name,
            "role": role,
            "visual_lock": "保持同一脸型、发型、服装主色和年龄感；不要在画面中出现角色编号或文字标签。",
            "personality": script.get("protagonist_arc", "") if index == 1 else role,
            "image_prompt": f"{title}，{name}人物设定图，{role}，清晰正脸参考，全身站姿，中性表情，角色三视图，制作设定稿，不要文字，不要标签",
        })
    return result


def _story_asset_names(script: dict | None, asset_type: str) -> list[str]:
    text = _story_asset_text(script)
    if not text:
        return []
    story_specific = _story_specific_asset_names(text, asset_type)
    if asset_type == "props":
        candidates = [
            ("桂花糕", "桂花糕"),
            ("止血散", "止血散"),
            ("聚气丹", "聚气丹"),
            ("药包", "散落的药包"),
            ("车驾", "贵人车驾"),
            ("尸体", "小巷里的尸体"),
            ("纸人", "纸人新娘"),
            ("红盖头", "红盖头"),
            ("相机", "相机闪光灯"),
            ("照片", "异常照片"),
            ("信", "关键来信"),
            ("手机", "带消息的手机"),
            ("合同", "关键合同"),
            ("钥匙", "断裂钥匙"),
            ("灯笼", "红灯笼"),
            ("剑", "古剑"),
        ]
    else:
        candidates = [
            ("下山", "山下街市"),
            ("街", "山下街市"),
            ("小巷", "偏僻小巷"),
            ("晚饭", "修仙队伍驻地"),
            ("队友", "修仙队伍驻地"),
            ("山村", "山村婚礼堂屋"),
            ("婚礼", "山村婚礼堂屋"),
            ("祠堂", "幽暗祠堂"),
            ("地下", "祠堂地下暗室"),
            ("办公室", "现代办公室"),
            ("夜街", "狭窄夜街"),
            ("停车场", "地下停车场"),
            ("宫", "夜色宫廊"),
            ("庭院", "雨中庭院"),
        ]
    names = []
    names.extend(story_specific)
    for keyword, name in candidates:
        if keyword in text and name not in names:
            names.append(name)
    return names


def _shot_plan(
    characters: list[dict],
    props: list[dict],
    scenes: list[dict],
    visual_style: str,
    beats: list[dict],
) -> list[dict]:
    visual_style = _premium_visual_style(visual_style)
    framings = ["特写", "中景", "超近特写", "插入镜头", "低角度双人镜头", "远景"]
    movements = ["缓慢推进", "手持跟拍", "固定机位", "快速转焦", "缓慢环绕", "缓慢拉远"]
    result = []
    for index, beat in enumerate(beats[:6], start=1):
        shot_id = f"shot_{index:03d}"
        shot_chars = characters[:1] if index in (1, 3) else characters[:2]
        if index == 6:
            shot_chars = characters[:3]
        shot_props = props[(index - 1) % len(props):((index - 1) % len(props)) + 1] if props else []
        shot_scenes = scenes[(index - 1) % len(scenes):((index - 1) % len(scenes)) + 1] if scenes else []
        char_names = "、".join(c["name"] for c in shot_chars) or "无可见人物"
        prop_names = "、".join(p["name"] for p in shot_props) or "无关键道具"
        scene_name = shot_scenes[0]["name"] if shot_scenes else "中性背景"
        framing = framings[(index - 1) % len(framings)]
        movement = movements[(index - 1) % len(movements)]
        beat_text = beat.get("content") or beat.get("name") or ""
        result.append({
            "id": shot_id,
            "order": index,
            "beat": beat_text,
            "framing": framing,
            "camera_movement": movement,
            "characters": [c["name"] for c in shot_chars],
            "character_ids": [c["id"] for c in shot_chars],
            "props": [p["name"] for p in shot_props],
            "prop_ids": [p["id"] for p in shot_props],
            "scene": scene_name,
            "scene_id": shot_scenes[0]["id"] if shot_scenes else "",
            "image_ref": f"{shot_id}_storyboard.png",
            "image_prompt": (
                f"{visual_style}，竖屏AI漫剧关键分镜，{framing}，{beat_text}，场景：{scene_name}，"
                f"人物：{char_names}，道具：{prop_names}。电影级画面，主体清晰，前景/中景/背景层次明确，"
                f"情绪表达强，镜头有叙事目的，光影统一，角色脸型和服装必须参考已生成角色设定，"
                f"道具和场景必须参考资产设定，不要文字，不要字幕，不要标签，不要编号，不要水印。"
            ),
            "video_prompt": f"{movement}，保持{framing}构图，人物动作服务于“{beat_text}”，镜头运动克制但有情绪推进，竖屏短剧节奏，保持人物脸型、服装、道具和场景连续。",
            "negative_prompt": "脸型变化、服装不一致、多余手指、背景扭曲、随机logo、不可读文字、画风漂移、画面标签、编号文字",
        })
    return result


def _build_consistency_bindings(
    title: str,
    creative_brief: dict,
    script_source: dict,
    script_binding: dict,
    characters: list[dict],
    props: list[dict],
    scenes: list[dict],
    shots: list[dict],
    episodes: list[dict],
    script_beats: list[dict],
) -> dict:
    beat_map = {beat.get("content", ""): beat for beat in script_beats}
    for character in characters:
        character["anchor_id"] = f"character:{character.get('id', '')}"
        character["binding"] = {
            "anchor_id": character["anchor_id"],
            "script_hash": script_binding["script_hash"],
            "script_version": script_binding["script_version"],
            "source_fields": ["story_draft", "protagonist_arc", "main_conflict"],
            "continuity_traits": [character.get("visual_lock", ""), character.get("personality", "")],
        }
    for prop in props:
        prop["anchor_id"] = f"prop:{prop.get('id', '')}"
        prop["binding"] = {
            "anchor_id": prop["anchor_id"],
            "script_hash": script_binding["script_hash"],
            "script_version": script_binding["script_version"],
            "source_fields": ["story_draft", "episode_outline"],
            "continuity_traits": [prop.get("continuity_rule", "")],
        }
    for scene in scenes:
        scene["anchor_id"] = f"scene:{scene.get('id', '')}"
        scene["binding"] = {
            "anchor_id": scene["anchor_id"],
            "script_hash": script_binding["script_hash"],
            "script_version": script_binding["script_version"],
            "source_fields": ["story_draft", "episode_outline", "visual_style"],
            "story_function": scene.get("name", ""),
            "continuity_traits": [scene.get("continuity_rule", "")],
        }
    for shot in shots:
        beat = beat_map.get(shot.get("beat", ""), {})
        shot["binding"] = {
            "anchor_id": f"shot:{shot.get('id', '')}",
            "script_hash": script_binding["script_hash"],
            "script_version": script_binding["script_version"],
            "beat_id": beat.get("id", ""),
            "beat_name": beat.get("name", ""),
            "beat_content": beat.get("content", ""),
            "scene_id": shot.get("scene_id", ""),
            "character_ids": list(shot.get("character_ids", []) or []),
            "prop_ids": list(shot.get("prop_ids", []) or []),
            "source_type": script_binding["source_type"],
        }
    return {
        "script": {
            **script_binding,
            "story_promise": creative_brief.get("story_promise", ""),
            "main_conflict": creative_brief.get("main_conflict", ""),
            "visual_style": creative_brief.get("visual_style", ""),
            "episode_count": len(script_source.get("episode_outline", []) or []),
        },
        "characters": [{"id": item.get("id", ""), "anchor_id": item.get("anchor_id", ""), "source_fields": item.get("binding", {}).get("source_fields", [])} for item in characters],
        "props": [{"id": item.get("id", ""), "anchor_id": item.get("anchor_id", ""), "source_fields": item.get("binding", {}).get("source_fields", [])} for item in props],
        "scenes": [{"id": item.get("id", ""), "anchor_id": item.get("anchor_id", ""), "story_function": item.get("binding", {}).get("story_function", "")} for item in scenes],
        "shots": [{"id": item.get("id", ""), "anchor_id": item.get("binding", {}).get("anchor_id", ""), "beat_id": item.get("binding", {}).get("beat_id", ""), "scene_id": item.get("binding", {}).get("scene_id", "")} for item in shots],
        "production_rule": "所有下游资产必须继承同一 script_hash/script_version；编号只保存在元数据和表格里，不能进入画面。",
        "scope": f"{title} 漫剧资产一致性绑定",
    }
