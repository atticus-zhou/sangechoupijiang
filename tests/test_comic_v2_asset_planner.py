import json
import unittest

from src.comic_office.v2.contracts import build_contract_bundle
from src.llm.providers import LLMResponse, ModelConfig


STORY = (
    "林昭在月税司登记月灯，发现裂纹月灯里出现亡兄林晦的影子。"
    "她带着裂纹月灯找到修灯匠顾砚，并在修灯铺查到月税簿。"
    "两人前往中央月塔，林昭最终熄灭月塔。"
)


def contract_bundle():
    return build_contract_bundle(STORY, {
        "title": "借月人",
        "genre": "古风幻想",
        "theme": "记忆与光明的代价",
        "protagonist_goal": "熄灭月塔",
        "main_conflict": "月塔燃烧记忆维持城市光明",
        "causal_chain": ["发现影子", "查到月税簿", "熄灭月塔"],
        "ending": "林昭最终熄灭月塔",
        "episodes": [{"episode": 1, "summary": "追查真相", "evidence_quote": "林昭在月税司登记月灯"}],
        "visual": {
            "medium": "电影级国风厚涂动画",
            "era": "架空古代",
            "aspect_ratio": "9:16",
            "palette": ["靛青", "银白", "暗朱红"],
            "lighting": "冷月光与暖灯火对照",
            "camera_language": "克制稳定",
            "character_rules": ["脸型固定"],
            "costume_rules": ["古代服装"],
            "prop_rules": ["裂纹位置固定"],
            "architecture_rules": ["木石结构"],
            "visual_motifs": ["裂纹月灯"],
            "prohibited_elements": ["现代车辆"],
        },
    })


def valid_assets():
    return [
        {
            "asset_type": "character",
            "name": "林昭",
            "evidence_quote": "林昭在月税司登记月灯",
            "scene_ids": ["scene_01", "scene_03"],
            "story_purpose": "主角，发现并终结月税真相",
            "visual_locks": ["靛青窄袖长袍", "固定发髻"],
            "allowed_changes": ["表情", "姿势"],
        },
        {
            "asset_type": "prop",
            "name": "裂纹月灯",
            "evidence_quote": "裂纹月灯",
            "scene_ids": ["scene_01", "scene_02", "scene_03"],
            "story_purpose": "贯穿真相与结局的核心证物",
            "visual_locks": ["裂纹位置固定"],
            "allowed_changes": ["发光强度"],
        },
        {
            "asset_type": "scene",
            "name": "月税司",
            "evidence_quote": "月税司",
            "scene_ids": ["scene_01"],
            "story_purpose": "异常最初发生的制度空间",
            "visual_locks": ["中央长柜", "悬吊月灯"],
            "allowed_changes": ["群众数量"],
        },
    ]


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def chat(self, messages, tools=None, tool_choice=None, response_format=None):
        self.calls.append(messages)
        return LLMResponse(content=self.responses.pop(0), model="fake/model", tokens_used=10)


class ComicV2AssetPlannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_agent_planning_returns_evidence_backed_manifest(self):
        from src.comic_office.v2.asset_planner import plan_asset_manifest

        planner = FakeProvider([json.dumps({"assets": valid_assets()}, ensure_ascii=False)])
        reviewer = FakeProvider([json.dumps({"status": "approved", "issues": []}, ensure_ascii=False)])
        config = ModelConfig(provider="openai", model="fake", api_key="test")

        manifest = await plan_asset_manifest(
            contract_bundle(),
            config,
            config,
            planner_llm=planner,
            reviewer_llm=reviewer,
        )

        self.assertEqual(manifest.review_status, "awaiting_user_review")
        self.assertEqual({item.asset_type for item in manifest.items}, {"character", "prop", "scene"})
        self.assertIn(STORY, planner.calls[0][-1].content)
        self.assertIn("人物必须是会行动", planner.calls[0][0].content)
        self.assertIn("裂纹月灯", reviewer.calls[0][-1].content)

    async def test_reviewer_rejection_is_fed_back_to_second_planning_attempt(self):
        from src.comic_office.v2.asset_planner import plan_asset_manifest

        first = valid_assets()[:-1]
        planner = FakeProvider([
            json.dumps({"assets": first}, ensure_ascii=False),
            json.dumps({"assets": valid_assets()}, ensure_ascii=False),
        ])
        reviewer = FakeProvider([
            json.dumps({"status": "rejected", "issues": ["缺少故事明确出现的月税司场景"]}, ensure_ascii=False),
            json.dumps({"status": "approved", "issues": []}, ensure_ascii=False),
        ])
        config = ModelConfig(provider="openai", model="fake", api_key="test")

        manifest = await plan_asset_manifest(
            contract_bundle(),
            config,
            config,
            planner_llm=planner,
            reviewer_llm=reviewer,
        )

        self.assertIn("月税司", [item.name for item in manifest.items])
        self.assertIn("缺少故事明确出现的月税司场景", planner.calls[1][-1].content)

    async def test_revision_replaces_full_manifest_and_rejects_noop(self):
        from src.comic_office.v2.asset_manifest import build_asset_manifest
        from src.comic_office.v2.asset_planner import AssetPlanningError, plan_asset_manifest

        current = build_asset_manifest(contract_bundle(), valid_assets())
        planner = FakeProvider([
            json.dumps({"assets": valid_assets()}, ensure_ascii=False),
            json.dumps({"assets": valid_assets()}, ensure_ascii=False),
        ])
        reviewer = FakeProvider([])
        config = ModelConfig(provider="openai", model="fake", api_key="test")

        with self.assertRaisesRegex(AssetPlanningError, "没有产生变化"):
            await plan_asset_manifest(
                contract_bundle(),
                config,
                config,
                revision_request="补充缺少的道具",
                previous_manifest=current,
                planner_llm=planner,
                reviewer_llm=reviewer,
            )


if __name__ == "__main__":
    unittest.main()
