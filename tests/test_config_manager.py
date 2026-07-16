import tempfile
import unittest
from pathlib import Path

from src.config_manager import ConfigManager
from src.main import SanShengLiuBu


class ConfigManagerTaskRunTests(unittest.TestCase):
    def test_task_run_lifecycle_is_persisted_with_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)

            manager.create_task_run("task-1", "write a report", "research")
            manager.append_task_event("task-1", "task_created", "queued", "accepted")
            manager.update_task_run(
                "task-1",
                "completed",
                current_phase="completed",
                result={"status": "completed", "final_report": "done"},
                completed=True,
            )

            run = manager.get_task_run("task-1")

            self.assertEqual(run["task_id"], "task-1")
            self.assertEqual(run["status"], "completed")
            self.assertEqual(run["current_phase"], "completed")
            self.assertEqual(run["result"]["final_report"], "done")
            self.assertEqual(len(run["events"]), 1)
            self.assertEqual(run["events"][0]["event_type"], "task_created")
            self.assertIsNotNone(run["completed_at"])

    def test_interrupted_task_runs_are_marked_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)

            manager.create_task_run("task-queued", "make comic package", "")
            manager.append_task_event(
                "task-queued",
                "task_created",
                "queued",
                "accepted",
                {"office_id": "comic_production", "workspace_id": "ws-prod"},
            )
            manager.create_task_run("task-done", "completed work", "")
            manager.update_task_run("task-done", "completed", current_phase="completed", completed=True)

            changed = manager.mark_interrupted_task_runs("server restarted before background task started")

            self.assertEqual(changed, 1)
            interrupted = manager.get_task_run("task-queued")
            self.assertEqual(interrupted["status"], "interrupted")
            self.assertEqual(interrupted["current_phase"], "interrupted")
            self.assertIn("server restarted", interrupted["error"])
            self.assertEqual(interrupted["events"][-1]["event_type"], "task_interrupted_after_restart")

            completed = manager.get_task_run("task-done")
            self.assertEqual(completed["status"], "completed")

    def test_failed_task_run_exposes_recovery_plan_from_last_failure_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)

            manager.create_task_run("task-recover", "generate comic images", "")
            manager.update_task_run(
                "task-recover",
                "failed",
                current_phase="image_generation",
                error="资产图片生产失败：vision schema rejected",
                completed=True,
            )
            manager.append_task_event(
                "task-recover",
                "comic_v2_images_failed",
                "failed",
                "基础资产图生产或质检失败",
                {
                    "workspace_id": "ws-comic",
                    "office_id": "comic_production",
                    "department": "工部 / 刑部",
                    "stage": "image_generation",
                    "agent": "gongbu/xingbu",
                    "impact": "Word 制片画布不会继续组装。",
                    "next_action": "修复工部生图模型和刑部视觉模型后重新生成基础资产图。",
                    "retry_action": {
                        "label": "重新生成并质检基础资产图",
                        "method": "POST",
                        "path": "/api/workspaces/ws-comic/comic/v2/images/generate",
                    },
                },
            )

            run = manager.get_task_run("task-recover")
            plan = run["recovery_plan"]

            self.assertTrue(plan["recoverable"])
            self.assertEqual(plan["failed_phase"], "image_generation")
            self.assertEqual(plan["department"], "工部 / 刑部")
            self.assertEqual(plan["workspace_id"], "ws-comic")
            self.assertIn("视觉模型", plan["next_action"])
            self.assertEqual(plan["retry_action"]["path"], "/api/workspaces/ws-comic/comic/v2/images/generate")

    def test_comic_v2_recovery_plan_infers_retry_action_from_failed_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)

            cases = [
                ("visual_bible_planning", "/api/workspaces/ws-comic/comic/v2/plan-confirmed"),
                ("asset_planning", "/api/workspaces/ws-comic/comic/v2/assets/plan"),
                ("prompt_planning", "/api/workspaces/ws-comic/comic/v2/prompts/plan"),
                ("document_generation", "/api/workspaces/ws-comic/comic/v2/delivery/build"),
            ]
            for stage, expected_path in cases:
                task_id = f"task-{stage}"
                manager.create_task_run(task_id, "recover stage", "")
                manager.update_task_run(
                    task_id,
                    "failed",
                    current_phase=stage,
                    error=f"{stage} failed",
                    completed=True,
                )
                manager.append_task_event(
                    task_id,
                    f"comic_v2_{stage}_failed",
                    "failed",
                    "stage failed",
                    {
                        "workspace_id": "ws-comic",
                        "office_id": "comic_production",
                        "stage": stage,
                        "department": "测试部门",
                    },
                )

                plan = manager.get_task_run(task_id)["recovery_plan"]

                self.assertTrue(plan["recoverable"], stage)
                self.assertEqual(plan["retry_action"]["path"], expected_path)
                self.assertEqual(plan["retry_action"]["method"], "POST")

    def test_research_recovery_plan_infers_retry_action_from_failed_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)

            cases = [
                ("feigua_evidence_capture", "/api/workspaces/ws-research/evidence/sync", "整理已上传/已截取证据"),
                ("evidence_extraction", "/api/workspaces/ws-research/evidence/extract-all", "重新识别工作区截图证据"),
                ("agent_workflow", "/api/tasks/task-agent_workflow/recover-artifacts", "整理已有研究产出"),
                ("artifact_packaging", "/api/tasks/task-artifact_packaging/recover-artifacts", "重新整理研究材料包"),
            ]
            for stage, expected_path, expected_label in cases:
                task_id = f"task-{stage}"
                manager.create_task_run(task_id, "research stage", "")
                manager.update_task_run(
                    task_id,
                    "failed",
                    current_phase=stage,
                    error=f"{stage} failed",
                    completed=True,
                )
                manager.append_task_event(
                    task_id,
                    f"research_{stage}_failed",
                    "failed",
                    "research stage failed",
                    {
                        "workspace_id": "ws-research",
                        "office_id": "research",
                        "stage": stage,
                        "department": "测试部门",
                    },
                )

                plan = manager.get_task_run(task_id)["recovery_plan"]

                self.assertTrue(plan["recoverable"], stage)
                self.assertEqual(plan["retry_action"]["path"], expected_path)
                self.assertEqual(plan["retry_action"]["method"], "POST")
                self.assertEqual(plan["retry_action"]["label"], expected_label)

    def test_workspace_and_artifact_are_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)

            manager.create_workspace(
                workspace_id="ws-1",
                office_id="research",
                title="Projector market research",
                brief="Need charts and source notes",
            )
            manager.create_artifact(
                artifact_id="art-1",
                workspace_id="ws-1",
                task_id="task-1",
                artifact_type="source_list",
                title="Initial sources",
                content="source A\nsource B",
                metadata={"count": 2},
                created_by="bingbu",
            )

            workspace = manager.get_workspace("ws-1")
            artifacts = manager.list_artifacts(workspace_id="ws-1")

            self.assertEqual(workspace["office_id"], "research")
            self.assertEqual(workspace["title"], "Projector market research")
            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifacts[0]["artifact_type"], "source_list")
            self.assertEqual(artifacts[0]["metadata"]["count"], 2)

    def test_artifact_metadata_is_normalized_to_office_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)
            manager.create_workspace(
                workspace_id="ws-comic",
                office_id="comic_production",
                title="Moon city",
            )

            manager.create_artifact(
                artifact_id="art-contract-1",
                workspace_id="ws-comic",
                task_id="task-comic",
                artifact_type="word_canvas",
                title="Word 制片画布",
                content="canvas",
                metadata={"custom": "kept"},
                created_by="gongbu",
            )

            artifact = manager.get_artifact("art-contract-1")
            metadata = artifact["metadata"]

            self.assertEqual(metadata["custom"], "kept")
            self.assertEqual(metadata["office_id"], "comic_production")
            self.assertEqual(metadata["source"], "workspace:ws-comic")
            self.assertEqual(metadata["version"], "v1")
            self.assertEqual(metadata["responsible_agent"], "gongbu")
            self.assertEqual(metadata["reference_chain"][0]["kind"], "workspace")
            self.assertEqual(metadata["reference_chain"][0]["id"], "ws-comic")
            self.assertEqual(metadata["reference_chain"][1]["kind"], "task")
            self.assertEqual(metadata["reference_chain"][1]["id"], "task-comic")

    def test_artifact_contract_rejects_missing_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)
            manager.create_workspace("ws-research", "research", "Market research")

            with self.assertRaises(ValueError) as ctx:
                manager.create_artifact(
                    artifact_id="",
                    workspace_id="ws-research",
                    task_id="task-research",
                    artifact_type="report",
                    title="Report",
                    created_by="libu_comm",
                )

            self.assertIn("artifact_id", str(ctx.exception))

    def test_model_config_can_be_scoped_by_office(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)
            config = manager.load_yaml()
            config["models"] = {
                "hubu": {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "api_key": "global-key",
                }
            }
            config["office_models"] = {
                "research": {
                    "hubu": {
                        "provider": "dashscope",
                        "model": "qwen-vl-max",
                        "api_key": "research-key",
                    }
                },
                "comic": {
                    "hubu": {
                        "provider": "minimax",
                        "model": "abab6.5s-chat",
                        "api_key": "comic-key",
                    }
                },
            }
            manager.save_yaml(config)

            global_cfg = manager.get_model_config("hubu")
            research_cfg = manager.get_model_config("hubu", office_id="research")
            comic_cfg = manager.get_model_config("hubu", office_id="comic")

            self.assertEqual(global_cfg.api_key, "global-key")
            self.assertEqual(research_cfg.api_key, "research-key")
            self.assertEqual(research_cfg.model, "qwen-vl-max")
            self.assertEqual(comic_cfg.api_key, "comic-key")
            self.assertEqual(comic_cfg.provider, "minimax")

    def test_engine_passes_office_id_to_all_agents(self):
        engine = SanShengLiuBu(office_id="research")

        agents = [
            engine.zhongshu,
            engine.menxia,
            engine.shangshu,
            engine.libu,
            engine.hubu,
            engine.libu_comm,
            engine.bingbu,
            engine.xingbu,
            engine.gongbu,
        ]

        self.assertEqual(engine.office_id, "research")
        self.assertTrue(all(agent.office_id == "research" for agent in agents))

    def test_comic_production_office_keeps_bingbu_text_and_gongbu_image_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)
            config = manager.load_yaml()
            config["office_models"] = {
                "comic_production": {
                    "bingbu": {
                        "provider": "deepseek",
                        "model": "deepseek-chat",
                        "api_key": "deepseek-key",
                    },
                    "gongbu": {
                        "provider": "doubao",
                        "model": "doubao-seedream-5",
                        "api_key": "doubao-key",
                    },
                }
            }
            manager.save_yaml(config)

            bingbu = manager.get_model_config("bingbu", office_id="comic_production")
            gongbu = manager.get_model_config("gongbu", office_id="comic_production")
            research_bingbu = manager.get_model_config("bingbu", office_id="research")

            self.assertEqual(bingbu.provider, "deepseek")
            self.assertEqual(bingbu.model, "deepseek-chat")
            self.assertEqual(gongbu.provider, "doubao")
            self.assertNotEqual(research_bingbu.provider, "doubao")

    def test_model_config_strips_copied_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ConfigManager(base_dir=tmp)
            config = manager.load_yaml()
            config["office_models"] = {
                "comic_production": {
                    "gongbu": {
                        "provider": " doubao ",
                        "model": "\tdoubao-seedream-5 ",
                        "api_key": "\t ark-test-key ",
                        "api_base": " https://ark.cn-beijing.volces.com/api/v3 ",
                    }
                }
            }
            manager.save_yaml(config)

            gongbu = manager.get_model_config("gongbu", office_id="comic_production")

            self.assertEqual(gongbu.provider, "doubao")
            self.assertEqual(gongbu.model, "doubao-seedream-5")
            self.assertEqual(gongbu.api_key, "ark-test-key")
            self.assertEqual(gongbu.api_base, "https://ark.cn-beijing.volces.com/api/v3")


if __name__ == "__main__":
    unittest.main()
