"""Shot template library for the AI comic production office."""

from __future__ import annotations


SHOT_TEMPLATES: dict[str, dict[str, str]] = {
    "dialogue_close_parallel": {
        "template_id": "dialogue_close_parallel",
        "name": "对话特写平行视角",
        "purpose": "用于诱导、追问、坦白、情绪试探等台词驱动镜头。",
        "framing": "特写平行视角",
        "movement": "固定镜头一镜到底",
        "composition": "人物眼睛和嘴角占画面重心，肩颈与手部动作保留在下三分之一，背景轻微虚化。",
        "cinematography": "变形宽荧幕电影质感，浅景深保留眼神、嘴角和呼吸变化，镜头贴近面部但不压迫五官。",
        "platform_note": "适合图生视频首帧参考，重点约束表演节奏、眼神方向和口型自然度。",
    },
    "death_reveal_pause": {
        "template_id": "death_reveal_pause",
        "name": "发现死亡停顿镜头",
        "purpose": "用于尸体、失踪、跳楼、撞击后的迟来意识和情绪空白。",
        "framing": "中近景跟随到低角度停顿",
        "movement": "手持轻微跟随后突然停住",
        "composition": "先让人物或道具遮挡一部分真相，再露出关键结果，给观众和角色共同反应时间。",
        "cinematography": "不追求刺激，重点放在迟来的意识、空白感、手部僵住和视线失焦。",
        "platform_note": "适合慢速镜头，避免血腥猎奇，失败时优先重试人物表情和空间遮挡关系。",
    },
    "clue_insert_reaction": {
        "template_id": "clue_insert_reaction",
        "name": "线索插入接反应",
        "purpose": "用于证物、秘密、关键道具、身份线索第一次被看见。",
        "framing": "道具插入镜头接人物反应特写",
        "movement": "固定机位慢慢转焦",
        "composition": "焦点先落在可见线索的材质和位置，再转向人物眼神反应。",
        "cinematography": "用焦点变化完成认知变化，线索要清楚但禁止文字水印和无关符号。",
        "platform_note": "适合首帧用道具资产，第二段动作写人物反应，降低随机生成新道具的概率。",
    },
    "decision_side_medium": {
        "template_id": "decision_side_medium",
        "name": "选择决定中景",
        "purpose": "用于拒绝、离开、复仇、追查、做出不可逆选择。",
        "framing": "中景侧面视角",
        "movement": "固定机位轻微推进",
        "composition": "人物站位和身体方向表达选择，画面保留前后空间，关系压力清晰。",
        "cinematography": "让身体转向、手部收回、视线变硬承担戏剧变化，避免夸张动作。",
        "platform_note": "适合强调行动方向，失败时重试人物站位、视线和手部动作。",
    },
    "wide_spatial_establishing": {
        "template_id": "wide_spatial_establishing",
        "name": "空间建立广角",
        "purpose": "用于街道、房间、宗门、办公室、驻地等空间关系说明。",
        "framing": "广角建立视角",
        "movement": "缓慢拉远或横移",
        "composition": "先交代入口、出口、关键道具和人物位置，再让主体动作进入画面中心。",
        "cinematography": "广角展示空间边界、动线和机位参考，保持环境结构不漂移。",
        "platform_note": "适合绑定场景广角图或俯视图，失败时优先回到场景资产重约束。",
    },
    "emotion_micro_closeup": {
        "template_id": "emotion_micro_closeup",
        "name": "情绪微表情特写",
        "purpose": "用于压抑、犹豫、悲伤、愤怒尚未爆发的内心变化。",
        "framing": "超近特写",
        "movement": "固定机位轻微推进",
        "composition": "眼神、呼吸、嘴角和手指细节承担情绪，不用夸张表演。",
        "cinematography": "长焦浅景深，主体面部稳定，背景只保留情绪色块和空间暗示。",
        "platform_note": "适合单人镜头，失败时重试眼神方向和表情幅度。",
    },
}


def select_shot_template(beat_text: str, index: int) -> dict[str, str]:
    """Pick a reusable shot template from the story beat."""
    text = beat_text or ""
    if any(word in text for word in ("说", "问", "开口", "台词", "诱导", "追问", "对话")):
        return dict(SHOT_TEMPLATES["dialogue_close_parallel"])
    if any(word in text for word in ("尸体", "死亡", "死在", "撞", "倒下", "失踪", "跳楼")):
        return dict(SHOT_TEMPLATES["death_reveal_pause"])
    if any(word in text for word in ("发现", "看见", "意识到", "线索", "证据", "秘密")):
        return dict(SHOT_TEMPLATES["clue_insert_reaction"])
    if any(word in text for word in ("拒绝", "决定", "选择", "离开", "复仇", "追查")):
        return dict(SHOT_TEMPLATES["decision_side_medium"])
    if any(word in text for word in ("空间", "门", "入口", "街", "巷", "房间", "办公室", "山路", "驻地")):
        return dict(SHOT_TEMPLATES["wide_spatial_establishing"])
    fallback_order = [
        "dialogue_close_parallel",
        "decision_side_medium",
        "emotion_micro_closeup",
        "wide_spatial_establishing",
    ]
    return dict(SHOT_TEMPLATES[fallback_order[(index - 1) % len(fallback_order)]])
