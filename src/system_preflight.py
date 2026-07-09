"""System-level startup preflight checks.

This module checks local runtime prerequisites without calling model providers.
It is meant for first-run clarity: users should know whether the app can read
its config, reach its local database, write outputs, and whether the main office
has enough configured model capacity to proceed.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.office_preflight import build_office_preflight


@dataclass(frozen=True)
class SystemCheck:
    id: str
    title: str
    status: str
    scope: str
    impact: str
    next_action: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "scope": self.scope,
            "impact": self.impact,
            "next_action": self.next_action,
            "detail": self.detail,
        }


def build_system_preflight(config_manager: Any, *, base_dir: Path | str = ".") -> dict[str, Any]:
    """Return a cheap, local-only startup readiness report."""
    base = Path(base_dir)
    main_office = _safe_main_office_preflight(config_manager, base)
    checks = [
        _python_runtime_check(),
        _config_file_check(Path(config_manager.config_path)),
        _database_check(Path(config_manager.db_path)),
        _output_directory_check(base / "output"),
        _model_configuration_check(main_office),
    ]
    blocking = [check for check in checks if check.status == "blocked"]
    missing = [check for check in checks if check.status == "missing"]
    if blocking:
        status = "blocked"
        summary = "启动检查发现本地运行条件未满足。"
        next_action = blocking[0].next_action
    elif missing:
        status = "partial"
        summary = "本地运行环境可用，但部分模型能力尚未配置。"
        next_action = missing[0].next_action
    else:
        status = "ready"
        summary = f"Python {sys.version_info.major}.{sys.version_info.minor}、配置、数据库、输出目录和主力办公室模型配置可用。"
        next_action = "可以进入 AI 漫剧制片办公室开始工作。"
    return {
        "status": status,
        "summary": summary,
        "next_action": next_action,
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
        },
        "blocking_reasons": [check.id for check in blocking],
        "available_modes": _available_modes(checks, main_office),
        "limited_features": _limited_features(checks, main_office),
        "checks": [check.to_dict() for check in checks],
    }


def _python_runtime_check() -> SystemCheck:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        return SystemCheck(
            id="python_runtime",
            title="Python 运行环境",
            status="ok",
            scope="runtime",
            detail=f"当前 Python {version}",
            impact="Python 可用时，后端服务、文档生成和本地数据库访问可以正常执行。",
            next_action="已具备。",
        )
    return SystemCheck(
        id="python_runtime",
        title="Python 运行环境",
        status="blocked",
        scope="runtime",
        detail=f"当前 Python {version}",
        impact="Python 版本过低时，FastAPI 后端和部分类型语法可能无法运行。",
        next_action="安装 Python 3.10 或更高版本后重新启动。",
    )


def _config_file_check(config_path: Path) -> SystemCheck:
    try:
        if not config_path.exists():
            raise FileNotFoundError
        config_path.read_text(encoding="utf-8")
        return SystemCheck(
            id="config_file",
            title="配置文件",
            status="ok",
            scope="config",
            detail=str(config_path),
            impact="配置文件可读时，系统可以加载办公室、模型和运行参数。",
            next_action="已具备。",
        )
    except OSError:
        return SystemCheck(
            id="config_file",
            title="配置文件",
            status="blocked",
            scope="config",
            detail=str(config_path),
            impact="无法读取 config.yaml 时，模型配置和系统参数都无法可靠加载。",
            next_action="确认 config.yaml 存在且当前用户有读取权限；必要时重新运行启动命令生成默认配置。",
        )


def _database_check(db_path: Path) -> SystemCheck:
    try:
        if not db_path.exists():
            raise FileNotFoundError
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
        return SystemCheck(
            id="database",
            title="本地数据库",
            status="ok",
            scope="user_data",
            detail=str(db_path),
            impact="数据库可访问时，模型配置、项目、历史和任务状态可以持久化。",
            next_action="已具备。",
        )
    except (OSError, sqlite3.Error):
        return SystemCheck(
            id="database",
            title="本地数据库",
            status="blocked",
            scope="user_data",
            detail=str(db_path),
            impact="数据库不可访问时，用户配置、项目历史和长任务记录可能无法保存。",
            next_action="检查 user_data 目录权限；如果是首次运行，请重启服务让系统重新创建数据库。",
        )


def _output_directory_check(output_dir: Path) -> SystemCheck:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / ".system_preflight_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return SystemCheck(
            id="output_directory",
            title="输出目录",
            status="ok",
            scope="output",
            detail=str(output_dir),
            impact="输出目录可写时，图片、证据、Word 画布和导出包可以保存。",
            next_action="已具备。",
        )
    except OSError:
        return SystemCheck(
            id="output_directory",
            title="输出目录",
            status="blocked",
            scope="output",
            detail=str(output_dir),
            impact="输出目录不可写时，生成图片和 Word 交付物会失败。",
            next_action="检查 output 目录权限，或把项目移动到当前用户可写的位置。",
        )


def _safe_main_office_preflight(config_manager: Any, base_dir: Path) -> dict[str, Any]:
    try:
        return build_office_preflight(
            "comic_production",
            config_manager.get_model_config,
            base_dir=base_dir,
        )
    except Exception as exc:  # pragma: no cover - defensive, reported to user.
        return {
            "office_id": "comic_production",
            "status": "blocked",
            "summary": str(exc),
            "next_action": "打开模型页面，检查 AI 漫剧制片办公室各部门供应商、模型名和 API Key。",
            "blocking_reasons": ["model_configuration"],
            "capabilities": [],
        }


def _model_configuration_check(office: dict[str, Any]) -> SystemCheck:
    if office.get("blocking_reasons") == ["model_configuration"] and not office.get("capabilities"):
        return SystemCheck(
            id="model_configuration",
            title="模型配置",
            status="blocked",
            scope="models",
            detail=office.get("summary", ""),
            impact="模型配置无法读取时，用户无法判断哪些部门能工作。",
            next_action=office.get("next_action", "打开模型页面补齐模型配置。"),
        )
    status = office.get("status", "blocked")
    if status == "ready":
        return SystemCheck(
            id="model_configuration",
            title="模型配置",
            status="ok",
            scope="models",
            detail=office.get("summary", ""),
            impact="主力办公室模型配置可用时，可以进入真实生产链路。",
            next_action="已具备。",
        )
    return SystemCheck(
        id="model_configuration",
        title="模型配置",
        status="blocked" if status == "blocked" else "missing",
        scope="models",
        detail=office.get("summary", ""),
        impact="模型配置不完整时，故事、资产、图片或视觉质检会在对应阶段被阻塞。",
        next_action=office.get("next_action", "打开模型页面补齐缺失部门。"),
    )


def _available_modes(checks: list[SystemCheck], office: dict[str, Any]) -> list[dict[str, str]]:
    modes = [
        {
            "id": "no_key_demo",
            "label": "无 Key 演示模式",
            "status": "available",
            "description": "可以直接查看固定样例、下载样例交付物，不读取也不消耗 API Key。",
        }
    ]
    if _has_blocking_runtime(checks):
        return modes

    capabilities = {item.get("id"): item for item in office.get("capabilities") or []}
    text_ready = all(
        (capabilities.get(capability_id) or {}).get("status") == "ok"
        for capability_id in ("story_planning", "asset_planning", "prompt_planning", "local_output")
    )
    image_ready = (capabilities.get("image_generation") or {}).get("status") == "ok"
    vision_ready = (capabilities.get("visual_review") or {}).get("status") == "ok"

    if text_ready:
        modes.append({
            "id": "comic_story_and_prompts",
            "label": "故事、资产拆解和提示词模式",
            "status": "available",
            "description": "文本部门可用，可以先完成故事确认、资产拆解、镜头卡和提示词包。",
        })
    if text_ready and image_ready and vision_ready:
        modes.append({
            "id": "comic_full_production",
            "label": "AI 漫剧完整制片模式",
            "status": "available",
            "description": "文本、生图、视觉质检和本地输出均可用，可以生成完整制片包。",
        })
    return modes


def _limited_features(checks: list[SystemCheck], office: dict[str, Any]) -> list[dict[str, str]]:
    limited = []
    for check in checks:
        if check.status == "blocked" and check.id != "model_configuration":
            limited.append({
                "id": "local_real_mode",
                "label": "本地真实生产模式",
                "reason": f"{check.title}不可用：{check.impact}",
                "next_action": check.next_action,
            })
    for capability in office.get("capabilities") or []:
        if capability.get("status") == "ok":
            continue
        limited.append({
            "id": capability.get("id", "unknown_capability"),
            "label": capability.get("title", "受限功能"),
            "reason": f"{capability.get('owner_label', '')}{capability.get('model_kind', '')}未就绪：{capability.get('impact', '')}",
            "next_action": capability.get("next_action", ""),
        })
    return limited


def _has_blocking_runtime(checks: list[SystemCheck]) -> bool:
    return any(check.status == "blocked" and check.id != "model_configuration" for check in checks)
