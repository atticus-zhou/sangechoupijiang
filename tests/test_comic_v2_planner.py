import unittest

from src.llm.providers import LLMResponse, ModelConfig


STORY = "林昭发现月灯燃烧记忆。她进入月塔，最终熄灭月塔，让全城重新想起亲人。"


def valid_planner_payload():
    return {
        "title": "借月人",
        "genre": "古风幻想",
        "theme": "记忆与光明的代价",
        "protagonist_goal": "熄灭月塔",
        "main_conflict": "月塔依靠记忆维持光明",
        "causal_chain": ["发现真相", "进入月塔", "熄灭月塔"],
        "ending": "林昭最终熄灭月塔",
        "episodes": [
            {
                "episode": 1,
                "summary": "发现真相并作出选择",
                "evidence_quote": "林昭发现月灯燃烧记忆",
            }
        ],
        "must_keep": ["林昭熄灭月塔"],
        "must_avoid": ["改写结局"],
        "visual": {
            "medium": "电影级国风厚涂动画",
            "era": "架空古代",
            "aspect_ratio": "9:16",
            "palette": ["靛青", "银白", "暗朱红"],
            "lighting": "冷月光与暖灯火对照",
            "camera_language": "克制稳定",
            "character_rules": ["脸型与服装主色固定"],
            "costume_rules": ["古代窄袖长袍"],
            "prop_rules": ["裂纹位置固定"],
            "architecture_rules": ["木石结构"],
            "visual_motifs": ["裂纹月灯"],
            "prohibited_elements": ["现代车辆", "可读文字"],
        },
    }


class FakePlannerProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def chat(self, messages, tools=None, tool_choice=None, response_format=None):
        self.calls.append({"messages": messages, "response_format": response_format})
        content = self.responses.pop(0)
        return LLMResponse(content=content, model="fake/planner", tokens_used=10)


class ComicV2PlannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_planner_preserves_confirmed_story_verbatim(self):
        from src.comic_office.v2.planner import plan_contract

        provider = FakePlannerProvider([__import__("json").dumps(valid_planner_payload(), ensure_ascii=False)])
        bundle = await plan_contract(
            STORY,
            ModelConfig(provider="openai", model="fake", api_key="test"),
            llm=provider,
        )

        self.assertEqual(bundle.creative.source_story, STORY)
        self.assertEqual(bundle.creative.title, "借月人")
        sent_prompt = provider.calls[0]["messages"][-1].content
        self.assertIn(STORY, sent_prompt)
        self.assertIn("不得改写", provider.calls[0]["messages"][0].content)

    async def test_planner_retries_malformed_json_then_accepts_valid_contract(self):
        from src.comic_office.v2.planner import plan_contract

        provider = FakePlannerProvider([
            "这不是 JSON",
            __import__("json").dumps(valid_planner_payload(), ensure_ascii=False),
        ])
        bundle = await plan_contract(
            STORY,
            ModelConfig(provider="openai", model="fake", api_key="test"),
            llm=provider,
        )

        self.assertEqual(bundle.visual.era, "架空古代")
        self.assertEqual(len(provider.calls), 2)

    async def test_planner_exposes_api_error_instead_of_using_template_fallback(self):
        from src.comic_office.v2.planner import PlannerError, plan_contract

        provider = FakePlannerProvider(["[API错误] invalid key", "[API错误] invalid key"])
        with self.assertRaisesRegex(PlannerError, "模型调用失败"):
            await plan_contract(
                STORY,
                ModelConfig(provider="openai", model="fake", api_key="bad"),
                llm=provider,
            )

    async def test_planner_rejects_unconfigured_online_model(self):
        from src.comic_office.v2.planner import PlannerError, plan_contract

        with self.assertRaisesRegex(PlannerError, "未配置"):
            await plan_contract(
                STORY,
                ModelConfig(provider="deepseek", model="deepseek-chat", api_key=""),
            )

    async def test_visual_revision_preserves_creative_contract_and_increments_style_version(self):
        from src.comic_office.v2.contracts import build_contract_bundle
        from src.comic_office.v2.planner import revise_visual_bible

        first = build_contract_bundle(STORY, valid_planner_payload())
        revised_visual = dict(valid_planner_payload()["visual"])
        revised_visual["lighting"] = "黎明冷雾中的银蓝顶光"
        provider = FakePlannerProvider([
            __import__("json").dumps({"visual": revised_visual}, ensure_ascii=False)
        ])

        second = await revise_visual_bible(
            first.to_dict(),
            "整体改成黎明冷雾，不要暖灯火",
            ModelConfig(provider="openai", model="fake", api_key="test"),
            llm=provider,
        )

        self.assertEqual(second.creative, first.creative)
        self.assertEqual(second.visual.style_version, 2)
        self.assertEqual(second.visual.lighting, "黎明冷雾中的银蓝顶光")

    async def test_visual_revision_rejects_noop_model_response(self):
        from src.comic_office.v2.contracts import build_contract_bundle
        from src.comic_office.v2.planner import PlannerError, revise_visual_bible

        first = build_contract_bundle(STORY, valid_planner_payload())
        provider = FakePlannerProvider([
            __import__("json").dumps({"visual": valid_planner_payload()["visual"]}, ensure_ascii=False),
            __import__("json").dumps({"visual": valid_planner_payload()["visual"]}, ensure_ascii=False),
        ])

        with self.assertRaisesRegex(PlannerError, "没有落实"):
            await revise_visual_bible(
                first.to_dict(),
                "改成黎明冷雾",
                ModelConfig(provider="openai", model="fake", api_key="test"),
                llm=provider,
            )


if __name__ == "__main__":
    unittest.main()
