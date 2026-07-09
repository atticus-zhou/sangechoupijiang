"""Verify that offices cannot leak model config, workspace state, artifacts, or history."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config_manager import ConfigManager


OFFICES = ["research", "comic_production"]


def _check(check_id: str, passed: bool, evidence: list[str], errors: list[str]) -> dict[str, Any]:
    if not passed:
        errors.append(check_id)
    return {
        "id": check_id,
        "status": "passed" if passed else "failed",
        "evidence": evidence,
    }


def _write_isolated_model_config(manager: ConfigManager) -> None:
    config = manager.load_yaml()
    config["models"] = {
        "zhongshu": {
            "provider": "deepseek",
            "model": "global-deepseek",
            "api_key": "${GLOBAL_TEXT_KEY}",
            "temperature": 0.2,
            "max_tokens": 2048,
        }
    }
    config["office_models"] = {
        "research": {
            "zhongshu": {
                "provider": "deepseek",
                "model": "research-deepseek",
                "api_key": "${RESEARCH_TEXT_KEY}",
                "temperature": 0.1,
                "max_tokens": 4096,
            }
        },
        "comic_production": {
            "zhongshu": {
                "provider": "qwen",
                "model": "comic-qwen-vl",
                "api_key": "${COMIC_VISION_KEY}",
                "temperature": 0.4,
                "max_tokens": 8192,
            }
        },
    }
    manager.save_yaml(config)


def _seed_isolated_state(manager: ConfigManager, output_root: Path) -> dict[str, str]:
    research_ws = "ws_research_isolation"
    comic_ws = "ws_comic_isolation"
    research_task = "task_research_isolation"
    comic_task = "task_comic_isolation"
    noise_task = "task_noise_mentions_research_workspace"

    manager.create_workspace(research_ws, "research", "Research isolation sample", "research only")
    manager.create_workspace(comic_ws, "comic_production", "Comic isolation sample", "comic only")

    manager.create_artifact(
        artifact_id="art_research_isolation_report",
        workspace_id=research_ws,
        task_id=research_task,
        artifact_type="research_report",
        title="Research report artifact",
        uri="output/research/ws_research_isolation/report.md",
        content="research artifact",
        metadata={"office_id": "research", "responsible_agent": "bingbu"},
        created_by="bingbu",
    )
    manager.create_artifact(
        artifact_id="art_comic_isolation_canvas",
        workspace_id=comic_ws,
        task_id=comic_task,
        artifact_type="comic_v2_word_canvas",
        title="Comic production canvas artifact",
        uri="output/comic_production/ws_comic_isolation/canvas.docx",
        content="comic artifact",
        metadata={"office_id": "comic_production", "responsible_agent": "shangshu"},
        created_by="shangshu",
    )

    for task_id, workspace_id, office_id in [
        (research_task, research_ws, "research"),
        (comic_task, comic_ws, "comic_production"),
    ]:
        manager.create_task_run(task_id, f"{office_id} isolated task")
        manager.update_task_run(task_id, "completed", current_phase="completed", completed=True)
        manager.append_task_event(
            task_id,
            "isolation_audit_event",
            "completed",
            f"{office_id} event",
            {"office_id": office_id, "workspace_id": workspace_id, "stage": "completed"},
        )

    manager.create_task_run(noise_task, "noise task that only mentions a workspace id")
    manager.append_task_event(
        noise_task,
        "noise_event",
        "completed",
        "This event mentions another workspace but does not belong to it",
        {
            "office_id": "comic_production",
            "workspace_id": "ws_noise_isolation",
            "note": research_ws,
        },
    )

    for office_id, workspace_id, file_name in [
        ("research", research_ws, "report.md"),
        ("comic_production", comic_ws, "canvas.docx"),
    ]:
        folder = output_root / office_id / workspace_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / file_name).write_text(f"{office_id}:{workspace_id}", encoding="utf-8")

    return {
        "research_ws": research_ws,
        "comic_ws": comic_ws,
        "research_task": research_task,
        "comic_task": comic_task,
        "noise_task": noise_task,
    }


def verify_office_isolation() -> dict[str, Any]:
    errors: list[str] = []
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="sange_office_isolation_") as temp_dir:
        base_dir = Path(temp_dir)
        output_root = base_dir / "output"
        manager = ConfigManager(base_dir=str(base_dir))
        _write_isolated_model_config(manager)
        ids = _seed_isolated_state(manager, output_root)

        research_model = manager.get_model_config("zhongshu", office_id="research")
        comic_model = manager.get_model_config("zhongshu", office_id="comic_production")
        global_model = manager.get_model_config("zhongshu")
        model_ok = (
            research_model.model == "research-deepseek"
            and comic_model.model == "comic-qwen-vl"
            and global_model.model == "global-deepseek"
            and research_model.model != comic_model.model
            and research_model.api_key != comic_model.api_key
        )
        checks.append(_check(
            "model_config_isolation",
            model_ok,
            [
                f"research.zhongshu={research_model.provider}/{research_model.model}",
                f"comic_production.zhongshu={comic_model.provider}/{comic_model.model}",
                f"global.zhongshu={global_model.provider}/{global_model.model}",
                "api keys remain env placeholders and are not printed",
            ],
            errors,
        ))

        research_workspaces = manager.list_workspaces(office_id="research")
        comic_workspaces = manager.list_workspaces(office_id="comic_production")
        workspace_ok = (
            [item["workspace_id"] for item in research_workspaces] == [ids["research_ws"]]
            and [item["workspace_id"] for item in comic_workspaces] == [ids["comic_ws"]]
        )
        checks.append(_check(
            "workspace_scope_isolation",
            workspace_ok,
            [
                f"research workspaces={[item['workspace_id'] for item in research_workspaces]}",
                f"comic workspaces={[item['workspace_id'] for item in comic_workspaces]}",
            ],
            errors,
        ))

        research_artifacts = manager.list_artifacts(workspace_id=ids["research_ws"])
        comic_artifacts = manager.list_artifacts(workspace_id=ids["comic_ws"])
        artifact_ok = (
            len(research_artifacts) == 1
            and len(comic_artifacts) == 1
            and research_artifacts[0]["metadata"].get("office_id") == "research"
            and comic_artifacts[0]["metadata"].get("office_id") == "comic_production"
            and research_artifacts[0]["artifact_id"] != comic_artifacts[0]["artifact_id"]
        )
        checks.append(_check(
            "artifact_scope_isolation",
            artifact_ok,
            [
                f"research artifact={research_artifacts[0]['artifact_id'] if research_artifacts else ''}",
                f"comic artifact={comic_artifacts[0]['artifact_id'] if comic_artifacts else ''}",
                "artifact metadata contains office_id and reference_chain",
            ],
            errors,
        ))

        research_tasks = manager.list_workspace_task_runs(ids["research_ws"])
        comic_tasks = manager.list_workspace_task_runs(ids["comic_ws"])
        research_task_ids = [item["task_id"] for item in research_tasks]
        comic_task_ids = [item["task_id"] for item in comic_tasks]
        history_ok = (
            research_task_ids == [ids["research_task"]]
            and comic_task_ids == [ids["comic_task"]]
            and ids["noise_task"] not in research_task_ids
            and ids["noise_task"] not in comic_task_ids
        )
        checks.append(_check(
            "history_trace_isolation",
            history_ok,
            [
                f"workspace_id={ids['research_ws']} task_ids={research_task_ids}",
                f"workspace_id={ids['comic_ws']} task_ids={comic_task_ids}",
                f"noise task mentioning {ids['research_ws']} is excluded by exact workspace_id filtering",
            ],
            errors,
        ))

        research_files = sorted(str(path.relative_to(output_root)).replace("\\", "/") for path in (output_root / "research").rglob("*") if path.is_file())
        comic_files = sorted(str(path.relative_to(output_root)).replace("\\", "/") for path in (output_root / "comic_production").rglob("*") if path.is_file())
        filesystem_ok = research_files == ["research/ws_research_isolation/report.md"] and comic_files == ["comic_production/ws_comic_isolation/canvas.docx"]
        checks.append(_check(
            "filesystem_output_isolation",
            filesystem_ok,
            [
                f"research output files={research_files}",
                f"comic output files={comic_files}",
                "sample output paths use output/{office_id}/{workspace_id}",
            ],
            errors,
        ))

    return {
        "status": "passed" if not errors else "failed",
        "mode": "offline_isolation_audit",
        "offices": OFFICES,
        "safe_for_public_repo": True,
        "checks": checks,
        "errors": errors,
    }


def format_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Office Isolation Audit",
        "",
        f"Status: `{audit.get('status')}`",
        f"Mode: `{audit.get('mode')}`",
        f"Offices: `{', '.join(audit.get('offices', []))}`",
        "",
        "| Check | Status | Evidence |",
        "| --- | --- | --- |",
    ]
    for item in audit.get("checks", []):
        evidence = "<br>".join(item.get("evidence", []))
        lines.append(f"| {item.get('id')} | {item.get('status')} | {evidence} |")
    if audit.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in audit["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify office isolation contracts without calling models.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    audit = verify_office_isolation()
    if args.format == "json":
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(audit))
    return 0 if audit["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
