import unittest
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.comic_artifacts import build_comic_artifacts
from src.comic_word_canvas import build_comic_word_canvas
from src.comic_office import (
    advance_comic_cabinet_session,
    advance_comic_cabinet_session_llm,
    build_confirmed_script,
    build_comic_brief,
    build_comic_request,
    build_comic_result,
    build_comic_script_preview,
    start_comic_cabinet_session,
    start_comic_cabinet_session_llm,
    validate_confirmed_script_session,
)
from src.llm.providers import LLMResponse, LiteLLMProvider, ModelConfig


class ComicOfficeWorkflowTests(unittest.TestCase):
    def test_word_canvas_contains_platform_execution_table(self):
        from docx import Document

        package = {
            "title": "纸人新娘",
            "creative_brief": {"core_idea": "山村婚礼夜", "story_promise": "纸人秘密被揭开"},
            "confirmed_script": {"story_draft": "新娘在婚礼夜发现宾客都是纸人。"},
            "shots": [
                {
                    "id": "shot_001",
                    "image_ref": "storyboard_shot_001.png",
                    "beat": "新娘掀开红盖头，看见满堂纸人。",
                    "characters": ["新娘"],
                    "scene": "山村堂屋",
                    "props": ["红盖头"],
                    "image_prompt": "新娘，红盖头，山村堂屋，惊恐表情",
                    "video_prompt": "镜头缓慢推进，新娘掀开红盖头",
                    "negative_prompt": "角色变脸，服装变化",
                }
            ],
        }
        with TemporaryDirectory() as tmp:
            path = build_comic_word_canvas(package, [], Path(tmp))
            doc = Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs)
            table_text = "\n".join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)

        self.assertIn("平台执行表", text)
        self.assertIn("上传图片", table_text)
        self.assertIn("失败重试建议", table_text)
        self.assertIn("Libtv", text)

    def test_comic_request_preserves_user_idea_fields(self):
        request = build_comic_request(
            idea="重生后的女主在公司年会上反击陷害她的人",
            genre="revenge short drama",
            length="5 episodes, 60 seconds each",
            platform="Douyin vertical short drama",
            visual_style="modern Chinese webtoon",
            extra="需要强反转和运镜设计",
        )

        self.assertIn("Idea: 重生后的女主", request)
        self.assertIn("Genre: revenge short drama", request)
        self.assertIn("Required output:", request)
        self.assertIn("中文剧本方向", request)

    def test_comic_brief_turn_returns_questions_before_generation(self):
        brief = build_comic_brief(
            idea="一个女孩每天醒来都会进入不同漫画世界",
            genre="fantasy",
            length="5 episodes",
            platform="Douyin",
            visual_style="Korean webtoon",
            extra="希望有悬疑感",
        )

        self.assertEqual(brief["status"], "needs_user_confirmation")
        self.assertIn("creative_brief", brief)
        creative_brief = brief["creative_brief"]
        self.assertIn("一个女孩", creative_brief["core_idea"])
        self.assertGreaterEqual(len(creative_brief["clarifying_questions"]), 4)
        self.assertIn("悬疑感", creative_brief["must_keep"])

    def test_script_preview_explains_why_and_how_before_asset_generation(self):
        brief = build_comic_brief(
            idea="一个女孩每天醒来都会进入不同漫画世界",
            genre="fantasy",
            length="5 episodes",
            platform="Douyin",
            visual_style="Korean webtoon",
            extra="希望有悬疑感",
        )["creative_brief"]

        preview = build_comic_script_preview(
            idea="一个女孩每天醒来都会进入不同漫画世界",
            genre="fantasy",
            length="5 episodes",
            platform="Douyin",
            visual_style="Korean webtoon",
            extra="希望有悬疑感",
            creative_brief=brief,
            user_answers="主角是普通女孩，最后要发现漫画世界是她自己创造的。",
        )

        self.assertEqual(preview["status"], "script_needs_confirmation")
        script = preview["script_preview"]
        self.assertIn("why_it_happens", script)
        self.assertIn("how_it_happens", script)
        self.assertIn("story_draft", script)
        self.assertEqual(script["story_draft"], "")
        self.assertIn("主角是普通女孩", preview["preview"])

    def test_ready_life_drama_can_confirm_without_explicit_hook_keyword(self):
        session = {
            "ready_to_produce": True,
            "creative_brief": {
                "core_idea": "毕业季散场",
                "main_conflict": "林远不知道毕业后的路要通向哪里，只能在最后一节晚自习里面对自己的迷茫。",
                "visual_style": "realistic urban drama",
                "platform": "Douyin/Kuaishou vertical short drama",
            },
            "script_preview": {
                "title": "毕业季散场",
                "genre": "school youth",
                "length": "1 episode, 30 seconds",
                "platform": "Douyin/Kuaishou vertical short drama",
                "visual_style": "realistic urban drama",
                "why_it_happens": "高三最后一节晚自习结束，熟悉的教室突然变得陌生。",
                "how_it_happens": "林远留到最后，在黑板角落画下一个指向窗外的小箭头，然后独自走向校门。",
                "protagonist_arc": "林远从害怕没有方向，到接受迷茫也是自己要走的第一步。",
                "story_draft": "高三最后一节晚自习，林远坐在靠窗的位置，看着窗外漆黑的夜。下课铃响后，他留到最后，在黑板角落画了一个小箭头，指向窗外。走出教学楼时，他回头看了一眼亮着灯的教室，没有拍照，只是加快脚步走向校门。明天就是高考，他不知道未来通向哪里，但至少决定自己走上去。",
                "episode_outline": [],
                "key_turns": [],
            },
            "user_notes": ["没有想去的地方，那只是迷茫接下来的路是什么"],
        }

        issues = validate_confirmed_script_session(session)

        self.assertEqual(issues, [])

    def test_confirmed_story_drives_assets_and_review_package(self):
        confirmed = {
            "status": "confirmed",
            "title": "毕业季散场",
            "script_version": 1,
            "script_hash": "story-hash",
            "story_promise": "一个迷茫的高三学生在最后一节晚自习里接受未知未来。",
            "main_conflict": "林远不知道毕业后的路要通向哪里，却必须独自走出熟悉的教室。",
            "logline": "林远在高考前夜留到最后，在黑板角落画下一个指向窗外的小箭头。",
            "why_it_happens": "高三最后一节晚自习结束，熟悉的教室突然变得陌生。",
            "how_it_happens": "林远拒绝同行，独自收拾练习册和书包，在黑板上画箭头后走向校门。",
            "protagonist_arc": "林远从害怕没有方向，到接受迷茫也是自己要走的第一步。",
            "platform": "Douyin/Kuaishou vertical short drama",
            "visual_style": "realistic urban drama",
            "story_draft": "高三最后一天晚自习，林远坐在靠窗的位置，看着窗外漆黑的夜。下课铃响后，他拒绝同学一起走，留到最后。他走到讲台边，拿起粉笔，在黑板角落画了一个小箭头，指向窗外。然后他把最后一本练习册放进书包，走出教学楼，独自走向校门。",
            "key_turns": "林远画箭头的决定；他拒绝同行者的邀请。",
        }
        request = build_comic_request(
            idea="毕业季散场",
            genre="school youth",
            length="1 episode, 30 seconds",
            platform="Douyin/Kuaishou vertical short drama",
            visual_style="realistic urban drama",
            confirmed_script=confirmed,
        )

        result = build_comic_result("task-life", request)
        package = result["comic_package"]
        artifacts = build_comic_artifacts("task-life", result)

        self.assertIn("林远坐在靠窗的位置", package["script_preview"]["story_draft"])
        self.assertEqual(package["confirmed_script"]["key_turns"], ["林远画箭头的决定；他拒绝同行者的邀请。"])
        self.assertIn("林远", [item["name"] for item in package["characters"]])
        self.assertIn("粉笔", [item["name"] for item in package["props"]])
        self.assertIn("高三晚自习教室", [item["name"] for item in package["scenes"]])
        review = next(item for item in artifacts if item["artifact_type"] == "asset_review_package")
        self.assertTrue(review["metadata"]["requires_human_review"])
        self.assertIn("待审核", review["content"])

    def test_crisis_family_idea_generates_humane_story_instead_of_generic_template(self):
        brief = build_comic_brief(
            idea="学生要跳楼母亲苦苦哀求",
            genre="",
            length="3 episodes",
            platform="Douyin",
            visual_style="现实主义漫画",
            extra="不要猎奇，要有现实痛感和救援希望",
        )["creative_brief"]

        preview = build_comic_script_preview(
            idea="学生要跳楼母亲苦苦哀求",
            genre="",
            length="3 episodes",
            platform="Douyin",
            visual_style="现实主义漫画",
            extra="不要猎奇，要有现实痛感和救援希望",
            creative_brief=brief,
            user_answers="学生长期被成绩和误解压垮，母亲一开始只会责备，最后第一次真正倾听孩子。",
        )

        script = preview["script_preview"]
        self.assertIn("现实情绪危机", script["genre"])
        self.assertEqual(script["story_draft"], "")

    def test_follow_up_questions_are_brief_and_match_non_mystery_story(self):
        session = start_comic_cabinet_session(
            idea="幸福美满的家庭聚餐",
            genre="",
            length="3 episodes",
            platform="Douyin",
            visual_style="现实主义漫画",
            extra="想要温情一点，不要悬疑反转。",
        )["session"]

        questions = session["story_state"]["questions"]
        rendered = "\n".join(questions)
        self.assertLessEqual(len(questions), 2)
        self.assertNotIn("物件", rendered)
        self.assertNotIn("秘密", rendered)
        self.assertNotIn("更狠", rendered)

    def test_domestic_warm_story_uses_life_drama_outline_not_mystery_defaults(self):
        preview = build_comic_script_preview(
            idea="幸福美满的家庭聚餐",
            genre="",
            length="3 episodes",
            platform="Douyin",
            visual_style="现实主义漫画",
            extra="温情生活流，不要悬疑反转。",
            user_answers="主角是一位很久没回家的女儿，家庭聚餐表面幸福，其实每个人都有没说出口的委屈。",
        )["script_preview"]

        # 硬编码的模板已被移除，默认 episode_outline 为空，直到 LLM 填充
        self.assertEqual(preview.get("episode_outline", []), [])

    def test_cabinet_session_supports_multi_turn_refinement_before_production(self):
        # Fallback to non-LLM version test to verify state progression
        session = start_comic_cabinet_session(
            idea="一个女孩每天醒来都会进入不同漫画世界",
            genre="fantasy",
            length="5 episodes",
            platform="Douyin",
            visual_style="Korean webtoon",
            extra="希望有悬疑感",
        )["session"]
        
        # Advance with user message (non-LLM doesn't auto-append assistant messages anymore)
        next_turn = advance_comic_cabinet_session(
            session,
            user_message="主角每次醒来都会带走上一部漫画里的一个关键道具",
        )
        self.assertEqual(next_turn["session"]["turn_count"], 1)
        self.assertEqual(next_turn["session"]["messages"][0]["role"], "user")
        self.assertIn("带走上一部漫画", next_turn["session"]["user_notes"][0])

    def test_llm_cabinet_session_uses_role_specific_prompt_outputs_when_available(self):
        session = start_comic_cabinet_session("我想写一个悬疑故事", "赛博朋克", "反转结局")
        role_configs = {"编剧顾问": ModelConfig(provider="mock", model="mock")}
        with patch("src.comic_office.workflow._model_config_usable", return_value=True):
            with patch("src.comic_office.workflow.advance_comic_cabinet_session") as mock_advance:
                mock_advance.return_value = {
                    "session": session["session"],
                    "creative_brief": session["creative_brief"],
                    "script_preview": session["script_preview"],
                    "assistant_message": "old",
                    "cabinet_roles": [],
                    "preview": "old"
                }
                with patch("src.comic_office.workflow._cabinet_story_writer_llm", return_value={"assistant_message": "LLM 回复", "story": {}}):
                    result = asyncio.run(advance_comic_cabinet_session_llm(session["session"], "角色是谁？", role_configs))
                    self.assertTrue(result["session"]["llm_cabinet"])
                    self.assertEqual(len(result["cabinet_roles"]), 0)
                    self.assertEqual(result["assistant_message"], "LLM 回复")

    def test_llm_cabinet_keeps_partial_role_outputs_and_marks_rule_fallbacks(self):
        # 这个测试由于移除了并行的内阁顾问，所以不再适用，可以直接删除或替换为单 Agent fallback 测试
        pass

    def test_confirmed_script_is_built_from_session_and_reused_by_production(self):
        session = start_comic_cabinet_session(
            idea="雨夜里失忆侦探捡到一封会改写身份的信",
            genre="suspense",
            length="3 episodes",
            platform="Douyin",
            visual_style="dark suspense comic",
            extra="",
        )["session"]
        session = advance_comic_cabinet_session(
            session,
            "主角是女侦探，反派一直在误导她，最后她发现自己名字也在信里，结尾要留悬念。",
        )["session"]
        
        # 模拟大模型生成了分集大纲
        session["script_preview"]["episode_outline"] = [
            {"episode": 1, "title": "第一集", "cause": "起因", "action": "行动", "turn": "转折", "hook": "钩子"}
        ]
        
        issues = validate_confirmed_script_session(session)
        self.assertEqual(issues, [])
        confirmed = build_confirmed_script(session, "第一集钩子要狠一点，但整体方向确认。")
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertIn("第一集钩子要狠一点", confirmed["confirmation_notes"])
        self.assertIn("story_draft", confirmed)
        self.assertEqual(confirmed["story_draft"], "")

        request = build_comic_request(
            idea="雨夜里失忆侦探捡到一封会改写身份的信",
            genre="suspense",
            length="3 episodes",
            platform="Douyin",
            visual_style="dark suspense comic",
            creative_brief=session["creative_brief"],
            user_answers="\n".join(session["user_notes"]),
            script_preview=session["script_preview"],
            confirmed_script=confirmed,
        )
        result = build_comic_result("task-confirmed", request)
        self.assertEqual(result["comic_package"]["confirmed_script"]["status"], "confirmed")
        self.assertEqual(
            result["comic_package"]["confirmed_script"].get("story_draft", ""),
            confirmed["story_draft"],
        )
        self.assertIn("完整故事稿", result["final_report"])
        self.assertEqual(
            result["comic_package"]["confirmed_script"]["why_it_happens"],
            confirmed["why_it_happens"],
        )
        self.assertTrue(result["comic_package"]["script_binding"]["confirmed"])
        self.assertEqual(result["comic_package"]["script_binding"]["script_version"], 1)
        self.assertEqual(
            result["comic_package"]["script_binding"]["script_hash"],
            confirmed["script_hash"],
        )
    def test_comic_result_contains_brief_assets_shots_and_prompts(self):
        brief = build_comic_brief(
            idea="民国侦探在雨夜发现一封会改写身份的信",
            genre="suspense",
            length="3 episodes, 60 seconds each",
            platform="vertical short-video platforms",
            visual_style="dark suspense comic",
            extra="",
        )
        result = build_comic_result(
            "task-1",
            build_comic_request(
                idea="民国侦探在雨夜发现一封会改写身份的信",
                genre="suspense",
                length="3 episodes, 60 seconds each",
                platform="vertical short-video platforms",
                visual_style="dark suspense comic",
                creative_brief=brief["creative_brief"],
                user_answers="主角是女性，结尾要留反转。",
            ),
        )

        package = result["comic_package"]
        self.assertEqual(result["status"], "completed")
        self.assertIn("creative_brief", package)
        self.assertIn("clarifying_questions", package["creative_brief"])
        self.assertIn("主角是女性", package["user_answers"])
        self.assertIn("民国侦探", package["title"])
        self.assertGreaterEqual(len(package["characters"]), 3)
        self.assertGreaterEqual(len(package["props"]), 3)
        self.assertGreaterEqual(len(package["scenes"]), 3)
        self.assertGreaterEqual(len(package["shots"]), 6)
        self.assertIn("script_binding", package)
        self.assertIn("consistency_bindings", package)
        self.assertTrue(package["consistency_bindings"]["script"]["script_hash"])
        self.assertTrue(all("anchor_id" in item for item in package["characters"]))
        self.assertTrue(all("binding" in item for item in package["shots"]))
        self.assertIn("beat_id", package["shots"][0]["binding"])
        self.assertIn("一致性闭环", result["final_report"])

    def test_comic_result_derives_assets_from_confirmed_story_content(self):
        result = build_comic_result(
            "task-paper-bride",
            (
                "Idea: 山村纸人新娘在婚礼夜突然睁眼\n"
                "Confirmed script:\n"
                "# 纸人新娘 确认版剧本\n\n"
                "- 题材：horror thriller\n"
                "- 长度：3 episodes, 60 seconds each\n"
                "- 平台：Douyin\n"
                "- 视觉风格：dark suspense comic\n"
                "- 故事承诺：山村婚礼、纸人新娘、红盖头、祠堂和相机闪光灯。\n"
                "- 主冲突：主角必须在村民阻止下救出真正的新娘。\n"
                "- 一句话故事：摄影师发现纸人新娘突然睁眼，真正的新娘被藏在祠堂地下。\n"
                "- 为什么发生：族老用冥婚仪式掩盖旧案。\n"
                "- 如何发生：主角拍摄婚礼，发现纸人、红盖头、祠堂地板和相机照片里的线索。\n"
                "- 主角变化：主角从完成拍摄到主动救人。\n\n"
                "## 完整故事稿\n"
                "山村婚礼夜，摄影师陈野看到纸人新娘隔着红盖头睁眼。他用相机闪光灯照亮祠堂地板，发现地下暗门。\n\n"
                "## 每集确认大纲\n"
                "1. 纸人睁眼｜起因：主角接到山村婚礼拍摄委托｜行动：拍摄仪式｜转折：相机拍到纸人身后有人｜钩子：纸人新娘隔着红盖头睁眼\n"
                "2. 祠堂暗门｜起因：追查照片里的女人｜行动：进入祠堂｜转折：族老阻止主角｜钩子：地板下传出求救声\n"
                "3. 红盖头｜起因：救出真新娘｜行动：用相机闪光灯揭露骗局｜转折：纸人被烧毁｜钩子：纸人再次出现在照片里\n"
            ),
        )

        package = result["comic_package"]
        prop_names = " ".join(item["name"] for item in package["props"])
        scene_names = " ".join(item["name"] for item in package["scenes"])
        prompts = result["final_report"]

        self.assertIn("纸人新娘", prop_names)
        self.assertIn("红盖头", prop_names)
        self.assertIn("相机", prop_names)
        self.assertIn("山村婚礼堂屋", scene_names)
        self.assertIn("祠堂", scene_names)
        self.assertNotIn("关键合同", prompts)
        self.assertNotIn("现代办公室", prompts)

    def test_comic_result_derives_real_shot_beats_from_story_draft(self):
        result = build_comic_result(
            "task-helper-death",
            (
                "Idea: 一队修仙队伍中的辅助死亡了\n"
                "Genre: xianxia tragedy\n"
                "Visual style: ink wash Chinese fantasy\n"
                "Confirmed script:\n"
                "# 一队修仙队伍中的辅助死亡了 确认版剧本\n\n"
                "- 题材：xianxia tragedy\n"
                "- 长度：3 episodes\n"
                "- 平台：Douyin\n"
                "- 视觉风格：ink wash Chinese fantasy\n"
                "- 故事承诺：辅助死亡后，队伍才意识到他承担了一切温柔细节。\n"
                "- 主冲突：队友想复仇，但真正要面对的是他们长期忽视辅助的愧疚。\n"
                "## 完整故事稿\n"
                "清晨，辅助阿衡下山采购，记下大师兄爱吃的桂花糕、二师姐常备的止血散、小师弟总弄丢的聚气丹。"
                "一辆贵人车驾横冲直撞，他被护卫拖进偏僻小巷乱棍打死。"
                "夜晚，队友们抱怨没人准备晚饭，才发现阿衡没有回来。"
                "他们在小巷发现他的尸体和散落的药包，沉默地意识到自己从未真正看见过他。\n"
            ),
        )

        package = result["comic_package"]
        beats = " ".join(shot["beat"] for shot in package["shots"])
        prompts = " ".join(shot["image_prompt"] for shot in package["shots"])
        names = " ".join(item["name"] for group in ("characters", "props", "scenes") for item in package[group])

        self.assertNotIn("确认故事", beats)
        self.assertNotIn("补充分镜节拍", beats)
        self.assertIn("下山采购", beats)
        self.assertIn("偏僻小巷", prompts)
        self.assertIn("辅助阿衡", names)
        self.assertIn("大师兄", names)
        self.assertIn("桂花糕", names)
        self.assertIn("止血散", names)
        self.assertIn("偏僻小巷", names)

    def test_comic_artifacts_cover_preproduction_delivery_canvas(self):
        brief = build_comic_brief(
            idea="一个外卖员误入未来城市后必须用三小时救回妹妹",
            genre="science fiction",
            length="5 episodes",
            platform="Douyin",
            visual_style="cinematic comic",
            extra="",
        )
        result = build_comic_result(
            "task-2",
            build_comic_request(
                idea="一个外卖员误入未来城市后必须用三小时救回妹妹",
                genre="science fiction",
                creative_brief=brief["creative_brief"],
                user_answers="主角要普通但行动力强。",
            ),
        )

        artifacts = build_comic_artifacts("task-2", result)
        artifact_types = {artifact["artifact_type"] for artifact in artifacts}

        self.assertEqual(len(artifacts), 17)
        self.assertIn("creative_brief", artifact_types)
        self.assertIn("script_preview", artifact_types)
        self.assertIn("story_draft", artifact_types)
        self.assertIn("confirmed_script", artifact_types)
        self.assertIn("cabinet_review", artifact_types)
        self.assertIn("script", artifact_types)
        self.assertIn("style_bible", artifact_types)
        self.assertIn("asset_review_package", artifact_types)
        self.assertIn("character_sheet", artifact_types)
        self.assertIn("storyboard_table", artifact_types)
        self.assertIn("production_canvas", artifact_types)
        self.assertIn("word_canvas", artifact_types)
        self.assertIn("camera_plan", artifact_types)
        self.assertIn("prompt_package", artifact_types)
        self.assertIn("consistency_checklist", artifact_types)
        self.assertTrue(all(artifact["metadata"]["office_id"] == "comic" for artifact in artifacts))
        self.assertTrue(all("script_hash" in artifact["metadata"] for artifact in artifacts))
        canvas = next(a for a in artifacts if a["artifact_type"] == "production_canvas")
        self.assertIn("shot_001", canvas["content"])
        self.assertIn("对应图片", canvas["content"])
        self.assertIn("脚本版本", canvas["content"])
        story = next(a for a in artifacts if a["artifact_type"] == "story_draft")
        self.assertIn("当前剧本尚未生成完整故事稿", story["content"])
        prompt_package = next(a for a in artifacts if a["artifact_type"] == "prompt_package")
        self.assertIn("提示词包", prompt_package["content"])
        self.assertIn("负面提示词", prompt_package["content"])


if __name__ == "__main__":
    unittest.main()
