"""Build a first-run checklist for people cloning the project from GitHub."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.doctor import build_doctor_report
from src.product_readiness import audit_comic_production_readiness


PUBLIC_DEMO_COMMAND = "python scripts/verify_public_demo_mode.py --format markdown"
STATIC_EXPORT_COMMAND = "python scripts/export_public_showcase.py"
STATIC_SHOWCASE_COMMAND = "python scripts/verify_static_public_showcase.py --format markdown"
DOWNSTREAM_HANDOFF_COMMAND = "python scripts/verify_comic_v2_downstream_handoff.py --format markdown"
LOCAL_DOCTOR_COMMAND = "python scripts/doctor.py --format markdown"
PRODUCT_READINESS_COMMAND = "python scripts/verify_product_readiness.py --format markdown"
OFFICE_ISOLATION_COMMAND = "python scripts/verify_office_isolation.py --format markdown"
SERVER_COMMAND = "python run.py --port 8080"
HANDOFF_AUDIT_COMMAND = "python scripts/audit_comic_v2_handoffs.py --format markdown"
REQUIRED_PYTHON_PACKAGES = [
    "litellm",
    "fastapi",
    "uvicorn",
    "chromadb",
    "pyyaml",
    "python-dotenv",
    "pydantic",
    "python-docx",
    "pillow",
    "requests",
    "beautifulsoup4",
    "python-multipart",
]
REAL_CLAIM_COMMAND = (
    "python scripts/verify_comic_real_production_claim.py "
    "--manifest output/your_project/xxx_handoff_manifest.json --format markdown"
)
PRODUCTION_BENCHMARK_COMMAND = (
    "python scripts/verify_comic_v2_production_benchmark.py "
    "--manifest output/your_project/xxx_handoff_manifest.json --format markdown"
)


def build_first_run_readiness(base_dir: Path | str = REPO_ROOT) -> dict[str, Any]:
    root = Path(base_dir)
    doctor = build_doctor_report(root)
    product = audit_comic_production_readiness(root)
    system_status = str(doctor.get("system", {}).get("status") or "blocked")
    office_status = str(doctor.get("office", {}).get("status") or "blocked")
    real_status = str((doctor.get("real_production") or {}).get("status") or "blocked")
    local_ready = system_status == "ready" and office_status == "ready" and real_status == "ready_for_real_run"

    paths = [
        _public_demo_path(),
        _local_real_use_path(doctor, local_ready),
        _developer_extension_path(product),
    ]
    return {
        "product": "三个臭皮匠",
        "status": "ready_for_guided_first_run",
        "mode": "new_user_reproducibility",
        "safe_for_public_repo": True,
        "summary": "A GitHub-first checklist for demo viewing, local real use, and office extension.",
        "paths": paths,
        "recommended_order": [item["id"] for item in paths],
        "github_download_checklist": _github_download_checklist(root),
        "deployment_mode_matrix": _deployment_mode_matrix(),
        "commands": {
            "public_demo": PUBLIC_DEMO_COMMAND,
            "static_showcase_export": STATIC_EXPORT_COMMAND,
            "static_showcase_verify": STATIC_SHOWCASE_COMMAND,
            "comic_downstream_handoff": DOWNSTREAM_HANDOFF_COMMAND,
            "local_doctor": LOCAL_DOCTOR_COMMAND,
            "comic_handoff_audit": HANDOFF_AUDIT_COMMAND,
            "comic_real_claim": REAL_CLAIM_COMMAND,
            "comic_production_benchmark": PRODUCTION_BENCHMARK_COMMAND,
            "product_readiness": PRODUCT_READINESS_COMMAND,
            "office_isolation": OFFICE_ISOLATION_COMMAND,
            "server": SERVER_COMMAND,
        },
        "common_first_run_failures": _common_first_run_failures(),
        "safety_boundaries": [
            "Do not commit API Key values; use environment variables or local config.yaml only.",
            "Do not publish user_data, output, runtime_logs, browser profiles, cookies, or generated private deliverables.",
            "Public demos must stay read-only and must not call real model providers.",
        ],
        "doctor_status": doctor.get("status", ""),
        "product_readiness_status": product.get("status", ""),
    }


def _github_download_checklist(root: Path) -> dict[str, Any]:
    expected_public_files = [
        "README.md",
        "requirements.txt",
        "config.example.yaml",
        "run.py",
        "scripts/doctor.py",
        "scripts/verify_first_run_readiness.py",
        "scripts/verify_release_readiness.py",
        "scripts/check_no_secrets.py",
        "docs/FIRST_RUN_DECISION_CARD.md",
        "docs/MODEL_CONFIGURATION.md",
        "docs/MODEL_CAPABILITY_MATRIX.json",
        "docs/DEPLOYMENT_MODES.md",
        "docs/STATIC_SHOWCASE_DEPLOYMENT.md",
        "docs/PUBLIC_RELEASE_HANDOFF.md",
    ]
    file_checks = [
        {
            "path": path,
            "status": "present" if (root / path).exists() else "missing",
            "why_it_matters": _first_run_file_reason(path),
        }
        for path in expected_public_files
    ]
    missing_files = [item["path"] for item in file_checks if item["status"] != "present"]
    dependency_check = _requirements_dependency_check(root)
    status = "ready"
    if missing_files:
        status = "missing_required_files"
    elif dependency_check["missing_packages"]:
        status = "missing_required_dependencies"
    return {
        "status": status,
        "summary": "What a GitHub downloader should see before trying real model calls.",
        "expected_public_file_count": len(file_checks),
        "present_public_file_count": len(file_checks) - len(missing_files),
        "missing_public_files": missing_files,
        "expected_public_files": file_checks,
        "required_python_packages": dependency_check["required_packages"],
        "present_python_packages": dependency_check["present_packages"],
        "missing_python_packages": dependency_check["missing_packages"],
        "private_paths_never_commit": [
            "config.yaml",
            ".env",
            "user_data/",
            "output/",
            "runtime_logs/",
            "logs/",
            "*.db",
            "*.sqlite3",
            "*.docx generated from real runs",
            "browser profiles, cookies, and third-party login state",
        ],
        "first_commands": [
            {
                "name": "本地环境体检",
                "command": LOCAL_DOCTOR_COMMAND,
                "proves": "依赖、配置、输出目录、办公室状态和真实生产前检查是否能被新人理解。",
            },
            {
                "name": "第一次运行清单",
                "command": "python scripts/verify_first_run_readiness.py --format markdown",
                "proves": "公开演示、本地真实使用和开发者扩展三条路径是否分开说明。",
            },
            {
                "name": "公开发布总门禁",
                "command": "python scripts/verify_release_readiness.py --format markdown",
                "proves": "无 Key demo、静态展示包、交付物、模型指引、隔离和密钥扫描是否统一通过。",
            },
        ],
        "before_public_sharing": [
            PUBLIC_DEMO_COMMAND,
            STATIC_EXPORT_COMMAND,
            STATIC_SHOWCASE_COMMAND,
            "python scripts/verify_release_readiness.py --format markdown",
            "python scripts/check_no_secrets.py",
        ],
    }


def _deployment_mode_matrix() -> list[dict[str, Any]]:
    return [
        {
            "id": "public_demo",
            "title": "公开无 Key 演示",
            "status": "ready",
            "who_can_use": "面试官、作品集访客、第一次看项目的人。",
            "allowed": [
                "查看固定样例",
                "下载样例 Word、handoff manifest、trace 和研究报告",
                "访问 /api/demo 或静态 dist/public-showcase",
            ],
            "forbidden": [
                "调用真实模型",
                "写入用户工作区",
                "读取 config.yaml、.env、Cookie、浏览器登录态或本地输出目录",
            ],
            "requires_api_key": False,
            "allows_real_model_calls": False,
            "allows_workspace_writes": False,
            "verification": STATIC_SHOWCASE_COMMAND,
        },
        {
            "id": "local_real_use",
            "title": "本地真实使用",
            "status": "ready_when_user_configures_models",
            "who_can_use": "项目使用者本人，使用自己的本地 Key 和本地文件。",
            "allowed": [
                "在本机填写模型 Key",
                "运行真实办公室任务",
                "生成本地 Word、图片、历史记录和追溯文件",
            ],
            "forbidden": [
                "提交 config.yaml、.env、user_data、output、runtime_logs 或真实生成文件",
                "把作者 Key 提供给外部访问者",
                "把未验证真实质量的产物说成 production_quality_verified",
            ],
            "requires_api_key": True,
            "allows_real_model_calls": True,
            "allows_workspace_writes": True,
            "verification": LOCAL_DOCTOR_COMMAND,
        },
        {
            "id": "future_saas",
            "title": "未来 SaaS 模式",
            "status": "not_current_product",
            "who_can_use": "未来的陌生在线用户；当前仓库还没有提供这类能力。",
            "allowed": [
                "未来可设计账号、租户隔离、配额、计费、队列和服务端 Key 托管",
            ],
            "forbidden": [
                "把当前本地版直接部署成多人在线真实生产系统",
                "把 API Key 放进前端 JavaScript、HTML、静态 JSON 或公开环境变量",
                "绕过权限、成本、队列和文件授权设计直接开放真实接口",
            ],
            "requires_api_key": "future_server_or_user_key_policy_required",
            "allows_real_model_calls": "not_implemented",
            "allows_workspace_writes": "not_implemented",
            "verification": "docs/DEPLOYMENT_MODES.md",
        },
    ]


def _requirements_dependency_check(root: Path) -> dict[str, Any]:
    requirements = root / "requirements.txt"
    declared = _declared_requirement_names(requirements.read_text(encoding="utf-8") if requirements.exists() else "")
    present = [package for package in REQUIRED_PYTHON_PACKAGES if package in declared]
    missing = [package for package in REQUIRED_PYTHON_PACKAGES if package not in declared]
    return {
        "required_packages": REQUIRED_PYTHON_PACKAGES,
        "present_packages": present,
        "missing_packages": missing,
    }


def _declared_requirement_names(text: str) -> set[str]:
    names: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split(";", 1)[0].strip()
        for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            name = name.split(separator, 1)[0].strip()
        name = name.split("[", 1)[0].strip().lower().replace("_", "-")
        if name:
            names.add(name)
    return names


def _first_run_file_reason(path: str) -> str:
    reasons = {
        "README.md": "GitHub front door: explains what the product is and which path a visitor should take.",
        "requirements.txt": "Lets a new user install the Python dependencies deterministically.",
        "config.example.yaml": "Shows model configuration shape without exposing any real API Key.",
        "run.py": "Starts the local app for real local use.",
        "scripts/doctor.py": "Gives a quick local health check before the user blames the product flow.",
        "scripts/verify_first_run_readiness.py": "Prints the GitHub-first onboarding checklist.",
        "scripts/verify_release_readiness.py": "Aggregates the public-release gate.",
        "scripts/check_no_secrets.py": "Prevents API Keys and runtime artifacts from entering the public repo.",
        "docs/FIRST_RUN_DECISION_CARD.md": "Short human decision card separating no-key demo, local real use, and developer extension.",
        "docs/MODEL_CONFIGURATION.md": "Explains which departments need text, image, or vision models.",
        "docs/MODEL_CAPABILITY_MATRIX.json": "Machine-readable office and department capability matrix for future UI, docs, and launch-gate checks.",
        "docs/DEPLOYMENT_MODES.md": "Separates public demo, local real use, and future SaaS deployment.",
        "docs/STATIC_SHOWCASE_DEPLOYMENT.md": "Explains how to publish the no-key static showcase.",
        "docs/PUBLIC_RELEASE_HANDOFF.md": "Explains what evidence must exist before sharing the project publicly.",
    }
    return reasons.get(path, "Required first-run file.")


def _common_first_run_failures() -> list[dict[str, Any]]:
    return [
        {
            "id": "missing_dependencies",
            "symptom": "命令启动后提示 ModuleNotFoundError、fastapi/docx/PIL 等模块不存在。",
            "likely_cause": "第一次从 GitHub 下载后还没有安装 requirements.txt 里的 Python 依赖。",
            "check_command": "python -m pip show fastapi python-docx pillow",
            "recovery_action": "先运行 `python -m pip install -r requirements.txt`，再重新执行 first-run 或 doctor 检查。",
            "requires_api_key": False,
        },
        {
            "id": "missing_local_config",
            "symptom": "本地真实模式无法保存模型，或者 doctor 提示配置文件缺失。",
            "likely_cause": "还没有把 config.example.yaml 复制成本机私有的 config.yaml。",
            "check_command": "Test-Path config.yaml",
            "recovery_action": "运行 `Copy-Item config.example.yaml config.yaml`，只在本机 config.yaml 或环境变量里填写 Key。",
            "requires_api_key": False,
        },
        {
            "id": "model_preflight_blocked",
            "symptom": "工作台能打开，但故事、资产、生图或视觉质检被启动检查拦住。",
            "likely_cause": "对应部门缺少文本模型、图片生成模型或视觉理解模型配置，或者 Key/模型名填错。",
            "check_command": "python scripts/doctor.py --format markdown",
            "recovery_action": "到模型页面逐个点击测试按钮；文本部门先跑通最小流程，再补工部生图模型和刑部视觉模型。",
            "requires_api_key": True,
        },
        {
            "id": "port_in_use",
            "symptom": "运行 python run.py --port 8080 后提示地址已占用，或浏览器打开的是旧页面。",
            "likely_cause": "8080 端口已经有旧服务在运行，或者浏览器缓存仍指向旧进程。",
            "check_command": "netstat -ano | findstr :8080",
            "recovery_action": "关闭旧进程，或改用 `python run.py --port 8081` 后打开新的 localhost 地址。",
            "requires_api_key": False,
        },
        {
            "id": "codex_windows_sandbox_setup_failed",
            "symptom": "Codex 桌面端反复弹出 codex-windows-sandbox-setup.exe，提示“找不到指定的模块”。",
            "likely_cause": "这是 Codex Windows 应用自带沙箱初始化组件启动失败，通常是应用更新不完整、安装包损坏或系统运行库缺失；它不是三个臭皮匠项目代码报错。",
            "check_command": "重新打开 Codex；如果仍弹窗，更新或重装 Codex Windows 应用。",
            "recovery_action": "先完全退出并重启 Codex。仍失败时更新或重装 Codex；项目本身可以继续用本地命令运行，公开演示和 release 验证不依赖这个弹窗里的 setup 程序。",
            "requires_api_key": False,
        },
        {
            "id": "public_deploy_real_mode",
            "symptom": "准备放到 Vercel/个人网站时，不确定是否会暴露作者自己的 API Key。",
            "likely_cause": "把本地真实模式当成公开 SaaS 部署，或者把 config.yaml/.env/运行产物带进公开构建。",
            "check_command": "python scripts/check_no_secrets.py",
            "recovery_action": f"运行 `{STATIC_EXPORT_COMMAND}` 导出 `dist/public-showcase`，再用 `{STATIC_SHOWCASE_COMMAND}` 验证；公开部署只上传这个静态目录，真实生产继续由使用者本地填写自己的 Key。",
            "requires_api_key": False,
        },
        {
            "id": "incomplete_handoff_download",
            "symptom": "历史页或公开样例能看到项目，但下载的 Word、manifest、图片记录、提示词包或 trace JSON 不完整。",
            "likely_cause": "产物没有完成归档，旧版 handoff 缺少 manifest v3，或者只下载了 Word 画布而没有下载机器可读引用清单。",
            "check_command": HANDOFF_AUDIT_COMMAND,
            "recovery_action": f"先运行 `{HANDOFF_AUDIT_COMMAND}` 清点本地输出；公开样例缺文件时重新运行 `{STATIC_EXPORT_COMMAND}` 和 `{STATIC_SHOWCASE_COMMAND}`；真实项目缺文件时回到历史页下载完整制片包，或按声明报告里的 recovery action 重新生成缺失阶段。",
            "requires_api_key": False,
        },
    ]


def _public_demo_path() -> dict[str, Any]:
    return {
        "id": "public_demo",
        "title": "公开无 Key 演示",
        "status": "ready",
        "requires_api_key": False,
        "who_it_is_for": "面试官、作品集访客、第一次看项目的人。",
        "next_action": f"Run `{PUBLIC_DEMO_COMMAND}`, then export the backend-free site with `{STATIC_EXPORT_COMMAND}`.",
        "steps": [
            f"Run `{PUBLIC_DEMO_COMMAND}` to verify demo endpoints and downloads.",
            f"Run `{STATIC_EXPORT_COMMAND}` and `{STATIC_SHOWCASE_COMMAND}` to build a deployable portfolio site.",
            f"Run `{DOWNSTREAM_HANDOFF_COMMAND}` to verify the AI comic sample can be handed to downstream video production.",
            f"Start the local app with `{SERVER_COMMAND}` if you want to browse the UI.",
            "Open the office hall and choose the no-key demo entry for AI comic production or research.",
            "Download the sample deliverables and use the reading guide to check what each file proves.",
        ],
        "deliverable_reading_guide": [
            {
                "file": "AI 漫剧 Word 制片画布",
                "uri": "/api/demo/comic-production/files/word_canvas.docx",
                "look_for": "故事、视觉母版、人物/道具/场景资产、镜头提示词和下游执行清单是否在同一份画布里串起来。",
                "proves": "公开演示不是聊天文本截图，而是可下载、可复核、可继续交给下游工具的制片包。",
            },
            {
                "file": "AI 漫剧 handoff manifest",
                "uri": "/api/demo/comic-production/files/handoff_manifest.json",
                "look_for": "story_version、style_version、asset_id、image_id、shot_id、首帧参考和 production_lineage。",
                "proves": "资产、图片、镜头、提示词和 Word 画布之间有引用链路，后续可以追溯和恢复。",
            },
            {
                "file": "AI 漫剧资产规格矩阵",
                "uri": "/api/demo/public-showcase",
                "look_for": "portfolio_embed.asset_requirement_matrix 中的人物 three_view、expression_sheet，道具 turnaround，场景 wide、top_down，以及 clean_background_required。",
                "proves": "公开样例不仅有 Word 和 manifest，还声明了下游继续制片前必须具备的基础资产图片标准。",
            },
            {
                "file": "研究办公室阶段报告",
                "uri": "/api/demo/research/files/report.md",
                "look_for": "报告结论、来源清单、数据表、截图计划和证据缺口是否分开呈现。",
                "proves": "研究办公室不会伪装成全自动抓取平台；它会把已确认资料和待补证据分开交付。",
            },
            {
                "file": "研究办公室证据清单",
                "uri": "/api/demo/research/files/evidence_manifest.json",
                "look_for": "来源、数据、截图计划、缺口和后续人工确认项。",
                "proves": "调研样例保留证据边界，适合演示 staged delivery 而不是虚假完整自动化。",
            },
            {
                "file": "AI 漫剧真实生产声明报告",
                "uri": "/api/demo/comic-production/claim-report",
                "look_for": "claim_level、quality_claim、can_claim_real_quality、allowed_public_claims 和 forbidden_public_claims。",
                "proves": "公开样例只能声明结构、谱系和交付链路通过，不能把固定样例冒充真实模型画质已验证。",
            },
            {
                "file": "研究办公室阶段性交付声明",
                "uri": "/api/demo/research/claim-report",
                "look_for": "claim_level、can_claim_full_automation、allowed_public_claims、forbidden_public_claims 和 claim_upgrade_checklist。",
                "proves": "研究办公室能公开展示阶段性交付能力，但不能把固定样例、待补截图或权限缺口说成全自动平台采集。",
            },
        ],
        "evidence": [
            "/api/demo/public-showcase",
            "/api/demo/comic-production/files/word_canvas.docx",
            "/api/demo/comic-production/files/handoff_manifest.json",
            "/api/demo/research/files/report.md",
            "/api/demo/research/files/evidence_manifest.json",
            "/api/demo/research/claim-report",
            "dist/public-showcase/index.html",
            "docs/STATIC_SHOWCASE_DEPLOYMENT.md",
            "docs/COMIC_DOWNSTREAM_HANDOFF.md",
        ],
    }


def _local_real_use_path(doctor: dict[str, Any], local_ready: bool) -> dict[str, Any]:
    blocking = list(doctor.get("system", {}).get("blocking_reasons") or [])
    blocking.extend(doctor.get("office", {}).get("blocking_reasons") or [])
    real = doctor.get("real_production") or {}
    if real.get("status") not in {"ready_for_real_run", ""}:
        blocking.append(f"real_production={real.get('status')}")
    return {
        "id": "local_real_use",
        "title": "本地真实使用",
        "status": "ready" if local_ready else "needs_user_action",
        "requires_api_key": True,
        "who_it_is_for": "想用自己的模型 Key 生成真实报告或 AI 漫剧制片包的人。",
        "next_action": doctor.get("next_action") or "Run doctor, then fill missing local model configuration.",
        "steps": [
            "Copy config.example.yaml to config.yaml if config.yaml does not exist.",
            "Put API Key values in environment variables or local config.yaml, never in committed files.",
            f"Run `{LOCAL_DOCTOR_COMMAND}` and fix every blocked item it reports.",
            "Check the doctor section `真实生产前检查`; only start full AI comic production when it says `ready_for_real_run`.",
            f"Start the app with `{SERVER_COMMAND}` and test each department from the model page.",
            "After a real run finishes, download the Word canvas, handoff manifest, prompt package, image records, and trace JSON from History.",
            f"Run `{HANDOFF_AUDIT_COMMAND}` to verify the output package is visible and traceable.",
            f"Run `{REAL_CLAIM_COMMAND}` and `{PRODUCTION_BENCHMARK_COMMAND}` before claiming production quality.",
        ],
        "model_setup_ladder": [
            {
                "level": "no_key_demo",
                "title": "公开无 Key 演示",
                "required_models": [],
                "can_do": "查看固定样例、下载七份交付物、阅读 quick-start 和安全边界。",
                "ready_when": f"`{PUBLIC_DEMO_COMMAND}` 和 `{STATIC_SHOWCASE_COMMAND}` 通过。",
            },
            {
                "level": "minimum_text",
                "title": "最小可跑配置",
                "required_models": ["中书省文本模型", "门下省文本模型", "兵部文本模型", "户部文本模型", "礼部文本模型"],
                "can_do": "聊故事、锁定剧本方向、拆资产、生成镜头和提示词草案。",
                "ready_when": "模型页面的文本部门测试通过，doctor 不再提示核心文本模型缺失。",
            },
            {
                "level": "full_comic_production",
                "title": "完整制片配置",
                "required_models": ["工部生图模型", "刑部视觉理解模型"],
                "can_do": "生成基础资产图、执行视觉质检、输出完整 Word 制片画布和 handoff manifest。",
                "ready_when": "doctor 的 `真实生产前检查` 显示 ready_for_real_run，且工部/刑部测试通过。",
            },
        ],
        "evidence": [
            f"doctor.status={doctor.get('status', '')}",
            f"system.status={doctor.get('system', {}).get('status', '')}",
            f"comic_production.status={doctor.get('office', {}).get('status', '')}",
            f"real_production.status={real.get('status', '')}",
            f"real_production.full={real.get('can_start_full_production')}",
        ],
        "post_run_validation": [
            {
                "name": "交付物清点",
                "command": HANDOFF_AUDIT_COMMAND,
                "pass_when": "Word canvas、handoff manifest、prompt package、image records 和 trace JSON 都能在输出目录或历史页找到。",
            },
            {
                "name": "真实生产声明",
                "command": REAL_CLAIM_COMMAND,
                "pass_when": "`can_claim_real_quality=True`，并且声明报告没有把 fixture 或缺图产物当成真实画质证据。",
            },
            {
                "name": "制片质量基准",
                "command": PRODUCTION_BENCHMARK_COMMAND,
                "pass_when": "`production_quality_verified` 或等价通过状态，且故事、资产、图片、镜头、提示词和 Word 引用链路互相对得上。",
            },
        ],
        "blocking_reasons": blocking,
    }


def _developer_extension_path(product: dict[str, Any]) -> dict[str, Any]:
    checks = {item.get("id"): item.get("status") for item in product.get("checks", [])}
    extension_ready = all(
        checks.get(item) == "passed"
        for item in ["office_protocols", "office_isolation_contract", "office_launch_gate_audit", "agent_output_schema_gate"]
    )
    return {
        "id": "developer_extension",
        "title": "开发者扩展新办公室",
        "status": "ready" if extension_ready else "needs_user_action",
        "requires_api_key": False,
        "who_it_is_for": "想新增短视频、电商、小说或技术项目办公室的开发者。",
        "next_action": "Use the office protocol first; do not copy a one-off route into production.",
        "steps": [
            "Read /api/offices/protocols and src/offices.py before adding a new office.",
            f"Run `{OFFICE_ISOLATION_COMMAND}` after touching model config, workspaces, artifacts, or history.",
            f"Run `{PRODUCT_READINESS_COMMAND}` and keep launch gates evidence-linked.",
        ],
        "evidence": [
            f"office_protocols={checks.get('office_protocols', '')}",
            f"office_isolation_contract={checks.get('office_isolation_contract', '')}",
            f"office_launch_gate_audit={checks.get('office_launch_gate_audit', '')}",
            f"agent_output_schema_gate={checks.get('agent_output_schema_gate', '')}",
        ],
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First Run Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Mode: `{payload.get('mode')}`",
        f"Safe for public repo: `{payload.get('safe_for_public_repo')}`",
        "",
        "## Recommended Order",
        "",
    ]
    for index, path_id in enumerate(payload.get("recommended_order", []), start=1):
        lines.append(f"{index}. `{path_id}`")
    checklist = payload.get("github_download_checklist") or {}
    lines.extend(
        [
            "",
            "## GitHub Download Checklist",
            "",
            f"Status: `{checklist.get('status')}`",
            f"Expected public files: `{checklist.get('present_public_file_count')}/{checklist.get('expected_public_file_count')}`",
            "",
            "### Expected Public Files",
            "",
        ]
    )
    for item in checklist.get("expected_public_files", []):
        lines.append(f"- `{item.get('path')}`: {item.get('status')} - {item.get('why_it_matters')}")
    lines.extend(["", "### Never Commit", ""])
    for path in checklist.get("private_paths_never_commit", []):
        lines.append(f"- `{path}`")
    lines.extend(["", "### First Commands", ""])
    for item in checklist.get("first_commands", []):
        lines.append(f"- {item.get('name')}: `{item.get('command')}` - {item.get('proves')}")
    lines.extend(["", "### Before Public Sharing", ""])
    for command in checklist.get("before_public_sharing", []):
        lines.append(f"- `{command}`")
    lines.extend(["", "## Deployment Mode Matrix", ""])
    for mode in payload.get("deployment_mode_matrix", []):
        lines.extend([
            f"### {mode.get('id')} - {mode.get('title')}",
            "",
            f"- Status: `{mode.get('status')}`",
            f"- Requires API Key: `{mode.get('requires_api_key')}`",
            f"- Allows real model calls: `{mode.get('allows_real_model_calls')}`",
            f"- Allows workspace writes: `{mode.get('allows_workspace_writes')}`",
            f"- Verification: `{mode.get('verification')}`",
            f"- Who can use: {mode.get('who_can_use')}",
            "- Allowed:",
        ])
        for allowed in mode.get("allowed", []):
            lines.append(f"  - {allowed}")
        lines.append("- Forbidden:")
        for forbidden in mode.get("forbidden", []):
            lines.append(f"  - {forbidden}")
    lines.extend(["", "## Paths", ""])
    for item in payload.get("paths", []):
        lines.extend([
            f"### {item.get('id')} - {item.get('title')}",
            "",
            f"- Status: `{item.get('status')}`",
            f"- Requires API Key: `{item.get('requires_api_key')}`",
            f"- For: {item.get('who_it_is_for')}",
            f"- Next action: {item.get('next_action')}",
            "- Steps:",
        ])
        for step in item.get("steps", []):
            lines.append(f"  - {step}")
        lines.append("- Evidence:")
        for evidence in item.get("evidence", []):
            lines.append(f"  - `{evidence}`")
        if item.get("deliverable_reading_guide"):
            lines.append("- Deliverable reading guide:")
            for guide in item.get("deliverable_reading_guide", []):
                lines.append(
                    f"  - `{guide.get('file')}` ({guide.get('uri')}): "
                    f"{guide.get('look_for')} 证明：{guide.get('proves')}"
                )
        if item.get("model_setup_ladder"):
            lines.append("- Model setup ladder:")
            for ladder in item.get("model_setup_ladder", []):
                required_models = ", ".join(ladder.get("required_models") or []) or "不需要模型"
                lines.append(
                    f"  - `{ladder.get('level')}` {ladder.get('title')}: "
                    f"需要 {required_models}；能做：{ladder.get('can_do')}；验收：{ladder.get('ready_when')}"
                )
        if item.get("post_run_validation"):
            lines.append("- Post-run validation:")
            for validation in item.get("post_run_validation", []):
                lines.append(
                    f"  - {validation.get('name')}: `{validation.get('command')}`；"
                    f"通过标准：{validation.get('pass_when')}"
                )
        if item.get("blocking_reasons"):
            lines.append("- Blocking reasons:")
            for reason in item.get("blocking_reasons", []):
                lines.append(f"  - {reason}")
        lines.append("")
    lines.extend(["## Safety Boundaries", ""])
    for boundary in payload.get("safety_boundaries", []):
        lines.append(f"- {boundary}")
    lines.extend(["", "## Common First-run Failures", ""])
    for item in payload.get("common_first_run_failures", []):
        lines.extend(
            [
                f"### {item.get('id')}",
                "",
                f"- Symptom: {item.get('symptom')}",
                f"- Likely cause: {item.get('likely_cause')}",
                f"- Check: `{item.get('check_command')}`",
                f"- Recovery: {item.get('recovery_action')}",
                f"- Requires API Key: `{item.get('requires_api_key')}`",
                "",
            ]
        )
    lines.extend(["", "## Commands", ""])
    for label, command in payload.get("commands", {}).items():
        lines.append(f"- `{label}`: `{command}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Verify first-run reproducibility guidance.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    payload = build_first_run_readiness(REPO_ROOT)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
