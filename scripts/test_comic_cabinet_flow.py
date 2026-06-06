from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.comic_artifacts import build_comic_artifacts
from src.comic_office import build_comic_request, build_comic_result
from src.comic_word_canvas import build_comic_word_canvas
from src.web.app import app


SCENARIOS = [
    {
        "name": "漫画世界悬疑成长",
        "idea": "一个普通女孩每天醒来都会进入不同漫画世界，必须找到让自己回到现实的作者签名",
        "genre": "fantasy suspense",
        "length": "5 episodes, 45 seconds each",
        "platform": "Douyin vertical comic drama",
        "visual_style": "Korean webtoon, emotional close-ups",
        "extra": "希望有悬疑感，结尾要发现漫画世界和她童年有关",
        "answers": "主角是普通高中女生，观众先同情她；结尾要反转但不黑暗；必须出现一本会自动改写的漫画书。",
        "notes": "第一集不要解释太多，用画面展示她醒来换世界。",
    },
    {
        "name": "民国钟表悬疑",
        "idea": "民国修表匠发现一只怀表能让案发现场倒退三分钟，但每用一次都会丢失一段记忆",
        "genre": "suspense detective",
        "length": "3 episodes, 60 seconds each",
        "platform": "Bilibili comic video",
        "visual_style": "dark suspense comic, rain night, realistic backgrounds",
        "extra": "不要爽剧，要克制、雨夜、证据反转",
        "answers": "主角是年轻女修表匠，观众先怀疑她；结尾要开放式悬念；怀表和一张烧焦照片必须出现。",
        "notes": "第二集要让观众误以为警探是反派。",
    },
]


def main() -> None:
    client = TestClient(app)
    for index, item in enumerate(SCENARIOS, start=1):
        payload = {key: item[key] for key in ["idea", "genre", "length", "platform", "visual_style", "extra"]}
        brief_response = client.post("/api/comic/brief", json=payload)
        assert brief_response.status_code == 200, brief_response.text
        brief_payload = brief_response.json()
        brief = brief_payload["creative_brief"]

        script_response = client.post(
            "/api/comic/script-preview",
            json={**payload, "creative_brief": brief, "user_answers": item["answers"]},
        )
        assert script_response.status_code == 200, script_response.text
        script_payload = script_response.json()
        script = script_payload["script_preview"]

        request = build_comic_request(
            idea=item["idea"],
            genre=item["genre"],
            length=item["length"],
            platform=item["platform"],
            visual_style=item["visual_style"],
            extra=item["extra"],
            creative_brief=brief,
            user_answers=item["answers"],
            script_preview=script,
            script_notes=item["notes"],
        )
        result = build_comic_result(f"cabinet-test-{index}", request)
        artifacts = build_comic_artifacts(f"cabinet-test-{index}", result)
        artifact_types = {artifact["artifact_type"] for artifact in artifacts}
        assert {"script_preview", "cabinet_review", "production_canvas", "word_canvas"}.issubset(artifact_types)
        assert len(script["cabinet_review"]) == 5
        assert len(script["episode_outline"]) == (5 if index == 1 else 3)

        docx = build_comic_word_canvas(
            result["comic_package"],
            [],
            Path("output/model_tests/cabinet") / f"scenario_{index}",
        )
        assert docx.exists() and docx.stat().st_size > 10000

        print(
            "scenario={index} status=ok questions={questions} episodes={episodes} "
            "cabinet_roles={roles} artifacts={artifacts} docx_bytes={bytes}".format(
                index=index,
                questions=len(brief["clarifying_questions"]),
                episodes=len(script["episode_outline"]),
                roles=len(script["cabinet_review"]),
                artifacts=len(artifacts),
                bytes=docx.stat().st_size,
            )
        )


if __name__ == "__main__":
    main()
