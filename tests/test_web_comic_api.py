import sqlite3
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.llm.providers import LLMResponse, LiteLLMProvider, ModelConfig
from src.web.app import _comic_image_specs, app, config_manager


class WebComicApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.created_workspaces = []

    def tearDown(self):
        if not self.created_workspaces:
            return
        conn = sqlite3.connect("user_data/config.db")
        for workspace_id in self.created_workspaces:
            conn.execute("DELETE FROM artifacts WHERE workspace_id=?", (workspace_id,))
            conn.execute("DELETE FROM workspaces WHERE workspace_id=?", (workspace_id,))
            conn.execute("DELETE FROM config_store WHERE key=?", (f"comic_cabinet_session:{workspace_id}",))
        conn.commit()
        conn.close()
        for workspace_id in self.created_workspaces:
            shutil.rmtree(Path("output") / "workspaces" / workspace_id, ignore_errors=True)

    def test_comic_cabinet_turn_creates_and_persists_session(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "一个女孩每天醒来都会进入不同漫画世界",
            "genre": "fantasy",
            "length": "5 episodes",
            "platform": "Douyin",
            "visual_style": "Korean webtoon",
            "extra": "希望有悬疑感",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        self.assertIn(body["status"], {"needs_more_discussion", "script_ready"})
        self.assertIn("session", body)
        self.assertIn("creative_brief", body)
        self.assertIn("script_preview", body)
        self.assertEqual(len(body["cabinet_roles"]), 0)

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "一个女孩每天醒来都会进入不同漫画世界",
            "genre": "fantasy",
            "length": "5 episodes",
            "platform": "Douyin",
            "visual_style": "Korean webtoon",
            "extra": "希望有悬疑感",
            "user_message": "主角是普通女大学生，每次穿越都会失去一点现实记忆，最后发现这些世界是她为了逃避妹妹去世创造的。",
            "session": body["session"],
        })
        self.assertEqual(response.status_code, 200)
        second = response.json()
        self.assertIn("女大学生", second["script_preview"]["user_answers"])

        saved = self.client.get(f"/api/comic/cabinet/{workspace_id}")
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["status"], "ok")
        self.assertIn("女大学生", saved.json()["session"]["script_preview"]["user_answers"])

    def test_comic_production_cabinet_creates_isolated_workspace(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "office_id": "comic_production",
            "idea": "A fallen healer in a cultivation team becomes the key to the revenge story.",
            "genre": "fantasy costume drama",
            "length": "5 episodes",
            "platform": "vertical short drama",
            "visual_style": "cinematic comic",
            "extra": "Need a production-ready package.",
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        workspace = config_manager.get_workspace(workspace_id)
        self.assertEqual(workspace["office_id"], "comic_production")
        self.assertEqual(body["office_id"], "comic_production")
        saved = self.client.get(f"/api/comic/cabinet/{workspace_id}")
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["office_id"], "comic_production")

    def test_comic_cabinet_defaults_to_production_office(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "A city clerk discovers every elevator opens to a different ending.",
            "genre": "urban fantasy",
            "length": "3 episodes",
            "platform": "vertical short drama",
            "visual_style": "cinematic comic",
            "extra": "",
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        self.assertEqual(body["office_id"], "comic_production")
        self.assertEqual(config_manager.get_workspace(workspace_id)["office_id"], "comic_production")

    def test_comic_production_task_uses_its_own_office_scope(self):
        workspace_id = f"ws_prod_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Production isolation test",
            brief="A confirmed story should start in the production office.",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_confirmed_script",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="confirmed_script",
            title="Confirmed script",
            content="Confirmed script hash: prod_scope_test",
            metadata={"office_id": "comic_production", "script_hash": "prod_scope_test", "confirmed": True},
            created_by="shangshu",
        )

        class DummyTask:
            def add_done_callback(self, callback):
                return None

        def fake_create_task(coro):
            coro.close()
            return DummyTask()

        with patch("src.web.app._schedule_background_task", side_effect=fake_create_task):
            started = self.client.post("/api/tasks", json={
                "user_request": "Idea: production isolation",
                "office_id": "comic_production",
                "workspace_id": workspace_id,
            })

        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["office_id"], "comic_production")
        run = config_manager.get_task_run(started.json()["task_id"])
        self.assertIn("prod_scope_test", run["user_request"])
        conn = sqlite3.connect("user_data/config.db")
        conn.execute("DELETE FROM task_runs WHERE task_id=?", (started.json()["task_id"],))
        conn.execute("DELETE FROM task_events WHERE task_id=?", (started.json()["task_id"],))
        conn.commit()
        conn.close()

    def test_comic_production_task_blocks_after_asset_review_when_image_models_are_missing(self):
        workspace_id = f"ws_prod_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Production image model guard",
            brief="A confirmed story should not start without image models.",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_confirmed_script",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="confirmed_script",
            title="Confirmed script",
            content="Confirmed script hash: prod_guard_test",
            metadata={"office_id": "comic_production", "script_hash": "prod_guard_test", "confirmed": True},
            created_by="shangshu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_asset_review_package",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="asset_review_package",
            title="Asset review package",
            content="Assets approved for image generation.",
            metadata={"office_id": "comic_production", "script_hash": "prod_guard_test", "review_status": "approved", "requires_human_review": True},
            created_by="menxia",
        )
        original_config = config_manager.load_yaml()
        modified_config = config_manager.load_yaml()
        modified_config.setdefault("office_models", {})["comic_production"] = {
            "gongbu": {"provider": "dashscope", "model": "qwen-vl-max", "api_key": "vision-key"},
            "bingbu": {"provider": "deepseek", "model": "deepseek-chat", "api_key": "chat-key"},
        }
        config_manager.save_yaml(modified_config)
        try:
            started = self.client.post("/api/tasks", json={
                "user_request": "Idea: production guard",
                "office_id": "comic_production",
                "workspace_id": workspace_id,
            })
        finally:
            config_manager.save_yaml(original_config)

        self.assertEqual(started.status_code, 400)
        self.assertIn("工部需要生图模型", started.json()["detail"])
        self.assertIn("兵部需要生图模型", started.json()["detail"])

    def test_asset_review_decision_is_bound_to_current_confirmed_script(self):
        workspace_id = f"ws_review_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Asset review decision",
            brief="Asset review should be explicit and script-bound.",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_confirmed_script",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="confirmed_script",
            title="Confirmed script",
            content="Confirmed script hash: current_hash",
            metadata={"office_id": "comic_production", "script_hash": "current_hash", "script_version": 2, "confirmed": True},
            created_by="shangshu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_asset_review_package",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="asset_review_package",
            title="Asset review package",
            content="人物、道具、场景拆解待审核。",
            metadata={"office_id": "comic_production", "script_hash": "current_hash", "review_status": "pending", "requires_human_review": True},
            created_by="menxia",
        )

        response = self.client.post(
            f"/api/workspaces/{workspace_id}/comic/asset-review/decision",
            json={"status": "approved", "reviewer_notes": "人物和场景拆解可以进入生产。"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "approved")
        artifact = config_manager.get_artifact(f"art_{workspace_id}_asset_review_package")
        metadata = artifact["metadata"]
        self.assertEqual(metadata["review_status"], "approved")
        self.assertEqual(metadata["script_hash"], "current_hash")
        self.assertEqual(metadata["script_version"], 2)
        self.assertEqual(metadata["reviewer_notes"], "人物和场景拆解可以进入生产。")
        self.assertTrue(metadata["reviewed_at"])

    def test_old_asset_review_approval_cannot_unlock_new_confirmed_script(self):
        workspace_id = f"ws_old_review_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="Old review must not unlock",
            brief="Old approved asset review should not unlock a new script hash.",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_confirmed_script",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="confirmed_script",
            title="Confirmed script",
            content="Confirmed script hash: new_hash",
            metadata={"office_id": "comic_production", "script_hash": "new_hash", "script_version": 2, "confirmed": True},
            created_by="shangshu",
        )
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_asset_review_package",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="asset_review_package",
            title="Old asset review package",
            content="Old assets approved.",
            metadata={"office_id": "comic_production", "script_hash": "old_hash", "review_status": "approved", "requires_human_review": True},
            created_by="menxia",
        )

        class DummyTask:
            def add_done_callback(self, callback):
                return None

        def fake_create_task(coro):
            coro.close()
            return DummyTask()

        with patch("src.web.app._schedule_background_task", side_effect=fake_create_task):
            started = self.client.post("/api/tasks", json={
                "user_request": "Idea: new story",
                "office_id": "comic_production",
                "workspace_id": workspace_id,
            })

        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["office_id"], "comic_production")

    def test_history_exposes_comic_word_canvas_download(self):
        task_id = f"hist_{str(uuid.uuid4())[:8]}"
        workspace_id = f"ws_hist_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic",
            title="历史下载测试",
            brief="测试历史页下载 Word 画布",
        )
        config_manager.save_task_record(
            task_id,
            "生成历史下载测试制片包",
            "",
            "completed",
            {"final_report": "完整制片包已经生成。"},
        )
        config_manager.create_task_run(task_id, "生成历史下载测试制片包", "")
        config_manager.append_task_event(
            task_id=task_id,
            event_type="task_created",
            status="queued",
            summary="Task accepted by Web API",
            payload={"office_id": "comic", "workspace_id": workspace_id},
        )
        config_manager.update_task_run(
            task_id,
            "completed",
            current_phase="completed",
            result={"final_report": "完整制片包已经生成。"},
            completed=True,
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_word",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="word_canvas",
            title="历史下载测试 - Word制片画布",
            uri=f"/api/workspaces/{workspace_id}/files/delivery/test.docx",
            content="# Word制片画布",
            metadata={"office_id": "comic"},
            created_by="gongbu",
        )
        try:
            response = self.client.get("/api/tasks/history?limit=20")
            self.assertEqual(response.status_code, 200)
            row = next(item for item in response.json()["history"] if item["task_id"] == task_id)
            self.assertEqual(row["workspace_id"], workspace_id)
            self.assertEqual(row["artifact_count"], 1)
            self.assertTrue(row["word_canvas_uri"].endswith("/test.docx"))
            self.assertEqual(row["workspace_export_uri"], f"/api/workspaces/{workspace_id}/export")
        finally:
            conn = sqlite3.connect("user_data/config.db")
            conn.execute("DELETE FROM task_history WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_runs WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_events WHERE task_id=?", (task_id,))
            conn.commit()
            conn.close()

    def test_history_exposes_comic_v2_word_canvas_download(self):
        task_id = f"hist_v2_{str(uuid.uuid4())[:8]}"
        workspace_id = f"ws_hist_v2_{str(uuid.uuid4())[:8]}"
        self.created_workspaces.append(workspace_id)
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic_production",
            title="V2 Word History",
            brief="history download",
        )
        config_manager.save_task_record(
            task_id,
            "build V2 delivery",
            "",
            "completed",
            {"final_report": "V2 delivery ready"},
        )
        config_manager.create_task_run(task_id, "build V2 delivery", "")
        config_manager.append_task_event(
            task_id=task_id,
            event_type="comic_v2_delivery_ready",
            status="completed",
            summary="V2 delivery ready",
            payload={"office_id": "comic_production", "workspace_id": workspace_id},
        )
        config_manager.update_task_run(
            task_id,
            "completed",
            current_phase="completed",
            result={"final_report": "V2 delivery ready"},
            completed=True,
        )
        config_manager.create_artifact(
            artifact_id=f"art_{task_id}_v2_word",
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="comic_v2_word_canvas",
            title="V2 Word Canvas",
            uri=f"/api/workspaces/{workspace_id}/files/delivery/v2.docx",
            content="ready",
            metadata={"office_id": "comic_production"},
            created_by="libu",
        )
        try:
            response = self.client.get("/api/tasks/history?limit=20")
            self.assertEqual(response.status_code, 200)
            row = next(item for item in response.json()["history"] if item["task_id"] == task_id)
            self.assertTrue(row["word_canvas_uri"].endswith("/v2.docx"))
            self.assertEqual(row["word_canvas_title"], "V2 Word Canvas")
        finally:
            conn = sqlite3.connect("user_data/config.db")
            conn.execute("DELETE FROM task_history WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_runs WHERE task_id=?", (task_id,))
            conn.execute("DELETE FROM task_events WHERE task_id=?", (task_id,))
            conn.commit()
            conn.close()

    def test_comic_image_specs_skip_shots_and_only_generate_base_assets(self):
        result = {
            "comic_package": {
                "script_binding": {"script_hash": "abc", "script_version": 1, "confirmed": True},
                "characters": [{"id": "char_01", "image_prompt": "人物站在山路上讲故事"}],
                "props": [{
                    "id": "prop_01",
                    "asset_specs": [
                        {"kind": "prop_turnaround", "label": "道具多角度", "prompt": "人物手持药瓶站在街道剧情现场"}
                    ],
                }],
                "scenes": [{
                    "id": "scene_01",
                    "image_prompt": "场景设定",
                    "asset_specs": [
                        {"kind": "scene_wide_establishing", "label": "场景广角建立图", "prompt": "广角空间参考"},
                        {"kind": "scene_top_down_layout", "label": "场景俯视布局图", "prompt": "俯视空间参考"},
                    ],
                }],
                "shots": [
                    {"id": f"shot_{index:03d}", "image_prompt": f"第{index}镜真实剧情画面", "binding": {}}
                    for index in range(1, 7)
                ],
            }
        }

        specs = _comic_image_specs(result, limit=12)
        storyboard_ids = [item["source_id"] for item in specs if item["kind"] == "storyboard"]
        spec_kinds = {item["kind"] for item in specs}

        self.assertEqual(storyboard_ids, [])
        self.assertIn("character", spec_kinds)
        self.assertIn("prop_turnaround", spec_kinds)
        self.assertIn("scene", spec_kinds)
        self.assertIn("scene_wide_establishing", spec_kinds)
        self.assertIn("scene_top_down_layout", spec_kinds)
        character_prompt = next(item["prompt"] for item in specs if item["kind"] == "character")
        prop_prompt = next(item["prompt"] for item in specs if item["kind"] == "prop_turnaround")
        self.assertIn("纯白或近白色干净背景", character_prompt)
        self.assertIn("禁止场景背景", character_prompt)
        self.assertIn("只生成单独角色参考", character_prompt)
        self.assertIn("纯白或近白色干净背景", prop_prompt)
        self.assertIn("禁止人物手持", prop_prompt)
        self.assertIn("只生成单独道具参考", prop_prompt)

    @patch("src.comic_office.workflow._model_config_usable", return_value=True)
    @patch("src.comic_office.workflow._cabinet_story_writer_llm", return_value={"assistant_message": "Mock LLM Message", "story": {}})
    @patch("src.comic_office.workflow.advance_comic_cabinet_session")
    @patch("src.web.app.config_manager.get_model_config")
    def test_comic_cabinet_turn_prefers_llm_role_reviews_when_models_are_available(self, mock_get_config, mock_advance, mock_writer, mock_usable):
        def fake_get_model_config(agent, office_id=""):
            return ModelConfig(provider="ollama", model=f"fake-{agent}")
        mock_get_config.side_effect = fake_get_model_config
        mock_advance.return_value = {
            "session": {"messages": [{"role": "assistant"}], "story_state": {"ready_to_produce": False}},
            "creative_brief": {},
            "script_preview": {},
            "assistant_message": "old",
            "cabinet_roles": [],
            "preview": "old"
        }

        async def fake_chat(self, messages, tools=None, tool_choice=None, response_format=None):
            return LLMResponse(
                content='{"assistant_message": "Mock LLM Message", "story": {}}',
                model="fake/provider",
                tokens_used=10,
            )

        with patch("src.web.app.config_manager.get_model_config", side_effect=fake_get_model_config):
            with patch.object(LiteLLMProvider, "chat", fake_chat):
                response = self.client.post("/api/comic/cabinet/turn", json={
                    "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
                    "genre": "suspense",
                    "length": "3 episodes",
                    "platform": "Douyin",
                    "visual_style": "dark suspense comic",
                    "extra": "第一集要有强钩子",
                })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)
        self.assertTrue(body["session"]["llm_cabinet"])
        self.assertEqual(body["assistant_message"], "Mock LLM Message")

    def test_confirm_script_endpoint_persists_confirmed_script_and_task_gate_requires_it(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
            "user_message": "主角是女侦探，反派在误导她，最后她发现自己名字也在信里，结尾要留悬念。",
            "session": body["session"],
        })
        self.assertEqual(response.status_code, 200)
        session = response.json()["session"]

        blocked = self.client.post("/api/tasks", json={
            "user_request": "Idea: 雨夜里失忆侦探捡到一封会改写身份的信",
            "office_id": "comic",
            "workspace_id": workspace_id,
        })
        self.assertEqual(blocked.status_code, 400)

        confirmed = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "session": session,
            "confirmation_notes": "确认这版，第一集钩子可以再狠一点。",
        })
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["status"], "confirmed")
        self.assertTrue(confirmed.json()["confirmed_script"]["script_hash"])
        self.assertEqual(confirmed.json()["confirmed_script"]["script_version"], 1)

        class DummyTask:
            def add_done_callback(self, callback):
                return None

        def fake_create_task(coro):
            coro.close()
            return DummyTask()

        with patch("src.web.app._schedule_background_task", side_effect=fake_create_task):
            started = self.client.post("/api/tasks", json={
                "user_request": "Idea: 雨夜里失忆侦探捡到一封会改写身份的信",
                "office_id": "comic",
                "workspace_id": workspace_id,
            })
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["workspace_id"], workspace_id)

    def test_confirm_and_start_comic_endpoint_freezes_script_and_enqueues_task(self):
        workspace_id = f"ws_test_{str(uuid.uuid4())[:8]}"
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id="comic",
            title="雨夜里失忆侦探捡到一封会改写身份的信",
            brief="一键确认并开始生产测试",
        )
        self.created_workspaces.append(workspace_id)
        session = {
            "creative_brief": {
                "core_idea": "雨夜里失忆侦探捡到一封会改写身份的信",
                "genre": "suspense",
                "length": "3 episodes",
                "platform": "Douyin",
                "visual_style": "dark suspense comic",
                "story_promise": "主角追查身份被改写的秘密",
                "main_conflict": "主角被对手误导，必须在身份被彻底改写前找到真相",
            },
            "script_preview": {
                "title": "雨夜信",
                "logline": "失忆女侦探追查一封会改写身份的信，最后发现自己的名字也在信里。",
                "why_it_happens": "对手为了隐藏真相，利用信件误导主角。",
                "how_it_happens": "主角不断追查线索，与对手冲突升级。",
                "protagonist_arc": "主角从被动怀疑自己，到主动反击对手，结尾留下悬念。",
                "episode_outline": [
                    {"episode": 1, "title": "雨夜来信", "cause": "主角捡到信", "action": "主角追查", "turn": "发现自己被误导", "hook": "最后她发现自己的名字也在信里"}
                ],
                "key_turns": ["最后她发现自己的名字也在信里"],
                "story_draft": "雨夜里，失忆女侦探捡到一封信。她追查对手，却发现自己的名字也在信里。",
            },
            "user_notes": ["主角是女侦探，对手在误导她，最后她发现自己的名字也在信里，结尾要留悬念。"],
            "cabinet_roles": [],
        }

        class DummyTask:
            def add_done_callback(self, callback):
                return None

        def fake_create_task(coro):
            coro.close()
            return DummyTask()

        with patch("src.web.app._schedule_background_task", side_effect=fake_create_task):
            started = self.client.post("/api/comic/confirm-and-start", json={
                "workspace_id": workspace_id,
                "session": session,
                "confirmation_notes": "Confirm this story and start production.",
                "user_request": "This client text should be replaced by the confirmed server script.",
            })

        self.assertEqual(started.status_code, 200)
        body = started.json()
        self.assertEqual(body["status"], "started")
        self.assertEqual(body["workspace_id"], workspace_id)
        self.assertTrue(body["task_id"])
        self.assertTrue(body["confirmed_script"]["script_hash"])
        self.assertTrue(body["artifact_id"].startswith(f"art_{workspace_id}_confirmed_script"))

        artifacts = config_manager.list_artifacts(workspace_id=workspace_id)
        self.assertTrue(any(a["artifact_type"] == "confirmed_script" for a in artifacts))
        run = config_manager.get_task_run(body["task_id"])
        self.assertIn(body["confirmed_script"]["script_hash"], run["user_request"])
        self.assertNotIn("This client text should be replaced", run["user_request"])

    def test_confirm_script_uses_saved_workspace_session_instead_of_client_session(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
            "user_message": "主角是女侦探，对手在误导她，最后她发现自己的名字也在信里，结尾要留悬念。",
            "session": body["session"],
        })
        self.assertEqual(response.status_code, 200)

        tampered_session = {
            "creative_brief": {
                "core_idea": "篡改项目",
                "genre": "suspense",
                "length": "3 episodes",
                "platform": "Douyin",
                "visual_style": "wrong style",
                "story_promise": "篡改承诺",
                "main_conflict": "主角和对手的篡改冲突",
            },
            "script_preview": {
                "title": "篡改标题",
                "logline": "篡改剧本",
                "why_it_happens": "主角被篡改事件卷入",
                "how_it_happens": "对手推动篡改",
                "protagonist_arc": "主角最后发现篡改",
                "episode_outline": [{"episode": 1, "title": "篡改", "cause": "篡改", "action": "篡改", "turn": "篡改", "hook": "最后篡改"}],
                "key_turns": ["最后篡改"],
            },
            "user_notes": ["主角、对手、最后都被篡改"],
            "cabinet_roles": [],
        }

        confirmed = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "session": tampered_session,
            "confirmation_notes": "确认真实后端会话",
        })

        self.assertEqual(confirmed.status_code, 200)
        confirmed_script = confirmed.json()["confirmed_script"]
        self.assertNotIn("篡改", confirmed_script["title"])
        self.assertNotIn("篡改", confirmed_script["logline"])

    def test_comic_task_replaces_client_confirmed_script_with_server_confirmed_script(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
            "user_message": "主角是女侦探，对手在误导她，最后她发现自己的名字也在信里，结尾要留悬念。",
            "session": body["session"],
        })
        self.assertEqual(response.status_code, 200)
        session = response.json()["session"]

        confirmed = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "session": session,
            "confirmation_notes": "确认真实版本",
        })
        self.assertEqual(confirmed.status_code, 200)
        server_hash = confirmed.json()["confirmed_script"]["script_hash"]

        class DummyTask:
            def add_done_callback(self, callback):
                return None

        def fake_create_task(coro):
            coro.close()
            return DummyTask()

        with patch("src.web.app._schedule_background_task", side_effect=fake_create_task):
            started = self.client.post("/api/tasks", json={
                "user_request": (
                    "Idea: 外部调用\n"
                    "Confirmed script:\nMALICIOUS SCRIPT SHOULD NOT SURVIVE\n"
                    "Script notes: Asset revision notes: 道具只有药箱、求救符、采购清单。"
                ),
                "office_id": "comic",
                "workspace_id": workspace_id,
            })

        self.assertEqual(started.status_code, 200)
        run = config_manager.get_task_run(started.json()["task_id"])
        self.assertIn(server_hash, run["user_request"])
        self.assertNotIn("MALICIOUS SCRIPT SHOULD NOT SURVIVE", run["user_request"])
        self.assertIn("Asset revision notes: 道具只有药箱、求救符、采购清单。", run["user_request"])

    def test_reconfirming_script_invalidates_assets_bound_to_old_script_hash(self):
        response = self.client.post("/api/comic/cabinet/turn", json={
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        workspace_id = body["workspace_id"]
        self.created_workspaces.append(workspace_id)

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
            "user_message": "主角是女侦探，反派在误导她，最后她发现自己名字也在信里，结尾要留悬念。",
            "session": body["session"],
        })
        self.assertEqual(response.status_code, 200)
        session = response.json()["session"]

        confirmed_v1 = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "session": session,
            "confirmation_notes": "先确认第一版。",
        })
        self.assertEqual(confirmed_v1.status_code, 200)
        old_hash = confirmed_v1.json()["confirmed_script"]["script_hash"]

        config_manager.create_artifact(
            artifact_id="art_old_character_sheet",
            workspace_id=workspace_id,
            task_id="",
            artifact_type="character_sheet",
            title="旧版人物设定",
            content="旧脚本版本下的人物设定。",
            metadata={
                "office_id": "comic",
                "script_hash": old_hash,
                "script_version": 1,
                "script_confirmed": True,
            },
            created_by="gongbu",
        )

        response = self.client.post("/api/comic/cabinet/turn", json={
            "workspace_id": workspace_id,
            "idea": "雨夜里失忆侦探捡到一封会改写身份的信",
            "genre": "suspense",
            "length": "3 episodes",
            "platform": "Douyin",
            "visual_style": "dark suspense comic",
            "extra": "",
            "user_message": "补充新设定：幕后操控者其实是她曾经的搭档，第一集必须出现怀表这个新道具。",
            "session": session,
        })
        self.assertEqual(response.status_code, 200)
        updated_session = response.json()["session"]

        confirmed_v2 = self.client.post("/api/comic/confirm-script", json={
            "workspace_id": workspace_id,
            "session": updated_session,
            "confirmation_notes": "确认第二版，加入怀表设定。",
        })
        self.assertEqual(confirmed_v2.status_code, 200)
        new_hash = confirmed_v2.json()["confirmed_script"]["script_hash"]
        self.assertNotEqual(old_hash, new_hash)
        self.assertGreaterEqual(confirmed_v2.json()["invalidated_count"], 1)

        old_artifact = config_manager.get_artifact("art_old_character_sheet")
        self.assertTrue(old_artifact["metadata"]["invalidated"])
        self.assertEqual(old_artifact["metadata"]["invalidated_reason"], "confirmed_script_changed")
        self.assertEqual(old_artifact["metadata"]["current_script_hash"], new_hash)


if __name__ == "__main__":
    unittest.main()
