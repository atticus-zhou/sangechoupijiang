"""三个臭皮匠 Web 应用 — FastAPI 后端"""

from __future__ import annotations

import asyncio
import base64
import uuid
import json
import os
import re
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, UploadFile, File, Form, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel, Field

from src.config_manager import config_manager
from src.offices import audit_office_launch_gates, get_office, list_office_creation_template, list_office_extension_blueprint, list_office_protocols, list_offices
from src.comic_artifacts import build_comic_artifacts
from src.comic_office.production_handoff import build_production_handoff_artifacts
from src.comic_office.production_chain import build_production_chain_state, format_production_chain_state
from src.comic_office import (
    advance_comic_cabinet_session,
    advance_comic_cabinet_session_llm,
    build_confirmed_script,
    build_comic_brief,
    build_comic_result,
    build_comic_script_preview,
    enhance_comic_prompts_llm,
    format_confirmed_script,
    start_comic_cabinet_session,
    start_comic_cabinet_session_llm,
    validate_confirmed_script_session,
)
from src.comic_word_canvas import build_comic_word_canvas
from src.comic_office.v2.asset_manifest import asset_manifest_from_dict, asset_manifest_review_view
from src.comic_office.v2.asset_planner import AssetPlanningError, plan_asset_manifest
from src.comic_office.v2.contracts import ContractValidationError, contract_bundle_from_dict
from src.comic_office.v2.delivery import DeliveryValidationError, build_delivery_from_v2
from src.comic_office.v2.fixture_flow import (
    fixture_contract_bundle,
    fixture_image_production,
    fixture_initial_manifest,
    fixture_mode_enabled,
    fixture_prompt_package,
    fixture_revised_manifest,
)
from src.comic_office.v2.planner import PlannerError, plan_contract, revise_visual_bible
from src.comic_office.v2.pipeline import ComicProductionV2, not_started_state
from src.comic_office.v2.claim_report import claim_level_from_benchmark, claim_upgrade_checklist
from src.comic_office.v2.production import (
    ProductionError,
    direct_asset_prompts,
    direct_shot_cards,
    image_production_result_from_dict,
    produce_asset_images,
    prompt_package_from_dict,
)
from src.comic_office.v2.prompt_quality import audit_prompt_package
from src.comic_office.v2.production_benchmark import audit_handoff_manifest
from src.research_artifacts import build_research_artifacts
from src.research_quality import assess_research_package
from src.evidence_artifacts import build_evidence_artifacts
from src.research_office import (
    build_evidence_fallback_result,
    format_workspace_evidence_context,
    needs_platform_evidence,
    research_capture_keyword,
)
from src.llm.providers import LLMFactory
from src.comic_quality import build_revised_prompt, review_comic_image, should_retry_image
from src.image_generation import (
    ImageGenerationError,
    generate_doubao_image,
    is_image_generation_config,
)
from src.model_connectivity import AGENT_IDS, probe_model_connectivity
from src.office_runtime import build_office_runtime_status
from src.office_preflight import build_office_preflight
from src.product_readiness import audit_comic_production_readiness, audit_comic_real_production_start_readiness
from src.system_preflight import build_system_preflight
from scripts.audit_comic_v2_handoffs import audit_handoff_inventory
from scripts.verify_comic_real_production_claim import build_claim_report
from src.browser_capture import (
    BrowserCaptureError,
    capture_feigua_plan,
    browser_status,
    capture_url,
    ensure_browser,
    open_login_page,
    feigua_login_state,
    wait_for_feigua_login,
)
from src.data.schemas import (
    SystemState,
    AgentId,
    TaskPlan,
)

# 延迟导入避免循环引用
def _get_engine(office_id: str = ""):
    from src.main import SanShengLiuBu
    return SanShengLiuBu(office_id=office_id)

# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="三个臭皮匠 · 多 Agent 办公室",
    description="项目型多 Agent 办公室平台，内部由协作调度框架驱动。",
    version="1.0.0",
)

# 活跃的 WebSocket 连接
active_ws: dict[str, list[WebSocket]] = {}  # task_id → [ws, ...]
court_ws: list[WebSocket] = []  # 朝堂报告的 WebSocket 订阅者
AGENT_WORKFLOW_TIMEOUT_SECONDS = 420
APP_BASE_DIR = Path(__file__).parent.parent.parent


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_api():
    """Avoid noisy browser 404s in local demos when no favicon asset is bundled."""
    return Response(status_code=204)


@contextmanager
def _demo_delivery_lock(lock_path: Path):
    """Serialize deterministic demo delivery writes across local verifier processes."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        if lock_file.tell() == 0:
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@app.on_event("startup")
async def mark_orphaned_background_tasks_on_startup():
    """Expose tasks lost with the previous Python process instead of leaving them queued."""
    reason = "server restarted before the in-memory background task finished"
    changed = config_manager.mark_interrupted_task_runs(reason)
    if changed:
        print(f"[startup] Marked {changed} orphaned background task(s) as interrupted.")


# ============================================================
# Pydantic 模型
# ============================================================

class TaskRequest(BaseModel):
    user_request: str
    template_id: Optional[str] = None
    office_id: Optional[str] = "research"
    workspace_id: Optional[str] = None

class ModelConfigUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

class PromptUpdate(BaseModel):
    text: str

class TemplateCreate(BaseModel):
    id: str
    name: str
    description: str = ""
    default_prompt: str = ""

class WorkspaceCreate(BaseModel):
    title: str
    brief: str = ""
    office_id: str = "research"

class ArtifactCreate(BaseModel):
    artifact_type: str
    title: str
    uri: str = ""
    content: str = ""
    metadata: dict = Field(default_factory=dict)
    task_id: str = ""


class EvidenceExtractRequest(BaseModel):
    agent_id: str = "hubu"
    instruction: str = ""


class EvidenceSyncRequest(BaseModel):
    force: bool = False


class ComicImageRegenerateRequest(BaseModel):
    instruction: str = ""


class ComicBriefRequest(BaseModel):
    idea: str
    office_id: str = "comic_production"
    genre: str = ""
    length: str = ""
    platform: str = ""
    visual_style: str = ""
    extra: str = ""


class ComicScriptPreviewRequest(ComicBriefRequest):
    creative_brief: dict = Field(default_factory=dict)
    user_answers: str = ""


class ComicCabinetTurnRequest(ComicBriefRequest):
    workspace_id: str = ""
    user_message: str = ""
    session: dict = Field(default_factory=dict)


class ComicConfirmScriptRequest(BaseModel):
    workspace_id: str
    office_id: str = "comic_production"
    session: dict = Field(default_factory=dict)
    confirmation_notes: str = ""


class ComicConfirmAndStartRequest(ComicConfirmScriptRequest):
    user_request: str = ""
    template_id: Optional[str] = None


class ComicAssetReviewDecisionRequest(BaseModel):
    status: str = "approved"
    reviewer_notes: str = ""


class ComicV2StartRequest(BaseModel):
    source_story: str
    planner_payload: dict = Field(default_factory=dict)


class ComicV2RevisionRequest(BaseModel):
    revision_request: str


class ComicV2VisualOverrideRequest(BaseModel):
    reason: str


class ComicV2QualityRecoveryRequest(BaseModel):
    action: str = ""


class BrowserStartRequest(BaseModel):
    url: str = "https://dy3.feigua.cn/"


class UrlCaptureRequest(BaseModel):
    url: str
    title: str = ""
    note: str = ""
    wait_seconds: float = 5
    full_page: bool = True


class FeiguaCaptureRequest(BaseModel):
    keyword: str
    wait_seconds: float = 6
    limit: int = 4


ALLOWED_EVIDENCE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

COMIC_OFFICE_IDS = {"comic", "comic_production"}


def _normalize_comic_office_id(office_id: str | None) -> str:
    office = get_office(office_id or "comic_production")
    if office.id not in COMIC_OFFICE_IDS:
        raise _comic_legacy_http_error(
            400,
            department="尚书省",
            reason=f"不支持的漫剧办公室：{office_id}。",
            impact="系统无法确定要使用哪个办公室的模型配置、工作区和历史记录。",
            next_action="请选择 comic 或 comic_production；当前默认建议使用 AI 漫剧制片办公室。",
            stage="office_routing",
        )
    return office.id


def _is_comic_office_id(office_id: str | None) -> bool:
    return (office_id or "") in COMIC_OFFICE_IDS


# ============================================================
# 页面路由
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """主页面"""
    static_dir = Path(__file__).parent / "static"
    return (static_dir / "index.html").read_text(encoding="utf-8")


# ============================================================
# 办公室 / 工作空间 API
# ============================================================

@app.get("/api/offices")
async def get_offices():
    """List available office profiles."""
    return {"offices": list_offices()}


@app.get("/api/offices/protocols")
async def get_office_protocols_api():
    """List product contracts every office must expose before it can scale."""
    return {
        "protocols": list_office_protocols(),
        "creation_template": list_office_creation_template(),
        "extension_blueprint": list_office_extension_blueprint(),
    }


@app.get("/api/offices/{office_id}")
async def get_office_profile(office_id: str):
    """Get one office profile."""
    return get_office(office_id).to_dict()


@app.get("/api/offices/{office_id}/preflight")
async def get_office_preflight_api(office_id: str):
    """Return static readiness checks for an office without calling providers."""
    return build_office_preflight(
        office_id,
        config_manager.get_model_config,
        base_dir=APP_BASE_DIR,
    )


@app.get("/api/offices/{office_id}/launch-gates")
async def get_office_launch_gates_api(office_id: str):
    """Return the productization launch-gate audit for an office."""
    return audit_office_launch_gates(office_id)


@app.get("/api/offices/{office_id}/readiness")
async def get_office_readiness_api(office_id: str):
    """Return product-level readiness evidence for an office."""
    normalized = "comic_production" if office_id == "comic" else office_id
    if normalized != "comic_production":
        return {
            "office_id": normalized,
            "mode": "real_product_with_no_key_demo",
            "status": "not_applicable",
            "summary": "当前只有 AI 漫剧制片办公室接入了产品级 readiness 审计。",
            "checks": [],
        }
    return audit_comic_production_readiness(APP_BASE_DIR)


@app.get("/api/offices/{office_id}/real-production-readiness")
async def get_office_real_production_readiness_api(office_id: str):
    """Return the current local readiness to start a real production run."""
    normalized = "comic_production" if office_id == "comic" else office_id
    if normalized != "comic_production":
        return {
            "office_id": normalized,
            "mode": "real_production_start_readiness",
            "status": "not_applicable",
            "summary": "当前只有 AI 漫剧制片办公室接入了真实生产前检查。",
            "can_start_full_production": False,
            "can_start_limited_planning": False,
            "calls_real_models": False,
            "requires_api_key_to_check": False,
            "writes_workspace": False,
            "required_capabilities": [],
            "handoff_inventory": {},
            "operator_checklist": [],
        }
    return audit_comic_real_production_start_readiness(
        config_manager.get_model_config,
        base_dir=APP_BASE_DIR,
    )


@app.get("/api/system/preflight")
async def get_system_preflight_api():
    """Return local startup checks without calling external providers."""
    return build_system_preflight(config_manager, base_dir=APP_BASE_DIR)


@app.get("/api/demo/comic-production")
async def get_comic_production_demo_api():
    """Return a fixed no-key demo package without touching live model or workspace state."""
    fixture_path = APP_BASE_DIR / "tests" / "fixtures" / "comic_v2_sample.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    story = payload.get("source_story", "")
    assets = payload.get("assets") or []
    shots = payload.get("shots") or []
    planner = payload.get("planner_payload") or {}
    demo_delivery = _ensure_comic_production_demo_delivery()
    quality_benchmark = _comic_v2_handoff_quality_benchmark(demo_delivery["handoff_manifest"])
    return {
        "mode": "no_key_demo",
        "office_id": "comic_production",
        "title": planner.get("title") or "AI 漫剧制片办公室固定样例",
        "summary": "固定样例演示：展示从故事到资产、镜头、提示词和交付物的生产链，不消耗 API Key。",
        "uses_real_models": False,
        "api_key_required": False,
        "calls_real_models": False,
        "requires_api_key": False,
        "writes_workspace": False,
        "viewer_path": [
            {
                "title": "先看故事如何变成生产合同",
                "body": "这个样例从完整故事出发，展示内阁确认故事后，三省六部如何进入资产、镜头和交付生产。",
                "focus": "故事预览、生产流程、人工确认节点",
            },
            {
                "title": "再看资产和镜头如何被引用",
                "body": "人物、道具、场景和镜头不再是散装文本，而是带有 ID、用途和引用关系的生产对象。",
                "focus": "资产样例、镜头样例、引用链路",
            },
            {
                "title": "最后下载 Word 画布和引用清单",
                "body": "交付物可以下载；引用清单同时展示五维质量分数，并明确固定样例只验证结构、不冒充真实模型画质。",
                "focus": "Word 制片画布、handoff manifest、质量基准",
            },
        ],
        "proof_points": [
            "不需要 API Key 就能安全展示完整流程。",
            "Word 制片画布和引用清单可以直接下载。",
            "资产、镜头、提示词和交付物之间保留引用链路。",
            "下游视频平台接手前所需的人物三视图、场景空间图、镜头视频包和失败重试策略都有独立验证命令覆盖。",
            "质量基准明确区分 demo_structure_verified 和 production_quality_verified，不把占位图冒充真实画质。",
        ],
        "quality_benchmark": quality_benchmark,
        "source_story_preview": story[:360],
        "asset_count": len(assets),
        "shot_count": len(shots),
        "stages": [
            {"id": "story", "title": "故事确认", "owner": "内阁 / 中书省", "status": "completed"},
            {"id": "visual_bible", "title": "视觉母版", "owner": "中书省 / 门下省", "status": "completed"},
            {"id": "assets", "title": "资产拆解", "owner": "户部 / 门下省", "status": "completed"},
            {"id": "prompts", "title": "镜头提示词", "owner": "兵部", "status": "completed"},
            {"id": "delivery", "title": "Word 制片画布", "owner": "礼部 / 刑部", "status": "completed"},
        ],
        "quality_gates": [
            {
                "id": "no_key_read_only",
                "title": "无 Key 只读演示",
                "status": "passed",
                "evidence": "不读取模型配置，不创建真实工作区，不消耗作者 API Key。",
            },
            {
                "id": "downloadable_delivery",
                "title": "可下载交付物",
                "status": "passed",
                "evidence": "提供 Word 制片画布和资产/镜头引用清单下载。",
            },
            {
                "id": "reference_chain",
                "title": "资产引用链路",
                "status": "passed",
                "evidence": "样例展示资产、镜头、提示词和交付物之间的引用关系。",
            },
            {
                "id": "downstream_handoff",
                "title": "下游交接门禁",
                "status": "passed",
                "evidence": "verify_comic_v2_downstream_handoff.py 检查人物三视图、道具参考图、场景广角/俯视图、镜头视频包、验收标准和失败重试策略。",
            },
            {
                "id": "honest_quality_claim",
                "title": "诚实的质量声明",
                "status": "passed" if quality_benchmark.get("status") == "demo_structure_verified" else "failed",
                "evidence": (
                    f"固定样例质量分 {quality_benchmark.get('package_quality_score', 0)}/100；"
                    "production_quality_verified=False，只证明流程与引用结构。"
                ),
            },
        ],
        "assets": [
            {
                "asset_id": item.get("asset_id", ""),
                "name": item.get("name", ""),
                "asset_type": item.get("asset_type", ""),
                "purpose": item.get("purpose", ""),
            }
            for item in assets[:6]
        ],
        "shots": [
            {
                "shot_id": item.get("shot_id", ""),
                "story_beat": item.get("story_beat", ""),
                "reference_asset_ids": item.get("reference_asset_ids") or [],
            }
            for item in shots[:6]
        ],
        "artifacts": [
            {
                "type": "word_canvas",
                "title": "样例 Word 制片画布",
                "status": "downloadable",
                "uri": "/api/demo/comic-production/files/word_canvas.docx",
            },
            {
                "type": "handoff_manifest",
                "title": "资产与镜头引用清单",
                "status": "downloadable",
                "uri": "/api/demo/comic-production/files/handoff_manifest.json",
            },
            {
                "type": "downstream_handoff_gate",
                "title": "下游交接门禁说明",
                "status": "documented",
                "uri": "docs/COMIC_DOWNSTREAM_HANDOFF.md",
            },
            {"type": "prompt_package", "title": "图片与视频提示词包", "status": "available_in_fixture"},
        ],
    }


@app.get("/api/demo/comic-production/handoff-inventory")
async def get_comic_production_handoff_inventory_demo_api():
    """Return a no-key inventory of generated comic V2 handoff manifests."""
    inventory = audit_handoff_inventory([APP_BASE_DIR / "output"])
    public_items = []
    for item in inventory.get("manifests", []):
        public_items.append({
            "title": item.get("title", ""),
            "schema_version": item.get("schema_version", 0),
            "quality_claim": item.get("quality_claim", ""),
            "package_quality_score": item.get("package_quality_score", 0),
            "production_quality_verified": item.get("production_quality_verified", False),
            "visual_evidence_level": item.get("visual_evidence_level", ""),
            "word_canvas_exists": item.get("word_canvas_exists", False),
            "asset_count": item.get("asset_count", 0),
            "image_count": item.get("image_count", 0),
            "shot_count": item.get("shot_count", 0),
            "recommended_recovery": item.get("recommended_recovery", {}),
            "next_action": item.get("next_action", ""),
        })
    return {
        "mode": "no_key_demo_handoff_inventory",
        "office_id": "comic_production",
        "requires_api_key": False,
        "calls_real_models": False,
        "writes_workspace": False,
        "status": inventory.get("status", ""),
        "manifest_count": inventory.get("manifest_count", 0),
        "production_verified_count": inventory.get("production_verified_count", 0),
        "demo_only_count": inventory.get("demo_only_count", 0),
        "needs_review_count": inventory.get("needs_review_count", 0),
        "legacy_unverifiable_count": inventory.get("legacy_unverifiable_count", 0),
        "safe_public_claim": inventory.get("safe_public_claim", ""),
        "next_action": inventory.get("next_action", ""),
        "items": public_items[:20],
    }


@app.get("/api/demo/comic-production/claim-report")
async def get_comic_production_claim_report_demo_api():
    """Return the public-safe claim boundary for the fixed comic demo package."""
    delivery = _ensure_comic_production_demo_delivery()
    report = build_claim_report(delivery["handoff_manifest"])
    return _public_claim_report(report)


def _public_claim_report(report: dict) -> dict:
    evidence = report.get("evidence") or {}
    return {
        "mode": "no_key_demo_claim_report",
        "office_id": "comic_production",
        "uri": "/api/demo/comic-production/claim-report",
        "requires_api_key": False,
        "calls_real_models": False,
        "writes_workspace": False,
        "status": report.get("status", ""),
        "claim_level": report.get("claim_level", ""),
        "quality_claim": report.get("quality_claim", ""),
        "can_publicly_show": bool(report.get("can_publicly_show")),
        "can_claim_real_quality": bool(report.get("can_claim_real_quality")),
        "downstream_status": report.get("downstream_status", ""),
        "allowed_public_claims": list(report.get("allowed_public_claims") or []),
        "forbidden_public_claims": list(report.get("forbidden_public_claims") or []),
        "claim_upgrade_checklist": [
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "status": item.get("status", ""),
                "required_evidence": list(item.get("required_evidence") or []),
                "why_it_matters": item.get("why_it_matters", ""),
            }
            for item in (report.get("claim_upgrade_checklist") or [])
        ],
        "next_action": report.get("next_action", ""),
        "evidence": {
            "manifest_uri": "/api/demo/comic-production/files/handoff_manifest.json",
            "word_canvas_uri": "/api/demo/comic-production/files/word_canvas.docx",
            "package_quality_score": evidence.get("package_quality_score"),
            "visual_evidence_level": evidence.get("visual_evidence_level", ""),
            "stored_benchmark_matches": bool(evidence.get("stored_benchmark_matches")),
            "production_quality_verified": bool(evidence.get("production_quality_verified")),
        },
    }


def _ensure_comic_production_demo_delivery() -> dict[str, Path]:
    """Build deterministic demo delivery files under output/demo without workspace writes."""
    output_root = APP_BASE_DIR / "output" / "demo" / "comic-production"
    delivery_dir = output_root / "delivery"
    image_dir = output_root / "images"
    lock_path = output_root / "demo_delivery.lock"
    with _demo_delivery_lock(lock_path):
        delivery_dir.mkdir(parents=True, exist_ok=True)
        fixture = json.loads((APP_BASE_DIR / "tests" / "fixtures" / "comic_v2_sample.json").read_text(encoding="utf-8"))
        bundle = fixture_contract_bundle(fixture["source_story"])
        manifest = fixture_revised_manifest(
            bundle,
            fixture_initial_manifest(bundle),
            "公开演示固定样例需要展示完整资产清单。",
        )
        prompt_package = fixture_prompt_package(bundle, manifest)
        image_result = fixture_image_production(prompt_package, manifest, image_dir)
        delivery = build_delivery_from_v2(bundle, manifest, prompt_package, image_result, delivery_dir)
        if delivery.handoff_manifest_path is None:
            raise HTTPException(status_code=500, detail="Demo handoff manifest was not generated.")
        return {
            "word_canvas": delivery.path,
            "handoff_manifest": delivery.handoff_manifest_path,
        }

@app.get("/api/demo/comic-production/files/{filename}")
async def get_comic_production_demo_file_api(filename: str):
    """Download one deterministic demo delivery file."""
    safe_name = Path(filename).name
    delivery = _ensure_comic_production_demo_delivery()
    allowed = {
        "word_canvas.docx": delivery["word_canvas"],
        "handoff_manifest.json": delivery["handoff_manifest"],
    }
    file_path = allowed.get(safe_name)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Demo file not found.")
    media_type = (
        "application/json"
        if file_path.suffix.lower() == ".json"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(str(file_path), filename=safe_name, media_type=media_type)


@app.get("/api/demo/research")
async def get_research_demo_api():
    """Return a fixed no-key research-office demo without touching live model or workspace state."""
    fixture = _load_research_demo_fixture()
    plan = fixture.get("plan") or {}
    results = fixture.get("results") or []
    delivery = _ensure_research_demo_delivery()
    sources = _research_demo_sources(results)
    data_points = _research_demo_data_points(results)
    competitors = _research_demo_competitors(results)
    chart_suggestions = _research_demo_chart_suggestions(results)
    evidence_handoff = _research_demo_evidence_handoff()
    return {
        "mode": "no_key_demo",
        "office_id": "research",
        "title": plan.get("title") or "研究办公室固定样例",
        "summary": "固定样例演示：展示从调研目标到来源、数据点、竞品表、截图取证计划和阶段报告的工作链，不消耗 API Key。",
        "uses_real_models": False,
        "api_key_required": False,
        "writes_workspace": False,
        "viewer_path": [
            {
                "title": "先看目标如何被拆成调研任务",
                "body": "样例展示研究办公室如何从调研目标进入来源、数据、竞品和截图计划，而不是只生成一段文字。",
                "focus": "调研目标、阶段流程、部门分工",
            },
            {
                "title": "再看证据和数据是否可追溯",
                "body": "来源、数据点、竞品和截图计划都被拆成可检查对象，缺权限的数据会标记为待核验。",
                "focus": "来源清单、数据点、竞品表、截图计划",
            },
            {
                "title": "最后下载阶段报告和证据清单",
                "body": "公开演示只提供固定样例，但交付形态接近真实调研工作中的报告和证据附件。",
                "focus": "阶段报告、evidence manifest",
            },
        ],
        "proof_points": [
            "不需要 API Key 就能查看调研办公室的工作链。",
            "报告、来源、数据、竞品和截图计划互相对应。",
            "证据清单可以下载，方便复核哪些结论已验证、哪些待补。",
        ],
        "evidence_boundaries": {
            "covered_in_demo": [
                "阶段调研报告",
                "来源清单",
                "数据表",
                "竞品表",
                "截图取证计划",
                "证据 manifest",
            ],
            "requires_human_or_account": [
                "第三方平台登录和账号权限",
                "飞瓜、抖音、电商后台等受限页面截图",
                "销量、达人榜、商品榜等需要截图或来源记录才能确认的数据",
                "老板汇报前对关键截图和表格做人工复核",
            ],
            "public_demo_boundary": "公开演示只展示固定样例和证据缺口，不读取账号、不登录第三方平台、不宣称全自动会员级采集。",
        },
        "evidence_handoff": evidence_handoff,
        "deliverable_reading_guide": [
            {
                "order": 1,
                "title": "先看阶段调研报告",
                "uri": "/api/demo/research/files/report.md",
                "look_for": "结论、来源清单、数据表、截图计划和证据缺口是否分开呈现。",
                "proves": "研究办公室能交付老板可读的阶段性判断，同时不把待补截图伪装成已验证事实。",
            },
            {
                "order": 2,
                "title": "再看来源、数据与截图清单",
                "uri": "/api/demo/research/files/evidence_manifest.json",
                "look_for": "来源、数据点、竞品记录、截图计划、待人工确认项和权限缺口是否可追踪。",
                "proves": "后续补飞瓜、抖音或电商后台截图时，用户知道该补哪一页、为什么补、补完影响哪条结论。",
            },
        ],
        "objective": plan.get("objective", ""),
        "deliverable": plan.get("deliverable", ""),
        "report_preview": (fixture.get("final_report") or "")[:520],
        "calls_real_models": False,
        "requires_api_key": False,
        "source_count": len(sources),
        "data_point_count": len(data_points),
        "competitor_count": len(competitors),
        "chart_count": len(chart_suggestions),
        "stages": [
            {"id": "plan", "title": "调研目标拆解", "owner": "中书省", "status": "completed"},
            {"id": "evidence", "title": "来源与截图计划", "owner": "兵部 / 刑部", "status": "verified"},
            {"id": "tables", "title": "数据表与竞品表", "owner": "户部", "status": "completed"},
            {"id": "delivery", "title": "阶段报告", "owner": "礼部", "status": "completed"},
        ],
        "quality_gates": [
            {
                "id": "no_key_read_only",
                "title": "无 Key 只读演示",
                "status": "passed",
                "evidence": "不读取模型配置，不创建真实工作区，不消耗作者 API Key。",
            },
            {
                "id": "traceable_sources",
                "title": "来源可追溯",
                "status": "passed",
                "evidence": "样例包含来源、数据点、竞品和截图取证计划。",
            },
            {
                "id": "downloadable_delivery",
                "title": "可下载交付物",
                "status": "passed",
                "evidence": "提供阶段调研报告和证据清单下载。",
            },
        ],
        "sources": sources[:5],
        "data_points": data_points[:5],
        "competitors": competitors[:5],
        "chart_suggestions": chart_suggestions[:4],
        "artifacts": [
            {
                "type": "report_markdown",
                "title": "样例阶段调研报告",
                "status": "downloadable",
                "uri": "/api/demo/research/files/report.md",
            },
            {
                "type": "evidence_manifest",
                "title": "来源、数据与截图清单",
                "status": "downloadable",
                "uri": "/api/demo/research/files/evidence_manifest.json",
            },
            {
                "type": "research_claim",
                "title": "研究办公室阶段性交付声明",
                "status": "downloadable",
                "uri": "/api/demo/research/claim-report",
            },
        ],
    }


def _research_claim_report_from_demo(demo: dict) -> dict:
    evidence_boundaries = demo.get("evidence_boundaries") or {}
    evidence_handoff = demo.get("evidence_handoff") or []
    return {
        "status": "passed",
        "mode": "research_staged_delivery_claim",
        "office_id": "research",
        "claim_level": "staged_research_demo",
        "can_publicly_show": True,
        "can_claim_full_automation": False,
        "requires_api_key": False,
        "calls_real_models": False,
        "allowed_public_claims": [
            "这份无 Key 样例证明研究办公室可以组织阶段报告、来源、数据表、竞品表和截图计划。",
            "可以展示报告与证据清单如何把已覆盖信息和待补证据分开。",
            "可以作为面试官或访客理解研究办公室工作链的固定样例。",
        ],
        "forbidden_public_claims": [
            "不能宣称已经自动登录飞瓜、抖音、电商后台或其他第三方平台。",
            "不能宣称已经完成会员级榜单、销量、达人或商品详情截图采集。",
            "不能把待人工核验的数据、截图计划或权限缺口说成已完成证据。",
        ],
        "evidence_boundaries": evidence_boundaries,
        "evidence_handoff": evidence_handoff,
        "claim_upgrade_checklist": [
            {
                "id": "account_authorized_capture",
                "title": "使用真实账号补齐平台截图",
                "status": "missing",
                "required_evidence": ["登录后的页面截图", "截图文件名", "来源页面或页面说明", "采集时间"],
                "why_it_matters": "固定样例只能证明证据计划，不能证明受限平台页面已经采集完成。",
            },
            {
                "id": "source_verification",
                "title": "复核关键数据来源",
                "status": "missing",
                "required_evidence": ["来源 URL", "数据年份", "截图或导出表格", "人工复核记录"],
                "why_it_matters": "老板汇报需要知道关键数字来自哪里、是否过期、是否只是待核验线索。",
            },
            {
                "id": "final_report_refresh",
                "title": "补证后重新生成最终报告",
                "status": "required_after_capture",
                "required_evidence": ["更新后的 report", "更新后的 evidence manifest", "变更说明"],
                "why_it_matters": "补截图或改数据后，阶段报告不能自动继承旧结论，必须重新生成并保留变更记录。",
            },
        ],
        "next_action": "真实调研时先按 evidence_handoff 补齐账号或截图证据，再重新生成报告和证据清单。",
    }


@app.get("/api/demo/research/claim-report")
async def get_research_claim_report_demo_api():
    """Return a no-key claim boundary for the research-office public demo."""
    demo = await get_research_demo_api()
    return _research_claim_report_from_demo(demo)



def _public_showcase_downloads(demo: dict) -> list[dict]:
    downloads = []
    for item in demo.get("deliverables") or demo.get("artifacts") or []:
        uri = item.get("uri") or ""
        if item.get("status") == "downloadable" and uri.startswith("/api/demo/"):
            downloads.append({
                "type": item.get("type", "artifact"),
                "title": item.get("title", uri),
                "status": "downloadable",
                "uri": uri,
            })
    return downloads


def _public_showcase_demo(demo: dict, demo_uri: str, office_label: str, why_it_matters: str) -> dict:
    return {
        "office_id": demo.get("office_id", ""),
        "office_name": office_label,
        "title": demo.get("title", office_label),
        "summary": demo.get("summary", ""),
        "demo_uri": demo_uri,
        "viewer_path": demo.get("viewer_path", []),
        "proof_points": demo.get("proof_points", []),
        "downloads": _public_showcase_downloads(demo),
        "quality_gates": demo.get("quality_gates", []),
        "quality_benchmark": demo.get("quality_benchmark", {}),
        "why_it_matters": why_it_matters,
    }


def _public_showcase_deliverable_guidance(item_type: str) -> tuple[str, list[str]]:
    guidance = {
        "word_canvas": (
            "打开后重点看故事、资产、镜头、提示词和图片记录是否在同一份制片画布里互相对应。",
            ["包含可交给下游平台的画布结构", "能看到资产 ID、镜头 ID 和引用关系", "不是一次性聊天文本"],
        ),
        "handoff_manifest": (
            "用于开发者或下游工具复核每个资产、镜头、图片和 Word 文件来自哪一版生产链路，并查看质量基准与恢复动作。",
            ["保留故事版本和视觉母版版本", "列出资产、镜头和图片记录", "区分结构演示与真实质量验证", "支持失败后追溯和重试"],
        ),
        "report_markdown": (
            "打开后重点看调研结论、数据点、竞品表和截图计划是否分开呈现，而不是混成一段泛泛文字。",
            ["报告可读", "来源和数据有对应关系", "证据缺口被明确标注"],
        ),
        "evidence_manifest": (
            "用于复核研究办公室到底有哪些来源、数据、截图计划和待人工确认事项。",
            ["来源清单可追踪", "截图计划可执行", "未验证信息不会伪装成已验证结论"],
        ),
        "research_claim": (
            "用于判断研究办公室公开样例能说到什么程度，重点看哪些证据已覆盖、哪些必须用真实账号或人工截图补齐。",
            ["明确 staged delivery 边界", "不宣称全自动会员级采集", "给出补证后重新生成报告的动作"],
        ),
        "real_production_claim": (
            "用于判断这份公开样例到底能对外说到什么程度，重点看 claim_level、production_quality_verified 和禁止宣传的内容。",
            ["明确 demo-only 边界", "不宣称真实模型画质已验证", "给出下一步真实生产验证动作"],
        ),
    }
    return guidance.get(
        item_type,
        (
            "用于证明公开演示不是静态介绍页，而是包含可下载、可复核的真实样例产物。",
            ["可下载", "可复核", "不消耗真实 API Key"],
        ),
    )


def _public_showcase_sample_deliverables(demos: list[dict]) -> list[dict]:
    deliverables: list[dict] = []
    for demo in demos:
        for item in demo.get("downloads", []):
            reader_guidance, acceptance_signals = _public_showcase_deliverable_guidance(item.get("type", "artifact"))
            deliverables.append({
                "office_id": demo.get("office_id", ""),
                "office_name": demo.get("office_name", ""),
                "title": item.get("title", ""),
                "type": item.get("type", "artifact"),
                "uri": item.get("uri", ""),
                "status": item.get("status", "downloadable"),
                "reader_guidance": reader_guidance,
                "acceptance_signals": acceptance_signals,
            })
    return deliverables


def _public_showcase_claim_report_deliverable(claim: dict) -> dict:
    reader_guidance, acceptance_signals = _public_showcase_deliverable_guidance("real_production_claim")
    return {
        "office_id": "comic_production",
        "office_name": "AI 漫剧制片办公室",
        "title": "AI 漫剧真实生产声明报告",
        "type": "real_production_claim",
        "uri": claim.get("uri", "/api/demo/comic-production/claim-report"),
        "status": "downloadable",
        "reader_guidance": reader_guidance,
        "acceptance_signals": acceptance_signals,
        "claim_level": claim.get("claim_level", ""),
        "can_claim_real_quality": claim.get("can_claim_real_quality", False),
    }


def _public_showcase_quality_upgrade_path(claim: dict) -> dict:
    evidence = claim.get("evidence") or {}
    return {
        "title": "从公开 demo 升级到真实生产证据",
        "summary": "公开展示只证明结构和交付链路；真实画质必须在本地用使用者自己的模型 Key 重新生成图片、完成视觉质检，再更新 claim report。",
        "current_public_level": claim.get("claim_level", "demo_structure_only"),
        "current_image_evidence": evidence.get("visual_evidence_level", "fixture_only"),
        "can_claim_real_quality": bool(claim.get("can_claim_real_quality")),
        "recovery_action": "regenerate_images",
        "recovery_endpoint": "/api/workspaces/{workspace_id}/comic/v2/quality/recover",
        "trace_endpoint": "/api/tasks/{task_id}/comic-v2-trace.json",
        "preserves": ["confirmed_story", "asset_manifest", "prompt_package", "old_word_canvas", "old_handoff_manifest"],
        "rebuilds": ["image_production_evidence", "visual_review", "quality_benchmark", "claim_report"],
        "steps": [
            {
                "order": 1,
                "owner": "使用者",
                "action": "在本地模型页配置并测试文本模型、生图模型和视觉理解模型。",
                "evidence": "模型预检通过，不把 API Key 放进公开页面或 GitHub。",
                "expected": "真实生产可以开始，但公开 demo 仍保持 no-key。",
            },
            {
                "order": 2,
                "owner": "工部 / 刑部",
                "action": "按已确认故事、资产拆解和提示词包重新生成图片并完成视觉质检。",
                "evidence": "图片记录包含 provider、model、非 fixture 标记和 review pass 结果。",
                "expected": "image_production_evidence 从 fixture_only 升级为 model_reviewed。",
            },
            {
                "order": 3,
                "owner": "史部 / 礼部",
                "action": "重新生成 Word 画布、handoff manifest 和 claim report，并保留旧交付物归档。",
                "evidence": "history trace 可看到 story、asset、prompt、image、review、delivery 的版本链。",
                "expected": "只有验证通过后，claim_level 才能从 demo_structure_only 升级。",
            },
        ],
    }


def _public_showcase_portfolio_integration() -> dict:
    return {
        "title": "个人网站接入方式",
        "summary": "公开展示应只接入 no-key 静态包或 /api/demo/public-showcase 数据，不接入真实生产接口、config.yaml、用户工作区或作者 API Key。",
        "recommended_path": "static_export",
        "static_export": {
            "command": "python scripts/export_public_showcase.py",
            "verify_command": "python scripts/verify_static_public_showcase.py --format markdown",
            "source_dir": "dist/public-showcase",
            "entrypoint": "dist/public-showcase/index.html",
            "requires_backend": False,
            "requires_api_key": False,
        },
        "integration_options": [
            {
                "id": "standalone_static_site",
                "label": "独立静态展示项目",
                "target": "Vercel / Netlify / GitHub Pages",
                "copy_from": "dist/public-showcase",
                "copy_to": "站点发布根目录",
                "public_url_example": "https://your-domain.example/three-stooges/",
                "best_for": "不想影响已有个人网站构建时最稳。",
            },
            {
                "id": "personal_site_subdirectory",
                "label": "复制到个人网站子目录",
                "target": "已有个人网站仓库",
                "copy_from": "dist/public-showcase/*",
                "copy_to": "public/three-stooges/",
                "public_url_example": "/three-stooges/",
                "best_for": "个人网站已经上线，只想新增一个作品入口。",
            },
        ],
        "must_keep": [
            "index.html",
            "data.js",
            "app.js",
            "style.css",
            "assets/public-showcase-desktop.png",
            "downloads/",
            "data/comic_production_claim_report.json",
            "export-manifest.json",
        ],
        "must_not_include": [
            "config.yaml",
            ".env",
            "API Key",
            "Cookie",
            "user_data/",
            "output/",
            "browser profile",
            "real user workspace",
        ],
        "verification_commands": [
            "python scripts/export_public_showcase.py",
            "python scripts/verify_static_public_showcase.py --format markdown",
            "python scripts/verify_release_readiness.py --format markdown",
            "python scripts/check_no_secrets.py",
        ],
    }


def _public_showcase_deliverable_reading_guide() -> list[dict]:
    return [
        {
            "order": 1,
            "title": "先看 AI 漫剧 Word 制片画布",
            "uri": "/api/demo/comic-production/files/word_canvas.docx",
            "look_for": "故事、视觉母版、人物/道具/场景资产、镜头提示词和下游执行清单是否处在同一份制片包里。",
            "proves": "AI 漫剧制片办公室交付的是可下载、可复核、可继续生产的制片包，而不是聊天文本截图。",
        },
        {
            "order": 2,
            "title": "再看 AI 漫剧 handoff manifest",
            "uri": "/api/demo/comic-production/files/handoff_manifest.json",
            "look_for": "story_version、style_version、asset_id、image_id、shot_id、首帧参考、production_lineage 和 quality_benchmark 是否完整。",
            "proves": "故事、资产、图片、镜头、提示词和 Word 文件之间有引用链路；固定样例只声明结构演示通过，失败后能按责任部门追溯和恢复。",
        },
        {
            "order": 3,
            "title": "再看 AI 漫剧交付盘点",
            "uri": "/api/demo/comic-production/handoff-inventory",
            "look_for": "production_verified_count、demo_only_count、needs_review_count 和 safe_public_claim 是否说明真实质量证据边界。",
            "proves": "公开展示不会把本地样例或历史产物误标成真实模型质量通过；多份制片包可以被统一盘点和分类。",
        },
        {
            "order": 4,
            "title": "再看研究办公室阶段报告",
            "uri": "/api/demo/research/files/report.md",
            "look_for": "报告结论、来源清单、数据表、截图计划和证据缺口是否分开呈现。",
            "proves": "研究办公室展示的是 staged delivery，不把未确认信息包装成完整自动化采集结果。",
        },
        {
            "order": 5,
            "title": "最后看研究办公室证据清单",
            "uri": "/api/demo/research/files/evidence_manifest.json",
            "look_for": "来源、数据、截图计划、缺口和人工确认项是否可追踪。",
            "proves": "公开演示保留证据边界，方便访客判断哪些已确认、哪些需要真实账号或人工补证。",
        },
        {
            "order": 6,
            "title": "最后确认研究办公室声明边界",
            "uri": "/api/demo/research/claim-report",
            "look_for": "claim_level、forbidden_public_claims、evidence_boundaries 和 claim_upgrade_checklist 是否明确说明不能宣称全自动平台采集。",
            "proves": "研究办公室可以公开展示阶段性交付能力，但不会把固定样例、待补截图或权限缺口说成完整自动化调研结果。",
        },
    ]


def _public_showcase_downstream_quick_start() -> list[dict]:
    return [
        {
            "step": 1,
            "title": "确认制片画布",
            "owner": "人类制片 / 礼部",
            "input_refs": ["Word 制片画布", "handoff manifest"],
            "action": "先通读故事、视觉母版、资产表和镜头表，确认下游要拍的是同一个故事版本。",
            "output": "一份可继续生产的锁定版制片画布。",
            "acceptance": "故事版本、视觉风格、资产 ID、镜头 ID 和交付文件能互相对应。",
        },
        {
            "step": 2,
            "title": "锁定基础资产",
            "owner": "工部 / 刑部",
            "input_refs": ["人物三视图", "人物表情", "道具白底图", "场景广角图", "场景俯视图"],
            "action": "把人物、道具、场景作为基础资产先验收，不把它们当成讲故事画面来用。",
            "output": "下游视频工具可复用的资产身份证和参考图集合。",
            "acceptance": "人物与道具背景干净，场景视角齐全，画风与故事时代一致，没有现代化误入或风格漂移。",
        },
        {
            "step": 3,
            "title": "逐镜头生成视频",
            "owner": "兵部 / 下游视频工具",
            "input_refs": ["shot_id", "首帧参考图", "角色引用图", "镜头提示词"],
            "action": "按 shot_id 逐条投喂首帧、角色引用和导演式提示词，单镜头生成后再进入下一镜头。",
            "output": "每个镜头一条可复查的视频片段或失败记录。",
            "acceptance": "镜头动作、对白、构图、情绪和引用资产一致；失败镜头保留原因，不能静默跳过。",
        },
        {
            "step": 4,
            "title": "执行质量复核",
            "owner": "刑部",
            "input_refs": ["生成视频片段", "资产身份证", "镜头提示词", "负面提示词"],
            "action": "检查脸、服装、道具、时代风格、镜头动作和文字污染，标记需要重跑的镜头。",
            "output": "通过清单、重跑清单和原因说明。",
            "acceptance": "不把废片混进交付；每个失败项都能追到资产、提示词或模型输出原因。",
        },
        {
            "step": 5,
            "title": "归档交付证据",
            "owner": "史部 / 礼部",
            "input_refs": ["最终视频片段", "Word 制片画布", "handoff manifest", "质量复核表"],
            "action": "把最终片段、使用的资产版本、提示词版本和质检结论归档，方便复盘和继续迭代。",
            "output": "可交给人类剪辑或下游平台继续处理的交付包。",
            "acceptance": "后续任何人打开交付包，都知道每个镜头用了哪些人物、道具、场景、提示词和参考图。",
        },
    ]


def _public_showcase_shot_contract() -> dict:
    return {
        "title": "镜头合同可执行性",
        "summary": "AI 漫剧制片包不是只给一段视频提示词；每个镜头都必须把首帧参考图、资产引用链和导演执行参数写成机器可读合同。",
        "manifest_uri": "/api/demo/comic-production/files/handoff_manifest.json",
        "required_fields": [
            {
                "field": "first_frame_reference_image",
                "label": "首帧参考图",
                "must_include": ["image_id", "file", "asset_id"],
                "proves": "下游视频工具知道第一帧应该绑定哪张已批准图片，而不是重新猜角色或场景。",
            },
            {
                "field": "reference_asset_chain",
                "label": "资产引用链",
                "must_include": ["asset_id", "asset_type", "name"],
                "proves": "每个镜头都能机器核对引用了哪些人物、道具和场景，避免自然语言提示词和资产表脱节。",
            },
            {
                "field": "director_execution",
                "label": "导演执行合同",
                "must_include": ["action_chain", "performance_intent", "framing", "camera_movement", "lighting", "dialogue", "sound"],
                "proves": "动作、表演、景别、运镜、灯光和声音被结构化保存，失败时可以定位到具体镜头重新生成。",
            },
        ],
        "release_gate": "python scripts/verify_comic_v2_downstream_handoff.py --format markdown",
        "failure_policy": "缺少任一字段时，制片包只能停在 needs_review，不能交给 Libtv、小云雀或其他视频平台当作最终生产素材。",
    }


def _public_showcase_interview_demo_script() -> list[dict]:
    return [
        {
            "order": 1,
            "title": "先打开公开展示页，不进入真实工作台",
            "visitor_action": "点击首页「公开展示页」，先看产品定位、无 Key 标识和安全边界。",
            "product_response": "页面读取 /api/demo/public-showcase，只展示固定样例、下载物和参观路径。",
            "proof": "面试官能确认这是可公开展示的 demo-only 入口，不需要作者 API Key。",
            "boundary": "不要在公开页面填写、上传或展示真实 config.yaml、Cookie、API Key 和用户工作区。",
        },
        {
            "order": 2,
            "title": "再进入 AI 漫剧制片办公室样例",
            "visitor_action": "点击「看 AI 漫剧样例」，查看故事、资产、镜头、提示词、图片记录和交付文件。",
            "product_response": "系统展示固定制片包，并提供 Word 制片画布和 handoff manifest 下载。",
            "proof": "这个办公室的价值不是写一段故事，而是把故事拆成可交接的资产和镜头生产材料。",
            "boundary": "公开样例不调用真实模型，也不代表当前在线版允许访客消耗作者模型额度。",
        },
        {
            "order": 3,
            "title": "下载交付物做文件级验证",
            "visitor_action": "按阅读顺序下载 Word 制片画布、handoff manifest、研究报告和证据清单。",
            "product_response": "每个下载链接都来自 /api/demo，并附带阅读重点和验收信号。",
            "proof": "访客能离开页面检查文件内容，验证产品有真实交付物而不是纯 UI 演示。",
            "boundary": "样例文件只证明公开演示路径，不包含作者本地历史、真实客户数据或运行产物。",
        },
        {
            "order": 4,
            "title": "最后看 GitHub 和本地复现路径",
            "visitor_action": "打开 GitHub，按 README 先跑 doctor、public demo verifier 和 release readiness。",
            "product_response": "仓库提供无 Key 自检、模型配置说明、办公室协议、上线门禁和敏感信息扫描。",
            "proof": "开发者可以复现公开 demo，并清楚知道真实生产要在本地配置自己的模型 Key。",
            "boundary": "当前公开形态不是多用户 SaaS；真实生产、账号权限、成本控制仍应留在本地或后续服务端方案。",
        },
    ]


def _public_showcase_fast_review_route() -> list[dict]:
    return [
        {
            "order": 1,
            "title": "先确认这是安全公开页",
            "viewer_action": "看首屏的无 Key、发布状态和真实生产声明边界。",
            "proof": "页面只展示固定样例，不调用真实模型，不读取作者 API Key。",
            "next_anchor": "#claim-title",
        },
        {
            "order": 2,
            "title": "再下载 Word 制片画布",
            "viewer_action": "打开 AI 漫剧 Word 制片画布，检查故事、资产、镜头和提示词是否在同一份交付物里。",
            "proof": "产品交付的是可继续生产的文件，不是一段聊天回答。",
            "next_anchor": "#deliverables-title",
        },
        {
            "order": 3,
            "title": "然后核对 handoff manifest",
            "viewer_action": "查看 story_version、asset_id、image_id、shot_id 和 production_lineage。",
            "proof": "故事、资产、图片、镜头、提示词和 Word 画布之间有引用链路。",
            "next_anchor": "#catalog-title",
        },
        {
            "order": 4,
            "title": "最后看声明边界和复现命令",
            "viewer_action": "确认漫画和研究两个办公室哪些能公开证明、哪些还不能宣称，并看 release readiness 命令。",
            "proof": "作品集展示不会夸大成真实 SaaS 或真实模型质量验证。",
            "next_anchor": "#repro-title",
        },
    ]


def _research_demo_evidence_handoff() -> list[dict]:
    return [
        {
            "id": "platform_price_band",
            "title": "补齐平台价格带截图",
            "owner": "人类操作者 / 兵部",
            "target_evidence": "电商或内容平台商品榜单、商品详情页、价格区间截图。",
            "why_needed": "把“主流消费级价格带=待核验”升级成可引用的价格带判断。",
            "upgrades": ["数据表", "价格带图表", "开品建议"],
            "status": "pending_human_account",
        },
        {
            "id": "competitor_ranking",
            "title": "补齐 TOP 竞品和销量信号",
            "owner": "人类操作者 / 户部",
            "target_evidence": "飞瓜、抖音、电商后台或公开榜单中的 TOP 商品、品牌、销量/热度截图。",
            "why_needed": "把样例竞品从结构占位升级成可对比的竞品矩阵。",
            "upgrades": ["竞品表", "机会地图", "老板摘要"],
            "status": "pending_human_account",
        },
        {
            "id": "review_pain_points",
            "title": "补齐评论痛点截图",
            "owner": "人类操作者 / 刑部",
            "target_evidence": "商品评论、达人内容评论区、售后反馈或测评页面截图。",
            "why_needed": "验证续航、炸机、售后、图传稳定性是否真的是近期高频痛点。",
            "upgrades": ["评论痛点表", "差异化机会", "风险提示"],
            "status": "pending_human_account",
        },
    ]


def _public_showcase_reproducibility_checklist() -> list[dict]:
    return [
        {
            "order": 1,
            "title": "确认第一次运行路径",
            "command": "python scripts/verify_first_run_readiness.py --format markdown",
            "expected": "看到 public_demo、local_real_use 和 developer_extension 三条路径，说明新用户知道先跑无 Key 演示还是本地真实使用。",
            "if_fails": "先修 README、部署说明或 first-run 文档，不要直接把仓库交给访客。",
        },
        {
            "order": 2,
            "title": "验证公开无 Key 演示",
            "command": "python scripts/verify_public_demo_mode.py --format markdown",
            "expected": "看到 AI 漫剧制片办公室和研究办公室都有固定样例、下载物、阅读指南和安全边界。",
            "if_fails": "先检查 /api/demo/public-showcase、样例下载文件和办公室 launch gate 证据链接。",
        },
        {
            "order": 3,
            "title": "导出可托管静态展示包",
            "command": "python scripts/export_public_showcase.py && python scripts/verify_static_public_showcase.py --format markdown",
            "expected": "看到 dist/public-showcase/index.html、6 个下载物、7 个可复核文件、6/6 阅读指南，并且 requires_backend=False。",
            "if_fails": "不要部署到 Vercel；先修复静态下载路径、data.js、截图资产或 claim report。",
        },
        {
            "order": 4,
            "title": "验证真实生产声明边界",
            "command": "python scripts/verify_comic_real_production_claim.py --format markdown",
            "expected": "看到 claim_level=demo_structure_only，明确不能宣称真实模型画质已验证。",
            "if_fails": "先修真实生产声明报告，避免作品集或 README 夸大能力。",
        },
        {
            "order": 5,
            "title": "最后跑公开发布总门禁",
            "command": "python scripts/verify_release_readiness.py --format markdown",
            "expected": "看到 All no-key release gates passed，并且 secret scan 通过。",
            "if_fails": "按失败项逐一修复；不要用单个局部测试替代总门禁。",
        },
    ]


def _public_showcase_first_run_paths() -> list[dict]:
    return [
        {
            "id": "public_demo",
            "title": "只看公开演示",
            "for_user": "面试官、作品集访客、第一次打开项目的人。",
            "requires_api_key": False,
            "start_here": "打开公开展示页，先看两个 no-key 样例和可下载交付物。",
            "do_first": [
                "打开首页的公开展示入口。",
                "下载 AI 漫剧 Word 制片画布和 handoff manifest。",
                "确认页面声明 demo-only，不调用真实模型，也不读取本地 Key。",
            ],
            "verification": "python scripts/verify_public_demo_mode.py --format markdown",
            "success_signal": "能看到固定样例、阅读指南、下载物和安全边界。",
        },
        {
            "id": "local_real_use",
            "title": "本地真实使用",
            "for_user": "想用自己的模型 Key 生成真实报告或 AI 漫剧制片包的人。",
            "requires_api_key": True,
            "start_here": "先复制本机配置，再用 doctor 检查缺哪些模型。",
            "do_first": [
                "复制 config.example.yaml 为 config.yaml，或使用本机环境变量。",
                "在模型页逐个测试部门 Key，先跑通文本部门，再补工部和刑部。",
                "真实产物完成后，从历史页下载 Word、manifest、提示词包和 trace。",
            ],
            "verification": "python scripts/doctor.py --format markdown",
            "success_signal": "doctor 显示 real_production.status=ready_for_real_run。",
        },
        {
            "id": "developer_extension",
            "title": "开发新办公室",
            "for_user": "想新增短视频、电商、小说 IP 或技术项目办公室的开发者。",
            "requires_api_key": False,
            "start_here": "先读办公室协议，不要直接复制一个临时页面或共享配置。",
            "do_first": [
                "查看 /api/offices/protocols 和 docs/NEW_OFFICE_STARTER_CHECKLIST.md。",
                "为新办公室声明独立 office_id、模型、工作区、历史和产物契约。",
                "补齐 no-key 样例、schema gate、失败恢复和 launch gate 证据。",
            ],
            "verification": "python scripts/verify_office_extension_governance.py --format markdown",
            "success_signal": "新办公室能说明参观路径、证明点、下载物、阅读指南和安全边界。",
        },
    ]


def _public_showcase_post_run_validation() -> list[dict]:
    return [
        {
            "order": 1,
            "title": "交付物清点",
            "command": "python scripts/audit_comic_v2_handoffs.py --format markdown",
            "expected": "Word 画布、handoff manifest、prompt package、image records 和 trace JSON 都能找到，并且引用链路没有断。",
            "if_fails": "先不要对外交付；回到历史页下载缺失文件，或按 trace 里的恢复动作补齐产物。",
        },
        {
            "order": 2,
            "title": "真实生产声明",
            "command": "python scripts/verify_comic_real_production_claim.py --manifest output/your_project/xxx_handoff_manifest.json --format markdown",
            "expected": "看到 can_claim_real_quality=True；如果仍是 demo_structure_only，就只能说结构样例通过，不能说真实画质通过。",
            "if_fails": "先补跑真实模型生图和刑部视觉质检，不要把 fixture、缺图或部分模型结果写成生产级。",
        },
        {
            "order": 3,
            "title": "制片质量基准",
            "command": "python scripts/verify_comic_v2_production_benchmark.py --manifest output/your_project/xxx_handoff_manifest.json --format markdown",
            "expected": "看到 production_quality_verified 或等价通过状态，且故事、资产、图片、镜头、提示词和 Word 引用链路互相对得上。",
            "if_fails": "按失败项修复资产 ID、图片记录、提示词引用或 Word 画布，再重新生成交付包。",
        },
    ]


def _public_showcase_office_extension_story(blueprint: dict) -> dict:
    starter = list(blueprint.get("starter_checklist") or [])
    steps = list(blueprint.get("implementation_steps") or [])
    candidates = list(blueprint.get("future_office_candidates") or [])
    backlog = list(blueprint.get("future_platform_backlog") or [])
    return {
        "title": "新办公室扩展路径",
        "summary": "未来任何办公室都不能只做一个入口就出现在公开产品里；它必须先证明产品价值、安全边界、office_id 隔离、人工确认节点、样例交付物、结构与失败恢复、无 Key 演示行为和发布检查。",
        "starter_checklist_doc": blueprint.get("starter_checklist_doc", "docs/NEW_OFFICE_STARTER_CHECKLIST.md"),
        "purpose": blueprint.get("purpose", ""),
        "starter_item_count": len(starter),
        "starter_phases": [item.get("phase", "") for item in starter if item.get("phase")],
        "starter_checklist": [
            {
                "order": item.get("order"),
                "id": item.get("id", ""),
                "phase": item.get("phase", ""),
                "question": item.get("question", ""),
                "evidence": item.get("evidence", ""),
            }
            for item in starter[:8]
        ],
        "implementation_steps": [
            {
                "order": item.get("order"),
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "owner": item.get("owner", ""),
                "done_when": item.get("done_when", ""),
                "files": item.get("files", []),
            }
            for item in steps[:5]
        ],
        "future_office_candidates": [
            {
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "user_job": item.get("user_job", ""),
                "not_ready_reason": item.get("not_ready_reason", ""),
                "required_before_public": item.get("required_before_public", []),
            }
            for item in candidates
        ],
        "future_platform_backlog": [
            {
                "id": item.get("id", ""),
                "status": item.get("status", ""),
                "description": item.get("description", ""),
                "evidence_required": item.get("evidence_required", ""),
            }
            for item in backlog
        ],
        "required_verifiers": blueprint.get("required_verifiers", []),
        "public_boundary": "公开展示可以说明如何扩展办公室，但不能暴露 API keys、cookies、浏览器配置、运行产物或用户工作区数据。",
    }


def _public_showcase_release_badge(comic_inventory: dict, comic_claim: dict) -> dict:
    return {
        "status": "safe_public_demo",
        "label": "可公开展示",
        "mode": "demo_only",
        "summary": "固定样例、下载物和发布门禁可公开展示；真实生产仍需使用者在本地填写自己的模型 Key。",
        "signals": [
            {"label": "API Key", "value": "不需要", "status": "passed"},
            {"label": "真实模型调用", "value": "不调用", "status": "passed"},
            {"label": "静态托管", "value": "支持", "status": "passed"},
            {"label": "真实画质声明", "value": "未验证", "status": "bounded"},
            {
                "label": "交付盘点",
                "value": f"{comic_inventory.get('manifest_count', 0)} 份结构样例",
                "status": "passed",
            },
        ],
        "safe_public_claim": comic_inventory.get("safe_public_claim", ""),
        "claim_level": comic_claim.get("claim_level", "demo_structure_only"),
        "can_claim_real_quality": comic_claim.get("can_claim_real_quality", False),
        "primary_gate": "python scripts/verify_release_readiness.py --format markdown",
        "proof_commands": [
            "python scripts/verify_public_demo_mode.py --format markdown",
            "python scripts/verify_static_public_showcase.py --format markdown",
            "python scripts/check_no_secrets.py",
        ],
    }


@app.get("/api/demo/public-showcase")
async def get_public_showcase_demo_api():
    """Return one public, no-key manifest for portfolio pages and external demos."""
    comic_demo = await get_comic_production_demo_api()
    comic_inventory = await get_comic_production_handoff_inventory_demo_api()
    comic_claim = await get_comic_production_claim_report_demo_api()
    research_demo = await get_research_demo_api()
    research_claim = _research_claim_report_from_demo(research_demo)
    extension_blueprint = list_office_extension_blueprint()
    featured_demos = [
        _public_showcase_demo(
            comic_demo,
            "/api/demo/comic-production",
            "AI 漫剧制片办公室",
            "证明产品能把故事拆成资产、镜头、提示词和 Word 制片画布，而不是只生成一段文字。",
        ),
        _public_showcase_demo(
            research_demo,
            "/api/demo/research",
            "研究办公室",
            "证明同一套办公室框架也能组织报告、来源、数据点、竞品表和截图计划。",
        ),
    ]
    sample_deliverables = _public_showcase_sample_deliverables(featured_demos)
    sample_deliverables.append(_public_showcase_claim_report_deliverable(comic_claim))
    return {
        "mode": "public_no_key_showcase",
        "product_name": "三个臭皮匠",
        "tagline": "把复杂项目交给办公室，而不是只让模型聊一段话。",
        "positioning": "本地优先的多 Agent 协作工作台：用办公室、人工审核节点、结构化产物和引用链路，把想法推进到可复现、可交付的结果。",
        "requires_api_key": False,
        "calls_real_models": False,
        "safe_for_public_portfolio": True,
        "safety_boundaries": [
            "公开展示只开放固定样例和 /api/demo 入口。",
            "不读取 config.yaml、环境变量、Cookie、登录态或本地用户工作区。",
            "不要把个人 API Key 写进前端、GitHub、Vercel 公开环境变量或静态文件。",
            "真实生产继续走本地模式，由使用者填写自己的模型 Key。",
        ],
        "audience_paths": [
            {
                "id": "interviewer",
                "label": "面试官",
                "takeaway": "3 分钟内看懂产品价值：它不是聊天框，而是能展示流程、证据和交付物的多 Agent 工作台。",
                "steps": [
                    "先看首页产品定位和无 Key 演示入口。",
                    "打开 AI 漫剧制片办公室样例，确认故事、资产、镜头、提示词和 Word 画布如何串起来。",
                    "下载 Word 画布或引用清单，验证交付物不是页面装饰。",
                ],
            },
            {
                "id": "developer",
                "label": "开发者",
                "takeaway": "能快速判断仓库是否可复现、能否扩展新办公室、公开部署是否安全。",
                "steps": [
                    "运行 doctor 和 public demo verifier。",
                    "查看 /api/offices/{office_id}/launch-gates 的门禁证据。",
                    "按办公室协议补齐新办公室的输入、输出、模型、schema gate 和恢复动作。",
                ],
            },
            {
                "id": "user",
                "label": "普通使用者",
                "takeaway": "先安全体验固定样例，再决定是否在本地填写自己的 Key 进入真实生产。",
                "steps": [
                    "先跑无 Key 演示，不需要配置模型。",
                    "看清每个办公室能交付什么文件。",
                    "进入本地真实模式前，在模型页逐个测试部门 Key。",
                ],
            },
        ],
        "featured_demos": featured_demos,
        "portfolio_embed": {
            "repository_url": "https://github.com/atticus-zhou/sangechoupijiang",
            "product_positioning": "办公室式多 Agent 协作平台，用可审核流程和可下载交付物替代一次性聊天回答。",
            "office_hall": {
                "title": "办公室大厅",
                "summary": "首页只突出办公室入口、无 Key 演示、系统预检和上线门禁，让访问者先理解产品结构，再进入具体办公室。",
                "primary_office": "AI 漫剧制片办公室",
                "secondary_offices": ["研究办公室"],
            },
            "workflow_showcase": [
                {
                    "kind": "screenshot_target",
                    "title": "办公室大厅首屏",
                    "route": "/",
                    "selector": "#product-showcase",
                    "caption": "展示产品定位、无 Key 演示入口和真实办公室入口。",
                },
                {
                    "kind": "screenshot_target",
                    "title": "AI 漫剧制片办公室演示",
                    "route": "/#demo_comic",
                    "selector": "#comic-demo-content",
                    "caption": "展示故事、资产、镜头、提示词、Word 画布和引用清单如何串联。",
                },
                {
                    "kind": "download",
                    "title": "样例 Word 制片画布",
                    "uri": "/api/demo/comic-production/files/word_canvas.docx",
                    "caption": "证明最终交付物不是网页装饰，可以下载并交给下游工具继续生产。",
                },
                {
                    "kind": "download",
                    "title": "研究办公室阶段报告",
                    "uri": "/api/demo/research/files/report.md",
                    "caption": "证明研究办公室也能输出来源、数据点、竞品和截图计划。",
                },
            ],
            "sample_deliverables": sample_deliverables,
            "release_badge": _public_showcase_release_badge(comic_inventory, comic_claim),
            "fast_review_route": _public_showcase_fast_review_route(),
            "deliverable_reading_guide": _public_showcase_deliverable_reading_guide(),
            "downstream_quick_start": _public_showcase_downstream_quick_start(),
            "shot_contract": _public_showcase_shot_contract(),
            "interview_demo_script": _public_showcase_interview_demo_script(),
            "first_run_paths": _public_showcase_first_run_paths(),
            "reproducibility_checklist": _public_showcase_reproducibility_checklist(),
            "post_run_validation": _public_showcase_post_run_validation(),
            "portfolio_integration": _public_showcase_portfolio_integration(),
            "office_extension_story": _public_showcase_office_extension_story(extension_blueprint),
            "handoff_inventory": {
                "uri": "/api/demo/comic-production/handoff-inventory",
                "status": comic_inventory.get("status", ""),
                "manifest_count": comic_inventory.get("manifest_count", 0),
                "production_verified_count": comic_inventory.get("production_verified_count", 0),
                "demo_only_count": comic_inventory.get("demo_only_count", 0),
                "needs_review_count": comic_inventory.get("needs_review_count", 0),
                "legacy_unverifiable_count": comic_inventory.get("legacy_unverifiable_count", 0),
                "safe_public_claim": comic_inventory.get("safe_public_claim", ""),
                "next_action": comic_inventory.get("next_action", ""),
            },
            "quality_upgrade_path": _public_showcase_quality_upgrade_path(comic_claim),
            "research_claim_boundary": {
                "uri": research_claim.get("uri", "/api/demo/research/claim-report"),
                "claim_level": research_claim.get("claim_level", ""),
                "can_publicly_show": research_claim.get("can_publicly_show", False),
                "can_claim_full_automation": research_claim.get("can_claim_full_automation", False),
                "requires_api_key": research_claim.get("requires_api_key", False),
                "calls_real_models": research_claim.get("calls_real_models", False),
                "allowed_public_claims": research_claim.get("allowed_public_claims", [])[:3],
                "forbidden_public_claims": research_claim.get("forbidden_public_claims", [])[:3],
                "claim_upgrade_checklist": research_claim.get("claim_upgrade_checklist", [])[:3],
                "evidence_handoff_count": len(research_claim.get("evidence_handoff") or []),
                "next_action": research_claim.get("next_action", ""),
            },
            "real_production_claim": {
                "uri": comic_claim.get("uri", "/api/demo/comic-production/claim-report"),
                "claim_level": comic_claim.get("claim_level", ""),
                "quality_claim": comic_claim.get("quality_claim", ""),
                "can_publicly_show": comic_claim.get("can_publicly_show", False),
                "can_claim_real_quality": comic_claim.get("can_claim_real_quality", False),
                "downstream_status": comic_claim.get("downstream_status", ""),
                "allowed_public_claims": comic_claim.get("allowed_public_claims", [])[:3],
                "forbidden_public_claims": comic_claim.get("forbidden_public_claims", [])[:3],
                "claim_upgrade_checklist": comic_claim.get("claim_upgrade_checklist", [])[:3],
                "next_action": comic_claim.get("next_action", ""),
                "evidence": comic_claim.get("evidence", {}),
            },
        },
        "public_deployment": {
            "mode": "demo_only",
            "allowed_route_prefixes": ["/api/demo"],
            "allows_real_model_calls": False,
            "allows_workspace_writes": False,
            "recommended_hosts": ["Vercel", "Netlify", "GitHub Pages"],
            "static_export": {
                "command": "python scripts/export_public_showcase.py",
                "verification_command": "python scripts/verify_static_public_showcase.py --format markdown",
                "entrypoint": "dist/public-showcase/index.html",
                "requires_backend": False,
                "requires_api_key": False,
            },
            "forbidden_public_assets": [
                "config.yaml",
                ".env",
                "user_data/",
                "output/",
                "browser profile",
                "Cookie",
                "API Key",
            ],
        },
        "verification_commands": [
            "python scripts/verify_public_demo_mode.py --format markdown",
            "python scripts/verify_static_public_showcase.py --format markdown",
            "python scripts/verify_comic_v2_downstream_handoff.py --format markdown",
            "python scripts/verify_product_readiness.py --format markdown",
            "python scripts/check_no_secrets.py",
        ],
    }


def _load_research_demo_fixture() -> dict:
    return json.loads((APP_BASE_DIR / "tests" / "fixtures" / "research_sample.json").read_text(encoding="utf-8"))


def _ensure_research_demo_delivery() -> dict[str, Path]:
    """Build deterministic research demo files under output/demo without workspace writes."""
    output_root = APP_BASE_DIR / "output" / "demo" / "research"
    delivery_dir = output_root / "delivery"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    fixture = _load_research_demo_fixture()
    artifacts = build_research_artifacts("demo_research", fixture)
    by_type = {item.get("artifact_type"): item for item in artifacts}
    report = by_type.get("standard_report") or by_type.get("report")
    if not report:
        raise HTTPException(status_code=500, detail="Demo research report was not generated.")
    report_path = delivery_dir / "report.md"
    report_path.write_text(report.get("content", ""), encoding="utf-8")
    manifest_path = delivery_dir / "evidence_manifest.json"
    manifest = {
        "title": (fixture.get("plan") or {}).get("title") or "研究办公室固定样例",
        "mode": "no_key_demo",
        "sources": _research_demo_sources(fixture.get("results") or []),
        "data_points": _research_demo_data_points(fixture.get("results") or []),
        "competitors": _research_demo_competitors(fixture.get("results") or []),
        "chart_suggestions": _research_demo_chart_suggestions(fixture.get("results") or []),
        "evidence_handoff": _research_demo_evidence_handoff(),
        "screenshot_plan": (by_type.get("screenshot_plan") or {}).get("content", ""),
        "artifacts": [
            {
                "artifact_type": item.get("artifact_type"),
                "title": item.get("title"),
                "created_by": item.get("created_by"),
            }
            for item in artifacts
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if manifest_path.stat().st_size <= 20:
        raise HTTPException(status_code=500, detail="Demo evidence manifest was not generated.")
    return {"report_markdown": report_path, "evidence_manifest": manifest_path}


@app.get("/api/demo/research/files/{filename}")
async def get_research_demo_file_api(filename: str):
    """Download one deterministic research demo file."""
    safe_name = Path(filename).name
    delivery = _ensure_research_demo_delivery()
    allowed = {
        "report.md": delivery["report_markdown"],
        "evidence_manifest.json": delivery["evidence_manifest"],
    }
    file_path = allowed.get(safe_name)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Demo file not found.")
    media_type = "application/json" if file_path.suffix.lower() == ".json" else "text/markdown; charset=utf-8"
    return FileResponse(str(file_path), filename=safe_name, media_type=media_type)


def _research_demo_sources(results: list[dict]) -> list[dict]:
    sources: list[dict] = []
    for step in results:
        for source in step.get("sources", []) or []:
            if isinstance(source, dict):
                sources.append(source)
    return sources


def _research_demo_data_points(results: list[dict]) -> list[dict]:
    data_points: list[dict] = []
    for step in results:
        for point in step.get("data_points", []) or []:
            if isinstance(point, dict):
                data_points.append(point)
    return data_points


def _research_demo_competitors(results: list[dict]) -> list[dict]:
    competitors: list[dict] = []
    for step in results:
        for item in step.get("competitors", []) or []:
            if isinstance(item, dict):
                competitors.append(item)
    return competitors


def _research_demo_chart_suggestions(results: list[dict]) -> list[dict]:
    suggestions: list[dict] = []
    for step in results:
        for item in step.get("chart_suggestions", []) or []:
            if isinstance(item, dict):
                suggestions.append(item)
    return suggestions


@app.get("/api/workspaces")
async def list_workspace_api(limit: int = 50, office_id: str = ""):
    """List project workspaces."""
    return {"workspaces": config_manager.list_workspaces(limit=limit, office_id=office_id)}


@app.post("/api/workspaces")
async def create_workspace_api(req: WorkspaceCreate):
    """Create a project workspace."""
    workspace_id = f"ws_{str(uuid.uuid4())[:8]}"
    office = get_office(req.office_id)
    config_manager.create_workspace(
        workspace_id=workspace_id,
        office_id=office.id,
        title=req.title,
        brief=req.brief,
    )
    return {
        "workspace_id": workspace_id,
        "office_id": office.id,
        "status": "created",
    }


@app.get("/api/workspaces/{workspace_id}")
async def get_workspace_api(workspace_id: str):
    """Get one project workspace."""
    workspace = config_manager.get_workspace(workspace_id)
    if not workspace:
        raise _missing_workspace_http_error(workspace_id)
    workspace["artifacts"] = config_manager.list_artifacts(workspace_id=workspace_id)
    return workspace


@app.get("/api/workspaces/{workspace_id}/artifacts")
async def list_workspace_artifacts_api(workspace_id: str):
    """List artifacts in a workspace."""
    if not config_manager.get_workspace(workspace_id):
        raise _missing_workspace_http_error(workspace_id)
    return {"artifacts": config_manager.list_artifacts(workspace_id=workspace_id)}


@app.get("/api/workspaces/{workspace_id}/tasks")
async def list_workspace_tasks_api(workspace_id: str):
    """List task runs and timeline events for a workspace."""
    if not config_manager.get_workspace(workspace_id):
        raise _missing_workspace_http_error(workspace_id)
    return {"tasks": config_manager.list_workspace_task_runs(workspace_id=workspace_id)}


@app.get("/api/workspaces/{workspace_id}/runtime-status")
async def get_workspace_runtime_status_api(workspace_id: str):
    """Explain where an office workspace is, what is missing, and how to recover."""
    status = build_office_runtime_status(config_manager, workspace_id)
    if not status:
        raise _missing_workspace_http_error(workspace_id)
    return status


def _comic_v2_key(workspace_id: str) -> str:
    return f"comic_v2_state:{workspace_id}"


def _comic_v2_workspace(workspace_id: str) -> dict:
    workspace = config_manager.get_workspace(workspace_id)
    if not workspace or workspace.get("office_id") != "comic_production":
        raise _comic_v2_http_error(
            404,
            department="尚书省",
            reason=f"AI漫剧制片工作空间 {workspace_id} 不存在或不属于制片办公室。",
            impact="无法读取该项目的 V2 生产状态，资产拆解、提示词、图片和 Word 画布都会停止。",
            next_action="回到 AI 漫剧制片办公室重新选择项目；如果项目不存在，请重新创建并确认故事。",
            stage="workspace_lookup",
        )
    return workspace


def _load_comic_v2_state(workspace_id: str) -> dict:
    raw = config_manager.get_kv(_comic_v2_key(workspace_id), "")
    if not raw:
        return {}
    try:
        return ComicProductionV2.from_dict(json.loads(raw)).to_dict()
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _comic_v2_http_error(
            500,
            department="尚书省",
            reason=f"V2 制片状态损坏，无法读取：{exc}",
            impact="系统无法判断当前阶段，继续操作可能导致资产、提示词或交付文档串版。",
            next_action="先刷新项目；如果仍失败，请重新创建项目或清理该项目的损坏状态后重新确认故事。",
            stage="state_load",
        ) from exc


def _save_comic_v2_state(workspace_id: str, state: dict) -> None:
    config_manager.set_kv(_comic_v2_key(workspace_id), json.dumps(state, ensure_ascii=False))


def _persist_comic_v2_contract(workspace: dict, state, review_status: str) -> None:
    workspace_id = state.workspace_id
    config_manager.create_artifact(
        artifact_id=(
            f"art_{workspace_id}_comic_v2_contract_"
            f"s{state.story_version}_v{state.style_version}"
        ),
        workspace_id=workspace_id,
        task_id="",
        artifact_type="comic_v2_contract",
        title=f"{workspace.get('title') or 'AI漫剧'} - V2故事合同与视觉母版",
        content=json.dumps(state.contract, ensure_ascii=False, indent=2),
        metadata={
            "office_id": "comic_production",
            "pipeline_version": 2,
            "story_id": state.story_id,
            "story_version": state.story_version,
            "style_id": state.style_id,
            "style_version": state.style_version,
            "review_status": review_status,
        },
        created_by="zhongshu",
    )


def _persist_comic_v2_manifest(workspace: dict, state, review_status: str) -> None:
    manifest = state.asset_manifest or {}
    version = int(manifest.get("version") or 0)
    if version < 1:
        raise ValueError("V2资产拆解包缺少有效版本")
    config_manager.create_artifact(
        artifact_id=f"art_{state.workspace_id}_comic_v2_asset_manifest_v{version}",
        workspace_id=state.workspace_id,
        task_id="",
        artifact_type="comic_v2_asset_manifest",
        title=f"{workspace.get('title') or 'AI漫剧'} - V2资产拆解包 v{version}",
        content=json.dumps(manifest, ensure_ascii=False, indent=2),
        metadata={
            "office_id": "comic_production",
            "pipeline_version": 2,
            "story_id": state.story_id,
            "story_version": state.story_version,
            "style_id": state.style_id,
            "style_version": state.style_version,
            "manifest_version": version,
            "manifest_hash": manifest.get("manifest_hash", ""),
            "review_status": review_status,
        },
        created_by="zhongshu",
    )


def _comic_v2_state_response(state) -> dict:
    payload = state.to_dict() if hasattr(state, "to_dict") else dict(state or {})
    manifest = payload.get("asset_manifest") or {}
    if manifest:
        try:
            payload["asset_review"] = asset_manifest_review_view(manifest)
        except Exception as exc:
            payload["asset_review"] = {
                "title": "资产拆解审核",
                "review_status": manifest.get("review_status", "awaiting_user_review"),
                "counts": {"characters": 0, "props": 0, "scenes": 0},
                "groups": {"characters": [], "props": [], "scenes": []},
                "human_guidance": f"资产审核视图暂时无法生成：{exc}",
            }
    payload["department_flow"] = _comic_v2_department_flow(payload)
    payload["production_lineage"] = _comic_v2_status_lineage(payload)
    payload["prompt_quality"] = audit_prompt_package(payload.get("prompt_package") or {})
    return payload


def _comic_v2_status_lineage(state: dict) -> list[dict]:
    stage = str(state.get("stage") or "")
    current_index = {
        "story_confirmed": 0,
        "visual_bible_review": 1,
        "asset_planning": 2,
        "asset_review": 2,
        "prompt_planning": 3,
        "image_generation": 4,
        "visual_review": 5,
        "document_generation": 6,
        "ready_for_handoff": 6,
    }.get(stage, -1)
    stages = [
        ("story_contract", "故事合同", "内阁 / 中书省", "主创对话官 / 中书省", "用户确认完整故事，后续部门不得擅自改写。", "视觉母版", "故事原文、故事版本和禁止改写规则齐全。", _comic_v2_lineage_output(state, "story_contract")),
        ("visual_bible", "风格圣经", "中书省 / 门下省", "美术设定官 / 连续性审核官", "用户确认画风、时代、禁用元素和连续性规则。", "资产拆解", "视觉母版包含画风、时代、比例、色彩、服装和禁用元素。", _comic_v2_lineage_output(state, "visual_bible")),
        ("asset_manifest", "资产拆解", "中书省 / 门下省", "资产拆解官 / 设定审校官", "用户确认人物、道具、场景是否属于当前故事。", "提示词与镜头执行包", "每个资产都有原文证据、故事用途、计划图片和审核状态。", _comic_v2_lineage_output(state, "asset_manifest")),
        ("prompt_package", "提示词与镜头执行包", "兵部 / 刑部", "镜头调度官 / 提示词质检官", "资产确认后生成镜头、动作链和可执行提示词。", "基础图片生产", "资产提示词和镜头卡引用已审核资产，并把负面提示词单独列出。", _comic_v2_lineage_output(state, "prompt_package")),
        ("image_production", "基础图片生产", "工部", "图片生成官", "失败、低分或风格不一致的图片需要重试或人工放行。", "一致性质检", "人物和道具基础图保持干净白底，场景图保留空间信息。", _comic_v2_lineage_output(state, "image_production")),
        ("visual_review", "一致性质检", "刑部", "一致性审核官", "交付前检查人物脸型、服装、道具、场景风格和引用关系。", "Word 画布交付", "图片通过身份、风格、时代、空间和用途检查，风险项有处理结论。", _comic_v2_lineage_output(state, "visual_review")),
        ("delivery", "Word 画布交付", "礼部 / 刑部", "交付排版官 / 结构审计官", "最终 Word 画布和引用清单必须一起交付。", "下游视频平台", "Word 画布、图片、镜头卡和 handoff manifest 可下载且引用一致。", _comic_v2_lineage_output(state, "delivery")),
    ]
    lineage = []
    for index, (stage_id, label, department, agent, checkpoint, handoff_to, acceptance, output) in enumerate(stages):
        if current_index < 0:
            status = "waiting"
        elif stage == "ready_for_handoff" and index == current_index:
            status = "completed"
        elif index < current_index:
            status = "completed"
        elif index == current_index:
            status = "current"
        else:
            status = "waiting"
        lineage.append({
            "stage": stage_id,
            "stage_label": label,
            "department": department,
            "agent": agent,
            "status": status,
            "human_checkpoint": checkpoint,
            "handoff_to": handoff_to,
            "acceptance_criteria": acceptance,
            "output": output,
        })
    return lineage


def _comic_v2_lineage_output(state: dict, stage_id: str) -> str:
    if stage_id == "story_contract":
        story_id = state.get("story_id") or ""
        version = state.get("story_version") or 0
        return f"{story_id} v{version}" if story_id else "等待故事确认"
    if stage_id == "visual_bible":
        contract = state.get("contract") or {}
        visual = contract.get("visual") or {}
        medium = visual.get("medium") or ""
        ratio = visual.get("aspect_ratio") or ""
        return " · ".join([item for item in [medium, ratio] if item]) or "等待视觉母版"
    if stage_id == "asset_manifest":
        items = (state.get("asset_manifest") or {}).get("items") or []
        return f"{len(items)} 个资产" if items else "等待资产拆解"
    if stage_id == "prompt_package":
        package = state.get("prompt_package") or {}
        prompts = package.get("prompts") or []
        shots = package.get("shots") or []
        return f"{len(prompts)} 条资产提示词 · {len(shots)} 张镜头卡" if package else "等待提示词生成"
    if stage_id == "image_production":
        images = state.get("image_production") or {}
        records = images.get("records") or []
        return f"{len(records)} 张基础资产图" if images else "等待图片生成"
    if stage_id == "visual_review":
        images = state.get("image_production") or {}
        failures = images.get("failures") or []
        if not images:
            return "等待视觉质检"
        return f"{len(failures)} 个风险项"
    if stage_id == "delivery":
        audit = (state.get("delivery") or {}).get("audit") or {}
        if not audit:
            return "等待 Word 画布"
        return f"{audit.get('embedded_images', 0)} 张嵌入图片"
    return ""


def _comic_v2_department_flow(state: dict) -> list[dict]:
    stage = str(state.get("stage") or "")
    current_agent = str(state.get("current_agent") or "")
    current_department_id = _comic_v2_stage_department(stage, current_agent)
    completed_by_stage = {
        "visual_bible_review": {"neige"},
        "asset_planning": {"neige", "zhongshu"},
        "asset_review": {"neige", "zhongshu"},
        "prompt_planning": {"neige", "zhongshu", "menxia", "shangshu", "ribu", "hubu"},
        "image_generation": {"neige", "zhongshu", "menxia", "shangshu", "ribu", "hubu", "bingbu"},
        "visual_review": {"neige", "zhongshu", "menxia", "shangshu", "ribu", "hubu", "bingbu", "gongbu"},
        "document_generation": {"neige", "zhongshu", "menxia", "shangshu", "ribu", "hubu", "bingbu", "gongbu", "xingbu"},
        "ready_for_handoff": {"neige", "zhongshu", "menxia", "shangshu", "ribu", "hubu", "bingbu", "gongbu", "xingbu", "libu"},
    }
    completed = completed_by_stage.get(stage, set())
    departments = [
        ("neige", "内阁", "和用户对齐故事、方向和创作取舍"),
        ("zhongshu", "中书省", "把确认故事变成生产合同、视觉母版和资产拆解草案"),
        ("menxia", "门下省", "审核故事、资产、镜头和交付是否遗漏或跑偏"),
        ("shangshu", "尚书省", "调度阶段、记录状态、决定下一步"),
        ("ribu", "吏部", "维护连续性、版本记录和人物道具场景身份稳定"),
        ("hubu", "户部", "维护结构化资产台账和资源引用链路"),
        ("bingbu", "兵部", "生成镜头、动作链、视频提示词和执行计划"),
        ("gongbu", "工部", "生成基础资产图并参与 Word 制片画布组装"),
        ("xingbu", "刑部", "执行文本/视觉质检、风险说明和人工放行判断"),
        ("libu", "礼部", "整理交付说明、下游提示和对人可读的 Word 画布"),
    ]
    return [
        {
            "department_id": department_id,
            "name": name,
            "responsibility": responsibility,
            "status": (
                "current"
                if department_id == current_department_id
                else "completed"
                if department_id in completed
                else "waiting"
            ),
            "human_checkpoint": _comic_v2_department_checkpoint(department_id, stage),
        }
        for department_id, name, responsibility in departments
    ]


def _comic_v2_stage_department(stage: str, current_agent: str) -> str:
    if "门下" in current_agent:
        return "menxia"
    if "工部" in current_agent:
        return "gongbu"
    if "刑部" in current_agent:
        return "xingbu"
    if "礼部" in current_agent:
        return "libu"
    if "尚书" in current_agent:
        return "shangshu"
    return {
        "story_confirmed": "neige",
        "visual_bible_review": "zhongshu",
        "asset_planning": "shangshu",
        "asset_review": "menxia",
        "prompt_planning": "gongbu",
        "image_generation": "gongbu",
        "visual_review": "xingbu",
        "document_generation": "libu",
        "ready_for_handoff": "libu",
    }.get(stage, "shangshu")


def _comic_v2_department_checkpoint(department_id: str, stage: str) -> str:
    if department_id == "zhongshu" and stage == "visual_bible_review":
        return "等待用户确认视觉母版"
    if department_id == "menxia" and stage == "asset_review":
        return "等待用户确认资产拆解"
    if department_id == "xingbu" and stage == "visual_review":
        return "等待用户处理视觉质检风险"
    if department_id == "libu" and stage == "ready_for_handoff":
        return "Word 制片画布可下载"
    return ""


def _comic_v2_http_error(
    status_code: int,
    *,
    department: str,
    reason: str,
    impact: str,
    next_action: str,
    stage: str = "",
    agent: str = "",
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "office_id": "comic_production",
            "office_name": "AI漫剧制片办公室",
            "department": department,
            "agent": agent or department,
            "stage": stage,
            "reason": reason,
            "impact": impact,
            "next_action": next_action,
        },
    )


def _research_http_error(
    status_code: int,
    *,
    department: str,
    reason: str,
    impact: str,
    next_action: str,
    stage: str = "",
    agent: str = "",
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "office_id": "research",
            "office_name": "研究办公室",
            "department": department,
            "agent": agent or department,
            "stage": stage,
            "reason": reason,
            "impact": impact,
            "next_action": next_action,
        },
    )


def _system_http_error(
    status_code: int,
    *,
    reason: str,
    impact: str,
    next_action: str,
    stage: str = "",
    department: str = "系统",
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "office_id": "system",
            "office_name": "系统配置",
            "department": department,
            "agent": department,
            "stage": stage,
            "reason": reason,
            "impact": impact,
            "next_action": next_action,
        },
    )

def _comic_legacy_http_error(
    status_code: int,
    *,
    department: str,
    reason: str,
    impact: str,
    next_action: str,
    stage: str = "",
    agent: str = "",
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "office_id": "comic_production",
            "office_name": "AI漫剧制片办公室",
            "department": department,
            "agent": agent or department,
            "stage": stage,
            "reason": reason,
            "impact": impact,
            "next_action": next_action,
        },
    )


def _workspace_actionable_http_error(
    workspace_id: str,
    status_code: int,
    *,
    department: str,
    reason: str,
    impact: str,
    next_action: str,
    stage: str = "",
    agent: str = "",
) -> HTTPException:
    workspace = config_manager.get_workspace(workspace_id)
    office_id = (workspace or {}).get("office_id", "research")
    if office_id == "comic_production":
        return _comic_v2_http_error(
            status_code,
            department=department,
            reason=reason,
            impact=impact,
            next_action=next_action,
            stage=stage,
            agent=agent,
        )
    if _is_comic_office_id(office_id):
        return _comic_legacy_http_error(
            status_code,
            department=department,
            reason=reason,
            impact=impact,
            next_action=next_action,
            stage=stage,
            agent=agent,
        )
    return _research_http_error(
        status_code,
        department=department,
        reason=reason,
        impact=impact,
        next_action=next_action,
        stage=stage,
        agent=agent,
    )


def _missing_workspace_http_error(workspace_id: str, *, stage: str = "workspace_lookup") -> HTTPException:
    return _research_http_error(
        404,
        department="尚书省",
        reason=f"工作空间 {workspace_id} 不存在或已被清理。",
        impact="系统无法读取这个项目的任务、产物或历史状态，页面也无法继续展示该项目内容。",
        next_action="回到办公室大厅或项目列表重新选择一个有效项目；如果这是刚创建的项目，请刷新后重试。",
        stage=stage,
    )


def _comic_v2_task_id(workspace_id: str) -> str:
    return f"comic_v2_{workspace_id}"


def _ensure_comic_v2_task_run(workspace: dict, action: str) -> str:
    workspace_id = workspace["workspace_id"]
    task_id = _comic_v2_task_id(workspace_id)
    existing = config_manager.get_task_run(task_id)
    if not existing:
        title = workspace.get("title") or workspace_id
        config_manager.create_task_run(task_id, f"AI漫剧制片办公室：{title} - {action}", "")
    return task_id


def _append_comic_v2_event(
    workspace_id: str,
    event_type: str,
    status: str,
    summary: str,
    payload: dict | None = None,
) -> None:
    data = {"workspace_id": workspace_id}
    data.update(payload or {})
    config_manager.append_task_event(
        task_id=_comic_v2_task_id(workspace_id),
        event_type=event_type,
        status=status,
        summary=summary,
        payload=data,
    )


def _confirmed_story_for_v2(workspace_id: str) -> tuple[str, dict]:
    session = _load_comic_cabinet_session(workspace_id)
    confirmed = (session or {}).get("confirmed_script") or {}
    story = str(confirmed.get("story_draft") or "")
    if not session.get("confirmed") or not story.strip():
        raise _comic_v2_http_error(
            400,
            department="内阁 / 中书省",
            reason="请先确认完整故事，再生成视觉母版。",
            impact="没有锁定故事时，中书省无法建立视觉母版，后续资产拆解、提示词、图片和 Word 画布都会偏离。",
            next_action="回到主创对话，补全并确认故事后再开始生产。",
            stage="story_confirming",
        )
    return story, confirmed


def _comic_v2_capability_model(
    capability_agent: str,
    fallback_agents: tuple[str, ...],
    *,
    kind: str,
):
    candidates = (capability_agent,) + fallback_agents
    selected = None
    for agent in candidates:
        config = config_manager.get_model_config(agent, office_id="comic_production")
        selected = selected or config
        has_access = bool(config.api_key) or config.provider.lower() == "ollama" or config.api_base.startswith("http://localhost") or config.api_base.startswith("http://127.0.0.1")
        if not has_access:
            continue
        is_image = is_image_generation_config(config)
        if kind == "image" and is_image:
            return config
        if kind in {"text", "vision"} and not is_image:
            return config
    return selected or config_manager.get_model_config(fallback_agents[-1], office_id="comic_production")


@app.get("/api/workspaces/{workspace_id}/comic/v2/status")
async def get_comic_v2_status_api(workspace_id: str):
    _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if raw:
        return _comic_v2_state_response(ComicProductionV2.from_dict(raw))
    return _comic_v2_state_response(not_started_state(workspace_id))


@app.post("/api/workspaces/{workspace_id}/comic/v2/start")
async def start_comic_v2_api(workspace_id: str, req: ComicV2StartRequest):
    workspace = _comic_v2_workspace(workspace_id)
    try:
        state = ComicProductionV2.start(
            req.source_story,
            req.planner_payload,
            workspace_id=workspace_id,
        )
    except ContractValidationError as exc:
        raise _comic_v2_http_error(
            400,
            department="中书省",
            reason=f"无法建立正式制片合同：{exc}",
            impact="正式制片合同无法建立时，生产链不会进入视觉母版、资产拆解和提示词阶段。",
            next_action="补充完整故事、主角目标、冲突、结局和视觉方向后重新开始。",
            stage="contract_planning",
        ) from exc
    payload = state.to_dict()
    _save_comic_v2_state(workspace_id, payload)
    _persist_comic_v2_contract(workspace, state, "awaiting_user_review")
    config_manager.append_task_event(
        task_id=f"comic_v2_{workspace_id}",
        event_type="comic_v2_visual_bible_ready",
        status="waiting_for_human",
        summary="V2故事合同与视觉母版等待用户确认",
        payload={
            "workspace_id": workspace_id,
            "stage": state.stage,
            "current_agent": state.current_agent,
            "current_object": state.current_object,
            "next_action": state.next_action,
        },
    )
    return payload


@app.post("/api/workspaces/{workspace_id}/comic/v2/plan-confirmed")
async def plan_confirmed_comic_v2_api(workspace_id: str):
    workspace = _comic_v2_workspace(workspace_id)
    source_story, confirmed = _confirmed_story_for_v2(workspace_id)
    try:
        if fixture_mode_enabled():
            bundle = fixture_contract_bundle(
                source_story,
                story_version=int(confirmed.get("script_version") or 1),
            )
        else:
            config = config_manager.get_model_config("zhongshu", office_id="comic_production")
            bundle = await plan_contract(
                source_story,
                config,
                source_mode="full_story",
                story_version=int(confirmed.get("script_version") or 1),
            )
    except PlannerError as exc:
        raise _comic_v2_http_error(
            502,
            department="中书省",
            reason=f"视觉母版规划失败：{exc}",
            impact="视觉母版没有生成时，人物、道具、场景和镜头提示词没有统一风格依据。",
            next_action="检查中书省模型配置、API Key、额度和返回质量；必要时补充更明确的故事确认信息。",
            stage="visual_bible_planning",
        ) from exc
    state = ComicProductionV2.from_bundle(bundle, workspace_id=workspace_id)
    _save_comic_v2_state(workspace_id, state.to_dict())
    _persist_comic_v2_contract(workspace, state, "awaiting_user_review")
    config_manager.append_task_event(
        task_id=f"comic_v2_{workspace_id}",
        event_type="comic_v2_visual_bible_ready",
        status="waiting_for_human",
        summary="故事合同与视觉母版等待用户确认",
        payload={"workspace_id": workspace_id, "style_version": state.style_version},
    )
    return _comic_v2_state_response(state)


@app.post("/api/workspaces/{workspace_id}/comic/v2/visual-bible/approve")
async def approve_comic_v2_visual_bible_api(workspace_id: str):
    workspace = _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if not raw:
        raise _comic_v2_http_error(
            409,
            department="中书省",
            reason="请先生成视觉母版。",
            impact="视觉母版无法确认，资产拆解和后续生产不会开始。",
            next_action="先确认故事，再由中书省生成故事合同与视觉母版。",
            stage="not_started",
        )
    try:
        state = ComicProductionV2.approve_visual_bible(ComicProductionV2.from_dict(raw))
    except ValueError as exc:
        current = ComicProductionV2.from_dict(raw)
        raise _comic_v2_http_error(
            409,
            department="中书省",
            reason=f"当前阶段不能确认视觉母版：{exc}",
            impact="系统不会覆盖当前阶段已经生成或等待审核的内容，避免串阶段。",
            next_action=f"先处理当前阶段：{current.next_action or '回到当前阶段继续处理'}；不要重复确认视觉母版。",
            stage=current.stage,
            agent=current.current_agent,
        ) from exc
    _save_comic_v2_state(workspace_id, state.to_dict())
    _persist_comic_v2_contract(workspace, state, "approved")
    config_manager.append_task_event(
        task_id=f"comic_v2_{workspace_id}",
        event_type="comic_v2_visual_bible_approved",
        status="completed",
        summary="视觉母版已确认，可以进入资产拆解",
        payload={"workspace_id": workspace_id, "style_version": state.style_version},
    )
    return _comic_v2_state_response(state)


@app.post("/api/workspaces/{workspace_id}/comic/v2/visual-bible/revise")
async def revise_comic_v2_visual_bible_api(workspace_id: str, req: ComicV2RevisionRequest):
    workspace = _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if not raw:
        raise _comic_v2_http_error(
            409,
            department="中书省",
            reason="请先生成视觉母版。",
            impact="视觉母版还不存在，无法修改；资产拆解和后续生产也没有风格依据。",
            next_action="先确认故事并生成视觉母版，再填写退回意见修改。",
            stage="not_started",
        )
    state = ComicProductionV2.from_dict(raw)
    try:
        if fixture_mode_enabled():
            bundle = fixture_contract_bundle(
                state.contract.get("creative", {}).get("source_story", ""),
                story_version=state.story_version,
                style_version=state.style_version + 1,
                revision_request=req.revision_request,
            )
        else:
            config = config_manager.get_model_config("zhongshu", office_id="comic_production")
            bundle = await revise_visual_bible(
                state.contract,
                req.revision_request,
                config,
            )
        revised = ComicProductionV2.replace_visual_bible(state, bundle)
    except (PlannerError, ValueError) as exc:
        raise _comic_v2_http_error(
            502,
            department="中书省",
            reason=f"视觉母版修改失败：{exc}",
            impact="新视觉母版未生成，下游资产拆解仍会沿用旧版本或暂停。",
            next_action="检查中书省模型配置和退回意见是否清晰；修复后重新提交视觉母版修改。",
            stage=state.stage,
            agent=state.current_agent,
        ) from exc
    _save_comic_v2_state(workspace_id, revised.to_dict())
    _persist_comic_v2_contract(workspace, revised, "awaiting_user_review")
    config_manager.append_task_event(
        task_id=f"comic_v2_{workspace_id}",
        event_type="comic_v2_visual_bible_revised",
        status="waiting_for_human",
        summary="视觉母版已按退回意见生成新版本",
        payload={
            "workspace_id": workspace_id,
            "style_version": revised.style_version,
            "revision_request": req.revision_request,
        },
    )
    return _comic_v2_state_response(revised)


@app.post("/api/workspaces/{workspace_id}/comic/v2/assets/plan")
async def plan_comic_v2_assets_api(workspace_id: str):
    workspace = _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if not raw:
        raise _comic_v2_http_error(
            409,
            department="尚书省",
            reason="还没有可调度的 V2 制片状态。",
            impact="资产拆解无法开始，人物、道具和场景清单不会生成。",
            next_action="先完成故事确认，并生成、确认视觉母版。",
            stage="not_started",
        )
    state = ComicProductionV2.from_dict(raw)
    if state.stage != "asset_planning":
        raise _comic_v2_http_error(
            409,
            department="尚书省",
            reason=f"当前阶段不能生成资产拆解包：系统处在“{state.stage}”。",
            impact="资产拆解不会重新开始，避免覆盖当前阶段已经生成或等待审核的内容。",
            next_action=state.next_action or "请先确认视觉母版，或回到当前阶段继续处理。",
            stage=state.stage,
            agent=state.current_agent,
        )
    try:
        bundle = contract_bundle_from_dict(state.contract)
        if fixture_mode_enabled():
            manifest = fixture_initial_manifest(bundle)
        else:
            manifest = await plan_asset_manifest(
                bundle,
                config_manager.get_model_config("zhongshu", office_id="comic_production"),
                config_manager.get_model_config("menxia", office_id="comic_production"),
            )
        waiting = ComicProductionV2.attach_asset_manifest(state, manifest)
    except (ContractValidationError, AssetPlanningError, ValueError) as exc:
        raise _comic_v2_http_error(
            502,
            department="中书省 / 门下省",
            reason=f"资产拆解失败：{exc}",
            impact="人物、道具、场景清单没有通过生成或校验，后续提示词、图片和 Word 画布都会暂停。",
            next_action="检查故事合同是否完整；如果是模型返回质量问题，请重试或补充明确的退回意见。",
            stage=state.stage,
            agent=state.current_agent,
        ) from exc
    _save_comic_v2_state(workspace_id, waiting.to_dict())
    _persist_comic_v2_manifest(workspace, waiting, "awaiting_user_review")
    config_manager.append_task_event(
        task_id=f"comic_v2_{workspace_id}",
        event_type="comic_v2_asset_manifest_ready",
        status="waiting_for_human",
        summary="人物、道具和场景清单等待用户确认",
        payload={
            "workspace_id": workspace_id,
            "manifest_version": manifest.version,
            "asset_count": len(manifest.items),
        },
    )
    return _comic_v2_state_response(waiting)


@app.post("/api/workspaces/{workspace_id}/comic/v2/assets/approve")
async def approve_comic_v2_assets_api(workspace_id: str):
    workspace = _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if not raw:
        raise _comic_v2_http_error(
            409,
            department="门下省",
            reason="请先生成资产拆解包。",
            impact="资产拆解无法确认，提示词、图片和 Word 制片画布都会暂停。",
            next_action="先确认视觉母版，再生成资产拆解审核包。",
            stage="not_started",
        )
    try:
        current = ComicProductionV2.from_dict(raw)
        approved = ComicProductionV2.approve_asset_manifest(current)
    except ValueError as exc:
        raise _comic_v2_http_error(
            409,
            department="门下省",
            reason=f"当前阶段不能确认资产拆解包：{exc}",
            impact="资产拆解没有被确认时，提示词、图片和 Word 画布不会继续生产。",
            next_action=f"请先进入资产审核阶段并检查人物、道具、场景清单；当前阶段建议：{current.next_action or '继续处理当前阶段'}。",
            stage=current.stage,
            agent=current.current_agent,
        ) from exc
    _save_comic_v2_state(workspace_id, approved.to_dict())
    _persist_comic_v2_manifest(workspace, approved, "approved")
    config_manager.append_task_event(
        task_id=f"comic_v2_{workspace_id}",
        event_type="comic_v2_asset_manifest_approved",
        status="completed",
        summary="资产拆解包已确认，可以生成逐项提示词",
        payload={
            "workspace_id": workspace_id,
            "manifest_version": approved.asset_manifest.get("version", 0),
        },
    )
    return _comic_v2_state_response(approved)


@app.post("/api/workspaces/{workspace_id}/comic/v2/assets/revise")
async def revise_comic_v2_assets_api(workspace_id: str, req: ComicV2RevisionRequest):
    workspace = _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if not raw:
        raise _comic_v2_http_error(
            409,
            department="门下省",
            reason="请先生成资产拆解包。",
            impact="没有资产拆解包时无法退回修改，人物、道具和场景清单也无法进入人工审核。",
            next_action="先确认视觉母版，并生成资产拆解审核包。",
            stage="not_started",
        )
    state = ComicProductionV2.from_dict(raw)
    if state.stage != "asset_review" or not state.asset_manifest:
        raise _comic_v2_http_error(
            409,
            department="门下省",
            reason="当前没有可退回修改的资产拆解包。",
            impact="系统不会在非资产审核阶段重拆资产，避免覆盖当前阶段状态。",
            next_action=f"当前没有进入资产审核阶段。请先进入资产审核并查看资产拆解包；当前阶段建议：{state.next_action or '继续处理当前阶段'}。",
            stage=state.stage,
            agent=state.current_agent,
        )
    try:
        bundle = contract_bundle_from_dict(state.contract)
        previous = asset_manifest_from_dict(
            state.asset_manifest,
            source_story=bundle.creative.source_story,
        )
        if fixture_mode_enabled():
            manifest = fixture_revised_manifest(bundle, previous, req.revision_request)
        else:
            manifest = await plan_asset_manifest(
                bundle,
                config_manager.get_model_config("zhongshu", office_id="comic_production"),
                config_manager.get_model_config("menxia", office_id="comic_production"),
                revision_request=req.revision_request,
                previous_manifest=previous,
            )
        waiting = ComicProductionV2.attach_asset_manifest(state, manifest)
    except (ContractValidationError, AssetPlanningError, ValueError) as exc:
        raise _comic_v2_http_error(
            502,
            department="中书省 / 门下省",
            reason=f"资产重拆失败：{exc}",
            impact="新版人物、道具、场景清单没有通过生成或校验，提示词、图片和 Word 画布会暂停。",
            next_action="检查退回意见是否明确指出要增加、删除或修改哪些资产；修复模型配置后重新提交。",
            stage=state.stage,
            agent=state.current_agent,
        ) from exc
    _save_comic_v2_state(workspace_id, waiting.to_dict())
    _persist_comic_v2_manifest(workspace, waiting, "awaiting_user_review")
    config_manager.append_task_event(
        task_id=f"comic_v2_{workspace_id}",
        event_type="comic_v2_asset_manifest_revised",
        status="waiting_for_human",
        summary="资产拆解包已按退回意见生成新版本",
        payload={
            "workspace_id": workspace_id,
            "manifest_version": manifest.version,
            "revision_request": req.revision_request,
        },
    )
    return _comic_v2_state_response(waiting)


@app.post("/api/workspaces/{workspace_id}/comic/v2/prompts/plan")
async def plan_comic_v2_prompts_api(workspace_id: str):
    workspace = _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if not raw:
        raise _comic_v2_http_error(
            409,
            department="工部",
            reason="还没有可用于生成提示词的 V2 制片状态。",
            impact="资产提示词和镜头提示词不会生成，后续图片与 Word 画布都会暂停。",
            next_action="先确认故事、视觉母版和资产拆解包。",
            stage="not_started",
        )
    state = ComicProductionV2.from_dict(raw)
    prompt_recovery_stages = {
        "prompt_planning",
        "image_generation",
        "visual_review",
        "document_generation",
        "ready_for_handoff",
    }
    if state.stage not in prompt_recovery_stages or state.assets_status != "approved":
        raise _comic_v2_http_error(
            409,
            department="工部",
            reason=f"资产拆解包尚未确认，不能生成提示词：系统处在“{state.stage}”。",
            impact="提示词不会生成，避免基于未确认的人物、道具或场景继续生产。",
            next_action=state.next_action or "请先完成人物、道具、场景资产拆解审核。",
            stage=state.stage,
            agent=state.current_agent,
        )
    if state.stage != "prompt_planning":
        state = state.with_status(
            status="active",
            stage="prompt_planning",
            current_agent="工部 / 兵部",
            current_object="逐项资产提示词",
            blocking_reason="提示词质量门禁要求重新生成提示词，后续图片和交付会重新进入生产。",
            next_action="重新生成资产提示词和镜头执行卡，再继续生成基础资产图。",
            can_generate_images=False,
            shots_status="pending",
            image_production={},
            delivery={},
        )
    try:
        bundle = contract_bundle_from_dict(state.contract)
        manifest = asset_manifest_from_dict(
            state.asset_manifest,
            source_story=bundle.creative.source_story,
        )
        if fixture_mode_enabled():
            package = fixture_prompt_package(bundle, manifest)
        else:
            package = await direct_asset_prompts(
                bundle,
                manifest,
                _comic_v2_capability_model("gongbu_text", ("zhongshu",), kind="text"),
            )
            package = await direct_shot_cards(
                bundle,
                manifest,
                package,
                _comic_v2_capability_model("bingbu_text", ("bingbu", "zhongshu"), kind="text"),
        )
        generating = ComicProductionV2.attach_prompt_package(state, package)
    except (ContractValidationError, ProductionError, ValueError) as exc:
        raise _comic_v2_http_error(
            502,
            department="工部 / 兵部",
            reason=f"提示词规划失败：{exc}",
            impact="资产提示词或镜头执行卡没有生成，图片生产和 Word 制片画布都会暂停。",
            next_action="检查工部/兵部文本模型配置、API Key 和模型返回；必要时补充更明确的资产退回意见后重试。",
            stage=state.stage,
            agent=state.current_agent,
        ) from exc
    _save_comic_v2_state(workspace_id, generating.to_dict())
    config_manager.create_artifact(
        artifact_id=f"art_{workspace_id}_comic_v2_prompt_package_m{package.manifest_version}",
        workspace_id=workspace_id,
        task_id="",
        artifact_type="comic_v2_prompt_package",
        title=f"{workspace.get('title') or 'AI漫剧'} - V2资产与镜头提示词包",
        content=json.dumps(package.to_dict(), ensure_ascii=False, indent=2),
        metadata={
            "office_id": "comic_production",
            "pipeline_version": 2,
            "story_id": state.story_id,
            "style_id": state.style_id,
            "manifest_version": package.manifest_version,
            "asset_prompt_count": len(package.prompts),
            "shot_prompt_count": len(package.shots),
            "review_status": "system_validated",
        },
        created_by="gongbu",
    )
    config_manager.append_task_event(
        task_id=f"comic_v2_{workspace_id}",
        event_type="comic_v2_prompts_ready",
        status="completed",
        summary="逐项资产提示词和镜头提示词卡已生成",
        payload={
            "workspace_id": workspace_id,
            "asset_prompt_count": len(package.prompts),
            "shot_prompt_count": len(package.shots),
        },
    )
    return _comic_v2_state_response(generating)


@app.post("/api/workspaces/{workspace_id}/comic/v2/images/generate")
async def generate_comic_v2_images_api(workspace_id: str):
    workspace = _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if not raw:
        raise _comic_v2_http_error(
            409,
            department="工部",
            reason="还没有可用于生图的提示词包。",
            impact="基础资产图不会生成，视觉质检和 Word 画布也无法继续。",
            next_action="先完成资产拆解审核，并生成专属提示词。",
            stage="not_started",
        )
    state = ComicProductionV2.from_dict(raw)
    if state.stage not in {"image_generation", "visual_review"}:
        raise _comic_v2_http_error(
            409,
            department="工部",
            reason=f"当前阶段不能生成资产图片：系统处在“{state.stage}”。",
            impact="基础资产图不会生成，避免跳过提示词或重复覆盖当前视觉质检结果。",
            next_action=state.next_action or "请先生成专属提示词，再生成并质检基础资产图。",
            stage=state.stage,
            agent=state.current_agent,
        )
    task_id = _ensure_comic_v2_task_run(workspace, "生成并质检基础资产图")
    config_manager.update_task_run(task_id, "running", current_phase="image_generation")
    _append_comic_v2_event(
        workspace_id,
        event_type="comic_v2_images_started",
        status="running",
        summary="工部开始生成基础资产图，刑部随后执行视觉质检",
        payload={"stage": state.stage, "current_agent": state.current_agent},
    )
    try:
        bundle = contract_bundle_from_dict(state.contract)
        manifest = asset_manifest_from_dict(
            state.asset_manifest,
            source_story=bundle.creative.source_story,
        )
        package = prompt_package_from_dict(state.prompt_package)
        task_dir = f"comic_v2_m{manifest.version}"
        output_dir = (
            Path(__file__).parent.parent.parent
            / "output" / "workspaces" / workspace_id / "generated" / task_dir
        )
        if fixture_mode_enabled():
            result = fixture_image_production(package, manifest, output_dir)
        else:
            result = await produce_asset_images(
                package,
                manifest,
                bundle.visual,
                _comic_v2_capability_model("gongbu_image", ("gongbu",), kind="image"),
                _comic_v2_capability_model("xingbu_vision", ("xingbu",), kind="vision"),
                output_dir,
                max_attempts=max(1, int(os.getenv("COMIC_IMAGE_MAX_ATTEMPTS", "2"))),
        )
        next_state = ComicProductionV2.attach_image_production(state, result)
    except (ContractValidationError, ProductionError, ValueError) as exc:
        config_manager.update_task_run(
            task_id,
            "failed",
            current_phase="image_generation",
            error=f"资产图片生产失败：{exc}",
            completed=True,
        )
        _append_comic_v2_event(
            workspace_id,
            event_type="comic_v2_images_failed",
            status="failed",
            summary=f"基础资产图生产或质检失败：{exc}",
            payload={
                "office_id": "comic_production",
                "department": "工部 / 刑部",
                "stage": "image_generation",
                "agent": state.current_agent,
                "impact": "基础资产图没有完成生产或质检，Word 制片画布不会继续组装。",
                "next_action": "检查工部生图模型、刑部视觉模型、API Key、额度和图片输出目录；修复后重新生成并质检基础资产图。",
                "retry_action": {
                    "label": "重新生成并质检基础资产图",
                    "method": "POST",
                    "path": f"/api/workspaces/{workspace_id}/comic/v2/images/generate",
                },
            },
        )
        raise _comic_v2_http_error(
            502,
            department="工部 / 刑部",
            reason=f"资产图片生产失败：{exc}",
            impact="基础资产图没有完成生产或质检，Word 制片画布不会继续组装。",
            next_action="检查工部生图模型、刑部视觉模型、API Key、额度和图片输出目录；修复后重新生成并质检基础资产图。",
            stage=state.stage,
            agent=state.current_agent,
        ) from exc
    _save_comic_v2_state(workspace_id, next_state.to_dict())
    prompt_lookup = {
        (prompt.object_id, prompt.image_kind): prompt
        for prompt in package.prompts
    }
    for record in result.records:
        filename = Path(record.path).name
        prompt = prompt_lookup.get((record.asset_id, record.image_kind))
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_{record.image_id}",
            workspace_id=workspace_id,
            task_id=f"comic_v2_{workspace_id}",
            artifact_type="comic_v2_generated_image",
            title=f"{record.asset_id} / {record.image_kind}",
            uri=f"/api/workspaces/{workspace_id}/files/generated/{task_dir}/{filename}",
            content=json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
            metadata={
                **record.to_dict(),
                "usage_contract": list(prompt.usage_contract) if prompt else [],
                "reference_policy": prompt.reference_policy if prompt else "",
                "office_id": "comic_production",
                "pipeline_version": 2,
            },
            created_by="gongbu",
        )
    config_manager.create_artifact(
        artifact_id=f"art_{workspace_id}_comic_v2_visual_review_m{manifest.version}",
        workspace_id=workspace_id,
        task_id=f"comic_v2_{workspace_id}",
        artifact_type="comic_v2_visual_review",
        title=f"{workspace.get('title') or 'AI漫剧'} - V2跨图质检",
        content=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        metadata={
            "office_id": "comic_production",
            "pipeline_version": 2,
            "production_ready": result.production_ready,
            "record_count": len(result.records),
            "failure_count": len(result.failures),
        },
        created_by="xingbu",
    )
    config_manager.update_task_run(
        task_id,
        "completed" if result.production_ready else "running",
        current_phase=next_state.stage,
        result={"stage": next_state.stage, "generated": len(result.records), "failures": list(result.failures)},
        completed=bool(result.production_ready),
    )
    config_manager.append_task_event(
        task_id=task_id,
        event_type="comic_v2_images_reviewed",
        status="completed" if result.production_ready else "waiting_for_human",
        summary="基础资产图已完成跨图质检" if result.production_ready else "部分基础资产图需要人工处理",
        payload={
            "workspace_id": workspace_id,
            "generated": len(result.records),
            "failures": list(result.failures),
            "next_stage": next_state.stage,
        },
    )
    return _comic_v2_state_response(next_state)


@app.post("/api/workspaces/{workspace_id}/comic/v2/images/override")
async def override_comic_v2_visual_review_api(workspace_id: str, req: ComicV2VisualOverrideRequest):
    _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if not raw:
        raise _comic_v2_http_error(
            409,
            department="刑部",
            reason="当前没有待人工处理的视觉质检。",
            impact="无法执行人工放行，因为还没有图片质检结果需要处理。",
            next_action="先生成提示词，再生成并质检基础资产图。",
            stage="not_started",
        )
    try:
        state = ComicProductionV2.override_visual_review(
            ComicProductionV2.from_dict(raw),
            req.reason,
        )
    except ValueError as exc:
        current = ComicProductionV2.from_dict(raw)
        raise _comic_v2_http_error(
            400,
            department="刑部",
            reason=f"人工放行失败：{exc}",
            impact="视觉质检风险没有被记录，系统不会继续把图片交给 Word 画布组装。",
            next_action="填写明确的人工放行理由，说明为什么可以接受这些风险；或者返回重新生成图片。",
            stage=current.stage,
            agent=current.current_agent,
        ) from exc
    _save_comic_v2_state(workspace_id, state.to_dict())
    config_manager.append_task_event(
        task_id=f"comic_v2_{workspace_id}",
        event_type="comic_v2_visual_review_overridden",
        status="completed_with_risk",
        summary="用户已人工放行未完全通过的资产图片",
        payload={"workspace_id": workspace_id, "reason": req.reason.strip()},
    )
    return _comic_v2_state_response(state)


@app.post("/api/workspaces/{workspace_id}/comic/v2/delivery/build")
async def build_comic_v2_delivery_api(workspace_id: str):
    workspace = _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if not raw:
        raise _comic_v2_http_error(
            409,
            department="礼部",
            reason="当前没有可组装的 V2 制片包。",
            impact="Word 制片画布不会生成，因为故事、资产、图片和提示词还没有形成完整包。",
            next_action="先完成故事确认、资产拆解、提示词、图片生产和质检。",
            stage="not_started",
        )
    state = ComicProductionV2.from_dict(raw)
    if state.stage != "document_generation":
        raise _comic_v2_http_error(
            409,
            department="礼部",
            reason=f"图片生产与质检尚未完成：系统处在“{state.stage}”。",
            impact="Word 制片画布不会生成，避免交付缺图、缺资产引用或缺质检说明。",
            next_action=state.next_action or "请先生成并质检基础资产图。",
            stage=state.stage,
            agent=state.current_agent,
        )
    task_id = _ensure_comic_v2_task_run(workspace, "生成 Word 制片画布")
    config_manager.update_task_run(task_id, "running", current_phase="document_generation")
    _append_comic_v2_event(
        workspace_id,
        event_type="comic_v2_delivery_started",
        status="running",
        summary="礼部开始组装 Word 制片画布，并交由刑部结构审计",
        payload={"stage": state.stage, "current_agent": state.current_agent},
    )
    try:
        bundle = contract_bundle_from_dict(state.contract)
        manifest = asset_manifest_from_dict(
            state.asset_manifest,
            source_story=bundle.creative.source_story,
        )
        package = prompt_package_from_dict(state.prompt_package)
        images = image_production_result_from_dict(state.image_production)
        output_dir = Path(__file__).parent.parent.parent / "output" / "workspaces" / workspace_id / "delivery"
        delivery = build_delivery_from_v2(
            bundle,
            manifest,
            package,
            images,
            output_dir,
            allow_human_override=bool(state.image_production.get("human_override")),
        )
        uri = f"/api/workspaces/{workspace_id}/files/delivery/{delivery.path.name}"
        handoff_manifest_uri = (
            f"/api/workspaces/{workspace_id}/files/delivery/{delivery.handoff_manifest_path.name}"
            if delivery.handoff_manifest_path
            else ""
        )
        production_lineage = _comic_v2_handoff_production_lineage(delivery.handoff_manifest_path)
        asset_baseline_chains = _comic_v2_handoff_asset_baseline_chains(delivery.handoff_manifest_path)
        shot_production_packages = _comic_v2_handoff_shot_production_packages(delivery.handoff_manifest_path)
        quality_benchmark = _comic_v2_handoff_quality_benchmark(delivery.handoff_manifest_path)
        ready = ComicProductionV2.attach_delivery(
            state,
            str(delivery.path),
            delivery.audit,
            uri=uri,
            handoff_manifest_uri=handoff_manifest_uri,
            quality_benchmark=quality_benchmark,
        )
    except (ContractValidationError, DeliveryValidationError, ProductionError, ValueError) as exc:
        config_manager.update_task_run(
            task_id,
            "failed",
            current_phase="document_generation",
            error=f"Word 制片画布生成失败：{exc}",
            completed=True,
        )
        _append_comic_v2_event(
            workspace_id,
            event_type="comic_v2_delivery_failed",
            status="failed",
            summary=f"Word 制片画布生成失败：{exc}",
            payload={
                "office_id": "comic_production",
                "department": "礼部 / 刑部",
                "stage": "document_generation",
                "agent": state.current_agent,
                "impact": "最终交付文件没有生成，历史记录也不会出现可下载的完整制片画布。",
                "next_action": "检查礼部组装输入、资产引用链路和结构审计结果；修复缺失项后重新生成 Word 制片画布。",
                "retry_action": {
                    "label": "重新生成 Word 制片画布",
                    "method": "POST",
                    "path": f"/api/workspaces/{workspace_id}/comic/v2/delivery/build",
                },
            },
        )
        raise _comic_v2_http_error(
            502,
            department="礼部 / 刑部",
            reason=f"Word 制片画布生成失败：{exc}",
            impact="最终交付文件没有生成，历史记录也不会出现可下载的完整制片画布。",
            next_action="检查礼部组装输入、资产引用链路和结构审计结果；修复缺失项后重新生成 Word 制片画布。",
            stage=state.stage,
            agent=state.current_agent,
        ) from exc
    _save_comic_v2_state(workspace_id, ready.to_dict())
    config_manager.create_artifact(
        artifact_id=f"art_{workspace_id}_comic_v2_word_canvas",
        workspace_id=workspace_id,
        task_id=f"comic_v2_{workspace_id}",
        artifact_type="comic_v2_word_canvas",
        title=f"{workspace.get('title') or 'AI漫剧'} - V2制片画布",
        uri=uri,
        content="V2 制片画布已通过结构审计，可下载交付。",
        metadata={
            "office_id": "comic_production",
            "pipeline_version": 2,
            "story_id": state.story_id,
            "story_version": state.story_version,
            "style_id": state.style_id,
            "style_version": state.style_version,
            "manifest_version": state.asset_manifest.get("version", 0),
            "audit": ready.delivery.get("audit", {}),
            "download_uri": uri,
            "handoff_manifest_uri": handoff_manifest_uri,
            "quality_benchmark": quality_benchmark,
        },
        created_by="libu",
    )
    if handoff_manifest_uri:
        config_manager.create_artifact(
            artifact_id=f"art_{workspace_id}_comic_v2_handoff_manifest",
            workspace_id=workspace_id,
            task_id=f"comic_v2_{workspace_id}",
            artifact_type="comic_v2_handoff_manifest",
            title=f"{workspace.get('title') or 'AI漫剧'} - V2制片引用清单",
            uri=handoff_manifest_uri,
            content="V2 制片引用清单已生成，可用于排查资产、图片、镜头和 Word 画布的对应关系。",
            metadata={
                "office_id": "comic_production",
                "pipeline_version": 2,
                "story_id": state.story_id,
                "story_version": state.story_version,
                "style_id": state.style_id,
                "style_version": state.style_version,
                "manifest_version": state.asset_manifest.get("version", 0),
                "download_uri": handoff_manifest_uri,
                "word_canvas_uri": uri,
                "production_lineage": production_lineage,
                "assets": asset_baseline_chains,
                "shots": shot_production_packages,
                "quality_benchmark": quality_benchmark,
            },
            created_by="libu",
        )
    config_manager.update_task_run(
        task_id,
        "completed",
        current_phase="ready_for_handoff",
        result={"stage": ready.stage, "download_uri": uri, "quality_benchmark": quality_benchmark},
        completed=True,
    )
    config_manager.append_task_event(
        task_id=task_id,
        event_type="comic_v2_delivery_ready",
        status="completed",
        summary="页面式 Word 制片画布已通过审计",
        payload={"workspace_id": workspace_id, "download_uri": uri, "handoff_manifest_uri": handoff_manifest_uri},
    )
    return _comic_v2_state_response(ready)


@app.post("/api/workspaces/{workspace_id}/comic/v2/quality/recover")
async def recover_comic_v2_quality_api(workspace_id: str, req: ComicV2QualityRecoveryRequest):
    """Return a generated handoff to the department that can fix its quality blocker."""
    workspace = _comic_v2_workspace(workspace_id)
    raw = _load_comic_v2_state(workspace_id)
    if not raw:
        raise _comic_v2_http_error(
            409,
            department="尚书省 / 刑部",
            reason="当前项目没有可恢复的 V2 制片状态。",
            impact="无法判断应该退回故事、资产、提示词、图片还是交付阶段。",
            next_action="先完成一次 V2 制片流程，或从历史下载旧版交付物留档。",
            stage="not_started",
        )
    state = ComicProductionV2.from_dict(raw)
    benchmark = (state.delivery or {}).get("quality_benchmark") or {}
    recommended = benchmark.get("recommended_recovery") or {}
    requested_action = str(req.action or "").strip()
    recommended_action = str(recommended.get("action") or "").strip()
    real_quality_upgrade = (
        requested_action == "regenerate_images"
        and benchmark.get("production_quality_verified") is not True
    )
    if benchmark.get("package_quality_ready") is True and not real_quality_upgrade:
        raise _comic_v2_http_error(
            409,
            department="尚书省 / 刑部",
            reason="当前制片包已经通过质量基准，没有需要执行的质量退回动作。",
            impact="继续退回会重复消耗模型额度，并使已经验收的下游产物失效。",
            next_action="直接下载 Word 制片画布和引用清单，或在新项目中发起新的生产版本。",
            stage=state.stage,
            agent=state.current_agent,
        )
    if recommended_action and requested_action and requested_action != recommended_action:
        raise _comic_v2_http_error(
            409,
            department=str(recommended.get("department") or "尚书省 / 刑部"),
            reason=f"请求的恢复动作 {requested_action} 与质量基准建议 {recommended_action} 不一致。",
            impact="跳过责任阶段可能保留真正的阻塞问题，并生成一份看似更新但仍不可生产的交付包。",
            next_action=str(recommended.get("description") or "按质量基准给出的恢复动作重新提交。"),
            stage=state.stage,
            agent=state.current_agent,
        )
    action = recommended_action or requested_action
    if not action:
        raise _comic_v2_http_error(
            409,
            department="礼部 / 刑部",
            reason="当前交付包没有可执行的质量恢复建议。",
            impact="系统无法安全判断应该保留哪些上游产物。",
            next_action="如果这是早期 V2 包，请从历史入口选择“补齐 V3 引用与质量清单”。",
            stage=state.stage,
            agent=state.current_agent,
        )
    try:
        recovered = ComicProductionV2.reopen_for_quality_recovery(state, action)
    except ValueError as exc:
        raise _comic_v2_http_error(
            409,
            department=str(recommended.get("department") or "尚书省 / 刑部"),
            reason=f"质量恢复无法执行：{exc}",
            impact="现有交付文件会保留在历史中，但当前项目不会被错误地回退或覆盖。",
            next_action=str(recommended.get("description") or "回到工作台检查制片包质量基准和项目阶段。"),
            stage=state.stage,
            agent=state.current_agent,
        ) from exc
    _save_comic_v2_state(workspace_id, recovered.to_dict())
    _ensure_comic_v2_task_run(workspace, "按质量基准退回处理")
    _append_comic_v2_event(
        workspace_id,
        event_type="comic_v2_quality_recovery_started",
        status="running" if recovered.status == "active" else recovered.status,
        summary=f"制片包按质量基准退回：{recommended.get('label') or action}",
        payload={
            "office_id": "comic_production",
            "department": recommended.get("department") or recovered.current_agent,
            "stage": recovered.stage,
            "action": action,
            "reason_code": recommended.get("reason_code", ""),
            "next_action": recovered.next_action,
        },
    )
    return _comic_v2_state_response(recovered)


@app.post("/api/comic/brief")
async def create_comic_brief_api(req: ComicBriefRequest):
    """Create the comic office's first-turn creative brief and questions."""
    if not req.idea.strip():
        raise _comic_legacy_http_error(
            400,
            department="内阁",
            reason="还没有输入故事灵感，无法生成创作简报。",
            impact="主创无法判断题材、冲突和视觉方向，后续剧本预览会跑偏。",
            next_action="先输入一句故事灵感，或者切换到完整剧本模式粘贴已有剧本。",
            stage="story_brief",
        )
    return build_comic_brief(
        idea=req.idea,
        genre=req.genre,
        length=req.length,
        platform=req.platform,
        visual_style=req.visual_style,
        extra=req.extra,
    )


@app.post("/api/comic/script-preview")
async def create_comic_script_preview_api(req: ComicScriptPreviewRequest):
    """Create the cabinet's script preview before asset production."""
    if not req.idea.strip():
        raise _comic_legacy_http_error(
            400,
            department="内阁",
            reason="还没有输入故事灵感，无法生成剧本预览。",
            impact="主创没有可承接的故事基础，剧本预览无法判断主角、冲突和结尾。",
            next_action="先输入故事灵感并生成创作简报，再继续生成剧本预览。",
            stage="script_preview",
        )
    if not req.creative_brief:
        raise _comic_legacy_http_error(
            400,
            department="内阁",
            reason="缺少创作简报，不能直接生成剧本预览。",
            impact="剧本预览没有经过主创对齐，后续资产拆解和提示词可能偏离用户想法。",
            next_action="先点击开始聊故事/生成创作简报，确认方向后再生成剧本预览。",
            stage="script_preview",
        )
    return build_comic_script_preview(
        idea=req.idea,
        genre=req.genre,
        length=req.length,
        platform=req.platform,
        visual_style=req.visual_style,
        extra=req.extra,
        creative_brief=req.creative_brief,
        user_answers=req.user_answers,
    )

def _comic_cabinet_key(workspace_id: str) -> str:
    return f"comic_cabinet_session:{workspace_id}"


def _comic_cabinet_model_configs(office_id: str = "comic_production") -> dict:
    office_id = _normalize_comic_office_id(office_id)
    role_agents = {
        "首辅/制片人": "shangshu",
        "编剧顾问": "zhongshu",
        "导演顾问": "gongbu",
        "美术顾问": "gongbu",
        "连续性顾问": "xingbu",
    }
    return {
        role: config_manager.get_model_config(agent, office_id=office_id)
        for role, agent in role_agents.items()
    }


def _comic_prompt_model_configs(office_id: str = "comic_production") -> dict:
    office_id = _normalize_comic_office_id(office_id)
    return {
        agent: config_manager.get_model_config(agent, office_id=office_id)
        for agent in ("gongbu", "bingbu", "xingbu", "shangshu")
    }


def _load_comic_cabinet_session(workspace_id: str) -> dict:
    raw = config_manager.get_kv(_comic_cabinet_key(workspace_id), "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _save_comic_cabinet_session(workspace_id: str, session: dict) -> None:
    config_manager.set_kv(_comic_cabinet_key(workspace_id), json.dumps(session, ensure_ascii=False))


def _comic_cabinet_assistant_message(session: dict) -> str:
    message = str((session or {}).get("assistant_message") or "").strip()
    if message:
        return message
    for item in reversed((session or {}).get("messages") or []):
        if item.get("role") == "assistant":
            return str(item.get("content") or "").strip()
    return ""


def _workspace_comic_session(workspace_id: str, client_session: dict | None = None) -> dict:
    """Return the server-owned cabinet session, using client state only as first-save fallback."""
    saved = _load_comic_cabinet_session(workspace_id)
    if saved:
        return saved
    return client_session or {}


def _request_with_server_confirmed_script(user_request: str, confirmed_artifact: dict) -> str:
    request_text = user_request or ""
    base_request = request_text.split("Confirmed script:", 1)[0].strip()
    script_notes = request_text.rsplit("Script notes:", 1)[1].strip() if "Script notes:" in request_text else ""
    confirmed_content = (confirmed_artifact or {}).get("content", "").strip()
    sections = [
        base_request,
        "",
        "Confirmed script:",
        confirmed_content,
    ]
    if script_notes:
        sections.extend(["", "Script notes:", script_notes])
    return "\n".join(sections).strip()

def _latest_workspace_artifact_by_type(workspace_id: str, artifact_type: str) -> dict:
    artifacts = config_manager.list_artifacts(workspace_id=workspace_id)
    for artifact in reversed(artifacts):
        if artifact.get("artifact_type") == artifact_type:
            return artifact
    return {}


def _comic_v2_handoff_production_lineage(path: Path | None) -> list[dict]:
    """Read the generated V2 handoff manifest and expose a compact production trace."""
    if not path or not Path(path).exists():
        return []
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    lineage = payload.get("production_lineage")
    if not isinstance(lineage, list):
        return []
    allowed = {
        "stage",
        "stage_label",
        "department",
        "agent",
        "status",
        "human_checkpoint",
        "handoff_to",
        "acceptance_criteria",
        "output",
    }
    summary = []
    for item in lineage:
        if not isinstance(item, dict):
            continue
        stage = {key: str(item.get(key, "")) for key in allowed if item.get(key) is not None}
        if stage.get("stage") and stage.get("department") and stage.get("status"):
            summary.append(stage)
    return summary


def _comic_v2_handoff_asset_baseline_chains(path: Path | None) -> list[dict]:
    """Read compact asset identity chains from the generated V2 handoff manifest."""
    if not path or not Path(path).exists():
        return []
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return []
    summary = []
    for item in assets:
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("asset_id") or "")
        baseline_id = str(item.get("identity_baseline_image_id") or "")
        baseline_kind = str(item.get("identity_baseline_image_kind") or "")
        image_ids = [str(value) for value in (item.get("image_ids") or []) if value]
        image_ids_by_kind = {
            str(key): str(value)
            for key, value in (item.get("image_ids_by_kind") or {}).items()
            if key and value
        }
        if asset_id and baseline_id:
            summary.append({
                "asset_id": asset_id,
                "asset_type": str(item.get("asset_type") or ""),
                "name": str(item.get("name") or ""),
                "identity_baseline_image_id": baseline_id,
                "identity_baseline_image_kind": baseline_kind,
                "image_ids": image_ids,
                "image_ids_by_kind": image_ids_by_kind,
            })
    return summary


def _comic_v2_handoff_shot_production_packages(path: Path | None) -> list[dict]:
    """Read compact, machine-usable shot execution packages from the V2 handoff manifest."""
    if not path or not Path(path).exists():
        return []
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    shots = payload.get("shots")
    if not isinstance(shots, list):
        return []
    summary = []
    for item in shots:
        if not isinstance(item, dict):
            continue
        shot_id = str(item.get("shot_id") or "")
        first_frame = item.get("first_frame_reference_image") if isinstance(item.get("first_frame_reference_image"), dict) else {}
        reference_chain = item.get("reference_asset_chain") if isinstance(item.get("reference_asset_chain"), list) else []
        execution_steps = item.get("execution_steps") if isinstance(item.get("execution_steps"), list) else []
        if not shot_id:
            continue
        summary.append({
            "shot_id": shot_id,
            "scene_id": str(item.get("scene_id") or ""),
            "story_beat": str(item.get("story_beat") or ""),
            "first_frame_reference_image": {
                "asset_id": str(first_frame.get("asset_id") or ""),
                "image_id": str(first_frame.get("image_id") or ""),
                "image_kind": str(first_frame.get("image_kind") or ""),
                "file": str(first_frame.get("file") or ""),
            },
            "reference_asset_chain": [
                {
                    "asset_id": str(ref.get("asset_id") or ""),
                    "name": str(ref.get("name") or ""),
                    "asset_type": str(ref.get("asset_type") or ""),
                    "first_frame_file": str(ref.get("first_frame_file") or ""),
                }
                for ref in reference_chain
                if isinstance(ref, dict)
            ],
            "video_prompt_block": str(item.get("video_prompt_block") or ""),
            "negative_prompt_block": str(item.get("negative_prompt_block") or ""),
            "execution_steps": [str(step) for step in execution_steps if str(step).strip()],
        })
    return summary


def _comic_v2_handoff_quality_benchmark(path: Path | None) -> dict:
    """Read the human-facing package quality claim from a generated handoff manifest."""
    if not path or not Path(path).exists():
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    benchmark = payload.get("quality_benchmark")
    if not isinstance(benchmark, dict):
        return {}
    prompt_quality = benchmark.get("prompt_quality_summary")
    if not isinstance(prompt_quality, dict):
        prompt_quality = (audit_handoff_manifest(payload).get("prompt_quality_summary") or {})
    dimensions = []
    for item in benchmark.get("dimensions") or []:
        if not isinstance(item, dict):
            continue
        dimensions.append({
            "id": str(item.get("id") or ""),
            "label": str(item.get("label") or ""),
            "status": str(item.get("status") or ""),
            "score": int(item.get("score") or 0),
        })
    raw_recovery = benchmark.get("recommended_recovery") or {}
    recovery = {
        "department": str(raw_recovery.get("department") or ""),
        "action": str(raw_recovery.get("action") or ""),
        "focus": str(raw_recovery.get("focus") or ""),
        "label": str(raw_recovery.get("label") or ""),
        "reason_code": str(raw_recovery.get("reason_code") or ""),
        "description": str(raw_recovery.get("description") or ""),
        "expected_stage": str(raw_recovery.get("expected_stage") or ""),
        "preserves": [str(item) for item in (raw_recovery.get("preserves") or []) if str(item).strip()],
        "clears": [str(item) for item in (raw_recovery.get("clears") or []) if str(item).strip()],
        "operator_steps": [str(item) for item in (raw_recovery.get("operator_steps") or []) if str(item).strip()],
    } if isinstance(raw_recovery, dict) and raw_recovery else {}
    return {
        "benchmark_version": int(benchmark.get("benchmark_version") or 0),
        "status": str(benchmark.get("status") or ""),
        "package_quality_score": int(benchmark.get("package_quality_score") or 0),
        "package_quality_ready": bool(benchmark.get("package_quality_ready")),
        "production_quality_verified": bool(benchmark.get("production_quality_verified")),
        "visual_evidence_level": str(benchmark.get("visual_evidence_level") or ""),
        "summary": str(benchmark.get("summary") or ""),
        "issue_count": int(benchmark.get("issue_count") or 0),
        "blocker_count": int(benchmark.get("blocker_count") or 0),
        "dimensions": dimensions,
        "prompt_quality_summary": {
            "status": str(prompt_quality.get("status") or ""),
            "asset_prompt_count": int(prompt_quality.get("asset_prompt_count") or 0),
            "clean_asset_prompt_count": int(prompt_quality.get("clean_asset_prompt_count") or 0),
            "shot_prompt_count": int(prompt_quality.get("shot_prompt_count") or 0),
            "director_prompt_count": int(prompt_quality.get("director_prompt_count") or 0),
            "issue_count": int(prompt_quality.get("issue_count") or 0),
            "summary": str(prompt_quality.get("summary") or ""),
        },
        "limitations": [str(item) for item in (benchmark.get("limitations") or []) if str(item).strip()],
        "recommended_recovery": recovery,
        "next_action": str(benchmark.get("next_action") or ""),
    }


def _current_confirmed_script_metadata(workspace_id: str) -> dict:
    artifact = _latest_workspace_artifact_by_type(workspace_id, "confirmed_script")
    return artifact.get("metadata") or {}


def _asset_review_approved(workspace_id: str, script_hash: str = "") -> bool:
    artifact = _latest_workspace_artifact_by_type(workspace_id, "asset_review_package")
    metadata = artifact.get("metadata") or {}
    if metadata.get("review_status") != "approved":
        return False
    expected_hash = script_hash or _current_confirmed_script_metadata(workspace_id).get("script_hash", "")
    review_hash = metadata.get("script_hash", "")
    if expected_hash and review_hash and expected_hash != review_hash:
        return False
    if expected_hash and not review_hash:
        return False
    return True


def _rewrite_artifact_with_metadata(artifact: dict, metadata: dict) -> None:
    if not artifact:
        return
    config_manager.create_artifact(
        artifact_id=artifact["artifact_id"],
        workspace_id=artifact.get("workspace_id", ""),
        task_id=artifact.get("task_id", ""),
        artifact_type=artifact.get("artifact_type", ""),
        title=artifact.get("title", ""),
        uri=artifact.get("uri", ""),
        content=artifact.get("content", ""),
        metadata=metadata,
        created_by=artifact.get("created_by", ""),
    )


def _mark_artifact_invalidated(
    artifact: dict,
    reason: str,
    scope: str,
    *,
    current_script_hash: str = "",
    current_script_version: int = 0,
    replaced_by_artifact_id: str = "",
) -> None:
    if not artifact:
        return
    metadata = dict(artifact.get("metadata") or {})
    metadata.update({
        "invalidated": True,
        "invalidated_reason": reason,
        "invalidated_scope": scope,
        "invalidated_at": datetime.now(timezone.utc).isoformat(),
    })
    if current_script_hash:
        metadata["current_script_hash"] = current_script_hash
    if current_script_version:
        metadata["current_script_version"] = current_script_version
    if replaced_by_artifact_id:
        metadata["replaced_by_artifact_id"] = replaced_by_artifact_id
    _rewrite_artifact_with_metadata(artifact, metadata)


def _invalidate_outdated_comic_artifacts(
    workspace_id: str,
    *,
    current_script_hash: str,
    current_script_version: int,
    confirmed_artifact_id: str,
) -> int:
    updated = 0
    for artifact in config_manager.list_artifacts(workspace_id=workspace_id):
        if artifact.get("artifact_id") == confirmed_artifact_id:
            continue
        metadata = artifact.get("metadata") or {}
        artifact_script_hash = metadata.get("script_hash", "")
        if not artifact_script_hash or artifact_script_hash == current_script_hash:
            continue
        _mark_artifact_invalidated(
            artifact,
            reason="confirmed_script_changed",
            scope="script",
            current_script_hash=current_script_hash,
            current_script_version=current_script_version,
        )
        updated += 1
    return updated


def _ensure_comic_workspace(workspace_id: str, idea: str, office_id: str = "comic_production") -> str:
    office_id = _normalize_comic_office_id(office_id)
    workspace = config_manager.get_workspace(workspace_id) if workspace_id else {}
    if workspace:
        if not _is_comic_office_id(workspace.get("office_id")):
            raise _comic_legacy_http_error(
                404,
                department="尚书省",
                reason=f"漫剧工作空间 {workspace_id} 不存在或不属于漫剧办公室。",
                impact="内阁会话无法归档到正确项目，继续操作可能串到其他办公室。",
                next_action="回到 AI 漫剧制片办公室重新选择项目，或新建一个漫剧项目。",
                stage="workspace_lookup",
            )
        return workspace["workspace_id"]
    new_workspace_id = f"ws_{str(uuid.uuid4())[:8]}"
    title = (idea or "AI漫剧项目").strip()[:40] or "AI漫剧项目"
    brief = f"内阁讨论中：{title}"
    config_manager.create_workspace(
        workspace_id=new_workspace_id,
        office_id=office_id,
        title=title,
        brief=brief,
    )
    return new_workspace_id


@app.post("/api/comic/cabinet/turn")
async def comic_cabinet_turn_api(req: ComicCabinetTurnRequest):
    """Run one cabinet discussion turn and keep refining the script draft."""
    if not req.idea.strip():
        raise _comic_legacy_http_error(
            400,
            department="内阁",
            reason="缺少创作灵感，无法开始主创对话。",
            impact="没有灵感时，内阁无法判断故事方向、人物关系和第一轮追问，后续确认故事也无法开始。",
            next_action="先输入一句最粗糙的想法，例如“学生要跳楼，母亲苦苦哀求”。",
            stage="story_discussion",
        )
    office_id = _normalize_comic_office_id(req.office_id)
    workspace_id = _ensure_comic_workspace(req.workspace_id, req.idea, office_id=office_id)
    workspace = config_manager.get_workspace(workspace_id)
    office_id = _normalize_comic_office_id(workspace.get("office_id") if workspace else office_id)
    session = _workspace_comic_session(workspace_id, req.session)
    role_model_configs = _comic_cabinet_model_configs(office_id)
    if session:
        if not req.user_message.strip() and not req.session:
            return {
                "workspace_id": workspace_id,
                "office_id": office_id,
                "status": "script_ready" if session.get("ready_to_produce") else "needs_more_discussion",
                "stage": session.get("stage", "drafting"),
                "ready_to_produce": bool(session.get("ready_to_produce")),
                "assistant_message": _comic_cabinet_assistant_message(session),
                "cabinet_roles": session.get("cabinet_roles", []),
                "creative_brief": session.get("creative_brief", {}),
                "script_preview": session.get("script_preview", {}),
                "confirmed_script": session.get("confirmed_script", {}),
                "session": session,
                "preview": session.get("preview", ""),
            }
        session.update(
            {
                "idea": req.idea,
                "genre": req.genre,
                "length": req.length,
                "platform": req.platform,
                "visual_style": req.visual_style,
                "extra": req.extra,
            }
        )
        try:
            result = await advance_comic_cabinet_session_llm(
                session,
                req.user_message,
                role_model_configs=role_model_configs,
            )
        except Exception as e:
            result = advance_comic_cabinet_session(session, req.user_message)
            result.setdefault("session", {})["llm_fallback_error"] = str(e)
    else:
        try:
            result = await start_comic_cabinet_session_llm(
                idea=req.idea,
                genre=req.genre,
                length=req.length,
                platform=req.platform,
                visual_style=req.visual_style,
                extra=req.extra,
                role_model_configs=role_model_configs,
            )
        except Exception as e:
            result = start_comic_cabinet_session(
                idea=req.idea,
                genre=req.genre,
                length=req.length,
                platform=req.platform,
                visual_style=req.visual_style,
                extra=req.extra,
            )
            result.setdefault("session", {})["llm_fallback_error"] = str(e)
        if req.user_message.strip():
            try:
                result = await advance_comic_cabinet_session_llm(
                    result["session"],
                    req.user_message,
                    role_model_configs=role_model_configs,
                )
            except Exception as e:
                result = advance_comic_cabinet_session(result["session"], req.user_message)
                result.setdefault("session", {})["llm_fallback_error"] = str(e)
    _save_comic_cabinet_session(workspace_id, result["session"])
    return {"workspace_id": workspace_id, "office_id": office_id, **result}


@app.post("/api/comic/confirm-script")
async def confirm_comic_script_api(req: ComicConfirmScriptRequest):
    """Freeze the current cabinet draft as the confirmed script before production."""
    workspace = config_manager.get_workspace(req.workspace_id)
    if not workspace or not _is_comic_office_id(workspace.get("office_id")):
        raise _comic_legacy_http_error(
            404,
            department="尚书省",
            reason=f"漫剧工作空间 {req.workspace_id} 不存在。",
            impact="系统无法找到要确认的项目，确认剧本和后续生产都不会执行。",
            next_action="先选择一个已有漫剧项目，或重新创建一个新项目。",
            stage="script_confirmation",
        )
    office_id = _normalize_comic_office_id(workspace.get("office_id"))
    session = _workspace_comic_session(req.workspace_id, req.session)
    if not session:
        raise _comic_legacy_http_error(
            400,
            department="内阁",
            reason="请先完成内阁讨论，再确认剧本。",
            impact="没有内阁讨论记录时，系统无法知道用户认可的故事版本，确认剧本会变成盲盒。",
            next_action="回到工作台点击“开始聊故事”，让主创先和你对齐故事。",
            stage="script_confirmation",
        )
    issues = validate_confirmed_script_session(session)
    if issues:
        raise _comic_legacy_http_error(
            400,
            department="门下省",
            reason="确认剧本前仍有问题：" + "；".join(issues),
            impact="剧本信息不完整会导致人物、道具、场景拆解和后续提示词跑偏。",
            next_action="继续补充主角、冲突、结尾或关键场面后再确认剧本。",
            stage="script_confirmation",
        )
    confirmed_script = build_confirmed_script(session, req.confirmation_notes)
    if not confirmed_script:
        raise _comic_legacy_http_error(
            400,
            department="门下省",
            reason="当前剧本草案还不完整，无法确认。",
            impact="不完整的剧本无法进入生产链，资产拆解和制片画布会缺少依据。",
            next_action="继续和内阁补全故事起因、发展、结尾和关键转折。",
            stage="script_confirmation",
        )
    content = format_confirmed_script(confirmed_script)
    artifact_id = f"art_{req.workspace_id}_confirmed_script"
    config_manager.create_artifact(
        artifact_id=artifact_id,
        workspace_id=req.workspace_id,
        task_id="",
        artifact_type="confirmed_script",
        title=f"{confirmed_script.get('title', 'AI漫剧')} - 确认版剧本",
        content=content,
        metadata={
            "office_id": office_id,
            "confirmed": True,
            "script_hash": confirmed_script.get("script_hash", ""),
            "script_version": confirmed_script.get("script_version", 1),
            "issues": issues,
        },
        created_by="shangshu",
    )
    session["confirmed_script"] = confirmed_script
    session["confirmed_script_artifact_id"] = artifact_id
    session["confirmed_script_content"] = content
    session["confirmed"] = True
    _save_comic_cabinet_session(req.workspace_id, session)
    invalidated_count = _invalidate_outdated_comic_artifacts(
        req.workspace_id,
        current_script_hash=confirmed_script.get("script_hash", ""),
        current_script_version=confirmed_script.get("script_version", 1),
        confirmed_artifact_id=artifact_id,
    )
    config_manager.append_task_event(
        task_id=f"comic_confirm_{req.workspace_id}",
        event_type="comic_script_confirmed",
        status="completed",
        summary="Comic script confirmed and frozen for production",
        payload={
            "workspace_id": req.workspace_id,
            "artifact_id": artifact_id,
            "script_hash": confirmed_script.get("script_hash", ""),
            "script_version": confirmed_script.get("script_version", 1),
            "invalidated_count": invalidated_count,
        },
    )
    return {
        "workspace_id": req.workspace_id,
        "office_id": office_id,
        "status": "confirmed",
        "confirmed_script": confirmed_script,
        "artifact_id": artifact_id,
        "invalidated_count": invalidated_count,
        "content": content,
    }


@app.post("/api/comic/confirm-and-start")
async def confirm_and_start_comic_api(req: ComicConfirmAndStartRequest):
    """Freeze the story and immediately enqueue the comic production task."""
    confirmed = await confirm_comic_script_api(ComicConfirmScriptRequest(
        workspace_id=req.workspace_id,
        office_id=req.office_id,
        session=req.session,
        confirmation_notes=req.confirmation_notes,
    ))
    confirmed_script = confirmed.get("confirmed_script") or {}
    office_id = _normalize_comic_office_id(confirmed.get("office_id") or req.office_id)
    base_request = (req.user_request or "").strip()
    if "Confirmed script:" not in base_request:
        base_request = "\n".join([
            f"Idea: {confirmed_script.get('title', 'AI comic story')}",
            "",
            "Confirmed script:",
            confirmed.get("content", ""),
        ])
    started = await create_task(TaskRequest(
        user_request=base_request,
        template_id=req.template_id,
        office_id=office_id,
        workspace_id=req.workspace_id,
    ))
    return {
        **started,
        "confirmed_script": confirmed_script,
        "artifact_id": confirmed.get("artifact_id", ""),
        "invalidated_count": confirmed.get("invalidated_count", 0),
    }


def _record_comic_asset_review_decision(
    workspace_id: str,
    *,
    status: str,
    reviewer_notes: str = "",
) -> dict:
    workspace = config_manager.get_workspace(workspace_id)
    if not workspace or not _is_comic_office_id(workspace.get("office_id")):
        raise _comic_legacy_http_error(
            404,
            department="尚书省",
            reason=f"漫剧工作空间 {workspace_id} 不存在。",
            impact="无法记录资产审核结果，后续图片和 Word 画布不会继续生产。",
            next_action="先选择一个有效的 AI 漫剧项目。",
            stage="asset_review",
        )
    normalized_status = (status or "approved").strip().lower()
    allowed_statuses = {"approved", "revision_requested", "pending"}
    if normalized_status not in allowed_statuses:
        raise _comic_legacy_http_error(
            400,
            department="门下省",
            reason=f"资产审核状态不支持：{status}",
            impact="系统无法判断你是要通过、退回还是暂存资产拆解包。",
            next_action="请使用 approved、revision_requested 或 pending。",
            stage="asset_review",
        )
    artifact = _latest_workspace_artifact_by_type(workspace_id, "asset_review_package")
    if not artifact:
        raise _comic_legacy_http_error(
            404,
            department="门下省",
            reason="资产审核包还没有生成。",
            impact="没有资产审核包时，用户无法确认人物、道具和场景，后续图片生产会暂停。",
            next_action="先完成剧本确认，并生成资产拆解包后再进行资产审核。",
            stage="asset_review",
        )
    confirmed_metadata = _current_confirmed_script_metadata(workspace_id)
    current_hash = confirmed_metadata.get("script_hash", "")
    current_version = confirmed_metadata.get("script_version", 0)
    metadata = dict(artifact.get("metadata") or {})
    artifact_hash = metadata.get("script_hash", "")
    if current_hash and artifact_hash and artifact_hash != current_hash:
        raise _comic_legacy_http_error(
            409,
            department="门下省",
            reason="资产审核包属于旧剧本版本。",
            impact="继续审核旧资产会污染当前剧本，导致图片和 Word 画布引用错误。",
            next_action="请先重新生成当前剧本的资产拆解包，再审核资产。",
            stage="asset_review",
        )
    metadata.update({
        "requires_human_review": True,
        "review_status": normalized_status,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    })
    if current_hash:
        metadata["script_hash"] = current_hash
    if current_version:
        metadata["script_version"] = current_version
    if reviewer_notes.strip():
        metadata["reviewer_notes"] = reviewer_notes.strip()
    _rewrite_artifact_with_metadata(artifact, metadata)
    event_type = "comic_asset_review_approved" if normalized_status == "approved" else "comic_asset_review_revision_requested"
    config_manager.append_task_event(
        task_id=artifact.get("task_id") or f"asset_review_{workspace_id}",
        event_type=event_type,
        status="completed" if normalized_status == "approved" else "needs_revision",
        summary="Comic production asset review decision recorded",
        payload={
            "workspace_id": workspace_id,
            "artifact_id": artifact.get("artifact_id"),
            "review_status": normalized_status,
            "script_hash": metadata.get("script_hash", ""),
        },
    )
    return {"workspace_id": workspace_id, "status": normalized_status, "artifact_id": artifact.get("artifact_id"), "metadata": metadata}


@app.post("/api/workspaces/{workspace_id}/comic/asset-review/decision")
async def decide_comic_asset_review_api(workspace_id: str, req: ComicAssetReviewDecisionRequest):
    return _record_comic_asset_review_decision(
        workspace_id,
        status=req.status,
        reviewer_notes=req.reviewer_notes,
    )


@app.post("/api/workspaces/{workspace_id}/comic/asset-review/approve")
async def approve_comic_asset_review_api(workspace_id: str, req: Optional[ComicAssetReviewDecisionRequest] = None):
    decision = req or ComicAssetReviewDecisionRequest(status="approved")
    return _record_comic_asset_review_decision(
        workspace_id,
        status="approved",
        reviewer_notes=decision.reviewer_notes,
    )


@app.get("/api/comic/cabinet/{workspace_id}")
async def get_comic_cabinet_session_api(workspace_id: str):
    """Load the saved comic cabinet discussion for one workspace."""
    workspace = config_manager.get_workspace(workspace_id)
    if not workspace or not _is_comic_office_id(workspace.get("office_id")):
        raise _comic_legacy_http_error(
            404,
            department="尚书省",
            reason=f"漫剧工作空间 {workspace_id} 不存在或不属于漫剧办公室。",
            impact="无法读取该项目的内阁讨论、剧本确认和生产状态。",
            next_action="回到 AI 漫剧制片办公室重新选择项目；如果项目不存在，请重新开始聊故事。",
            stage="workspace_lookup",
        )
    session = _load_comic_cabinet_session(workspace_id)
    if not session:
        return {"workspace_id": workspace_id, "office_id": workspace.get("office_id", "comic"), "status": "empty"}
    return {
        "workspace_id": workspace_id,
        "office_id": workspace.get("office_id", "comic"),
        "status": "ok",
        "session": session,
        "creative_brief": session.get("creative_brief") or {},
        "script_preview": session.get("script_preview") or {},
        "confirmed_script": session.get("confirmed_script") or {},
        "confirmed": bool(session.get("confirmed")),
        "ready_to_produce": bool(session.get("ready_to_produce")),
        "stage": session.get("stage") or "",
        "assistant_message": _comic_cabinet_assistant_message(session),
    }


@app.get("/api/workspaces/{workspace_id}/export")
async def export_workspace_api(workspace_id: str):
    """Export all workspace artifacts as a zip package."""
    workspace = config_manager.get_workspace(workspace_id)
    if not workspace:
        raise _missing_workspace_http_error(workspace_id, stage="workspace_export")
    artifacts = config_manager.list_artifacts(workspace_id=workspace_id)
    export_dir = Path(__file__).parent.parent.parent / "output" / "workspaces"
    export_dir.mkdir(parents=True, exist_ok=True)
    zip_path = export_dir / f"{workspace_id}.zip"

    def safe_name(text: str) -> str:
        import re
        return re.sub(r'[<>:"/\\|?*]+', "_", text or "artifact")[:80]

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        overview = {
            "workspace": workspace,
            "artifact_count": len(artifacts),
        }
        zf.writestr("workspace.json", json.dumps(overview, ensure_ascii=False, indent=2))
        for index, artifact in enumerate(artifacts, start=1):
            filename = f"{index:02d}_{artifact.get('artifact_type','artifact')}_{safe_name(artifact.get('title',''))}.md"
            body = [
                f"# {artifact.get('title', 'Artifact')}",
                "",
                f"- Type: {artifact.get('artifact_type', '')}",
                f"- Created by: {artifact.get('created_by', '')}",
                f"- Created at: {artifact.get('created_at', '')}",
                "",
                artifact.get("content", ""),
                "",
            ]
            zf.writestr(filename, "\n".join(body))
            uri = artifact.get("uri") or ""
            if uri.startswith("/api/workspaces/") and "/files/generated/" in uri:
                generated_relative = uri.split("/files/generated/", 1)[1]
                generated_parts = [Path(part).name for part in generated_relative.split("/") if part]
                generated_path = export_dir / workspace_id / "generated" / Path(*generated_parts)
                if generated_path.exists():
                    zf.write(generated_path, str(Path("generated", *generated_parts)).replace("\\", "/"))
            if uri.startswith("/api/workspaces/") and "/files/delivery/" in uri:
                delivery_name = uri.rsplit("/", 1)[-1]
                delivery_path = export_dir / workspace_id / "delivery" / delivery_name
                if delivery_path.exists():
                    zf.write(delivery_path, f"delivery/{delivery_name}")
    return FileResponse(str(zip_path), filename=f"{workspace_id}.zip")


@app.post("/api/workspaces/{workspace_id}/artifacts")
async def create_workspace_artifact_api(workspace_id: str, req: ArtifactCreate):
    """Create an artifact in a workspace."""
    if not config_manager.get_workspace(workspace_id):
        raise _missing_workspace_http_error(workspace_id)
    artifact_id = f"art_{str(uuid.uuid4())[:8]}"
    config_manager.create_artifact(
        artifact_id=artifact_id,
        workspace_id=workspace_id,
        task_id=req.task_id,
        artifact_type=req.artifact_type,
        title=req.title,
        uri=req.uri,
        content=req.content,
        metadata=req.metadata,
        created_by="human",
    )
    return {"artifact_id": artifact_id, "status": "created"}


@app.post("/api/workspaces/{workspace_id}/evidence")
async def upload_workspace_evidence_api(
    workspace_id: str,
    file: UploadFile = File(...),
    note: str = Form(""),
):
    """Upload screenshot evidence into a research workspace."""
    workspace = config_manager.get_workspace(workspace_id)
    if not workspace:
        raise _research_http_error(
            404,
            department="尚书省",
            reason=f"工作空间 {workspace_id} 不存在。",
            impact="截图证据无法归档到项目，后续报告和证据表不会包含这份材料。",
            next_action="先新建或选择一个研究办公室项目，再上传截图证据。",
            stage="evidence_upload",
        )

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_EVIDENCE_TYPES:
        raise _research_http_error(
            400,
            department="户部 / 刑部",
            reason="截图格式不支持，目前只支持 png、jpg、webp、gif。",
            impact="证据无法入库，户部无法整理截图数据，刑部也无法做视觉识别。",
            next_action="请重新上传 png、jpg、webp 或 gif 格式的截图。",
            stage="evidence_upload",
        )

    raw = await file.read()
    max_size = 12 * 1024 * 1024
    if len(raw) > max_size:
        raise _research_http_error(
            400,
            department="户部",
            reason="截图文件过大，不能超过 12MB。",
            impact="证据无法入库，后续数据识别和报告引用都会缺少这张截图。",
            next_action="请压缩截图，或裁剪为更小的页面区域后重新上传。",
            stage="evidence_upload",
        )

    original_name = Path(file.filename or "screenshot").name
    safe_stem = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", Path(original_name).stem).strip("_")
    safe_stem = safe_stem[:60] or "screenshot"
    suffix = ALLOWED_EVIDENCE_TYPES[content_type]
    evidence_id = str(uuid.uuid4())[:8]
    saved_name = f"{evidence_id}_{safe_stem}{suffix}"

    evidence_dir = Path(__file__).parent.parent.parent / "output" / "workspaces" / workspace_id / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    file_path = evidence_dir / saved_name
    file_path.write_bytes(raw)

    artifact_id = f"art_ev_{evidence_id}"
    uri = f"/api/workspaces/{workspace_id}/files/evidence/{saved_name}"
    title = f"截图证据：{original_name}"
    content = "\n".join([
        f"文件名：{original_name}",
        f"大小：{len(raw)} bytes",
        f"说明：{note or '用户上传的截图证据，等待视觉模型识别。'}",
        "",
        "状态：已入库，待户部/兵部使用千问视觉模型提取结构化数据。",
    ])
    metadata = {
        "original_filename": original_name,
        "stored_filename": saved_name,
        "content_type": content_type,
        "size": len(raw),
        "note": note,
        "evidence_kind": "screenshot",
        "extraction_status": "pending_visual_model",
        "recommended_agents": ["hubu", "bingbu", "xingbu", "gongbu"],
    }
    config_manager.create_artifact(
        artifact_id=artifact_id,
        workspace_id=workspace_id,
        task_id="",
        artifact_type="screenshot_evidence",
        title=title,
        uri=uri,
        content=content,
        metadata=metadata,
        created_by="human",
    )
    _sync_workspace_evidence_artifacts(workspace_id)
    return {
        "artifact_id": artifact_id,
        "workspace_id": workspace_id,
        "uri": uri,
        "status": "uploaded",
        "metadata": metadata,
    }


@app.get("/api/workspaces/{workspace_id}/files/evidence/{filename}")
async def get_workspace_evidence_file_api(workspace_id: str, filename: str):
    """Return a stored workspace evidence image."""
    if not config_manager.get_workspace(workspace_id):
        raise _research_http_error(
            404,
            department="尚书省",
            reason=f"工作空间 {workspace_id} 不存在。",
            impact="无法读取截图证据，报告里的截图引用也无法打开。",
            next_action="先回到研究办公室选择有效项目，或重新上传截图证据。",
            stage="evidence_file_download",
        )
    safe_name = Path(filename).name
    file_path = Path(__file__).parent.parent.parent / "output" / "workspaces" / workspace_id / "evidence" / safe_name
    if not file_path.exists():
        raise _research_http_error(
            404,
            department="户部",
            reason=f"截图文件 {safe_name} 不存在或已被移动。",
            impact="这张截图不能预览、识别或写入最终报告。",
            next_action="重新上传截图，或重新执行自动截图后再做图片识别。",
            stage="evidence_file_download",
        )
    return FileResponse(str(file_path))


@app.get("/api/workspaces/{workspace_id}/files/generated/{filename}")
async def get_workspace_generated_file_api(workspace_id: str, filename: str):
    """Return a generated workspace image."""
    if not config_manager.get_workspace(workspace_id):
        raise _workspace_actionable_http_error(
            workspace_id,
            404,
            department="尚书省",
            reason=f"工作空间 {workspace_id} 不存在。",
            impact="无法读取这个项目的生成图片，历史记录里的图片链接也会失效。",
            next_action="回到对应办公室选择有效项目，或重新生成制片/调研产物。",
            stage="generated_file_download",
        )
    safe_name = Path(filename).name
    file_path = Path(__file__).parent.parent.parent / "output" / "workspaces" / workspace_id / "generated" / safe_name
    if not file_path.exists():
        raise _workspace_actionable_http_error(
            workspace_id,
            404,
            department="工部",
            reason=f"生成图片 {safe_name} 不存在或已被清理。",
            impact="Word 画布、历史详情或资产审核里的这张图片无法展示。",
            next_action="重新生成基础资产图片；如果只是历史项目，请重新下载最新的 Word 画布。",
            stage="generated_file_download",
        )
    return FileResponse(str(file_path))


@app.get("/api/workspaces/{workspace_id}/files/generated/{task_id}/{filename}")
async def get_workspace_task_generated_file_api(workspace_id: str, task_id: str, filename: str):
    """Return an image from one isolated comic production task."""
    if not config_manager.get_workspace(workspace_id):
        raise _workspace_actionable_http_error(
            workspace_id,
            404,
            department="尚书省",
            reason=f"工作空间 {workspace_id} 不存在。",
            impact="无法读取该任务隔离目录下的图片，制片画布引用会失效。",
            next_action="回到对应办公室选择有效项目，或重新执行当前生产任务。",
            stage="generated_file_download",
        )
    safe_task_id = Path(task_id).name
    safe_name = Path(filename).name
    file_path = (
        Path(__file__).parent.parent.parent
        / "output" / "workspaces" / workspace_id / "generated" / safe_task_id / safe_name
    )
    if not file_path.exists():
        raise _workspace_actionable_http_error(
            workspace_id,
            404,
            department="工部",
            reason=f"任务 {safe_task_id} 的生成图片 {safe_name} 不存在或已被清理。",
            impact="这个任务的资产图片无法展示，Word 画布中对应图片也可能缺失。",
            next_action="重新生成该任务的基础资产图片，或从历史里下载已存在的 Word 画布。",
            stage="generated_file_download",
        )
    return FileResponse(str(file_path))


@app.get("/api/workspaces/{workspace_id}/files/delivery/{filename}")
async def get_workspace_delivery_file_api(workspace_id: str, filename: str):
    """Return a generated delivery document."""
    if not config_manager.get_workspace(workspace_id):
        raise _workspace_actionable_http_error(
            workspace_id,
            404,
            department="尚书省",
            reason=f"工作空间 {workspace_id} 不存在。",
            impact="无法下载这个项目的交付文档，历史记录里的下载入口也会失效。",
            next_action="回到对应办公室选择有效项目，或重新生成交付文档。",
            stage="delivery_download",
        )
    safe_name = Path(filename).name
    file_path = Path(__file__).parent.parent.parent / "output" / "workspaces" / workspace_id / "delivery" / safe_name
    if not file_path.exists():
        raise _workspace_actionable_http_error(
            workspace_id,
            404,
            department="礼部",
            reason=f"交付文档 {safe_name} 不存在或已被移动。",
            impact="用户无法下载 Word 画布，也无法把这份结果交给下游平台继续生产。",
            next_action="重新点击“生成 Word 制片画布/交付文档”；如果任务已过期，请从当前项目重新生产。",
            stage="delivery_download",
        )
    return FileResponse(str(file_path), filename=safe_name)


@app.post("/api/artifacts/{artifact_id}/regenerate-comic-image")
async def regenerate_comic_image_api(artifact_id: str, req: ComicImageRegenerateRequest):
    """Regenerate one generated comic image with optional user instructions."""
    source = config_manager.get_artifact(artifact_id)
    if not source:
        raise _comic_v2_http_error(
            404,
            department="工部",
            reason=f"图片产物 {artifact_id} 不存在，无法重生成。",
            impact="用户无法针对这张图进行修正，资产一致性问题也无法通过重生成解决。",
            next_action="回到资产图片列表选择真实存在的图片；如果图片已被清理，请重新生成基础资产图。",
            stage="image_regeneration",
        )
    if source.get("artifact_type") != "generated_image":
        raise _comic_v2_http_error(
            400,
            department="工部",
            reason="当前产物不是 generated_image，不能执行图片重生成。",
            impact="系统没有可复用的生图上下文，重生成后无法保证资产一致性。",
            next_action="请选择人物、道具或场景的生成图片产物，再提交重生成意见。",
            stage="image_regeneration",
        )
    workspace = config_manager.get_workspace(source.get("workspace_id", ""))
    if not workspace or not _is_comic_office_id(workspace.get("office_id")):
        raise _comic_v2_http_error(
            400,
            department="尚书省",
            reason="这张图片不属于 AI 漫剧办公室项目，不能在这里重生成。",
            impact="跨办公室重生成会破坏项目隔离，也可能把模型配置用错。",
            next_action="回到图片所属办公室处理；如果这是漫剧资产，请重新在漫剧项目里生成。",
            stage="image_regeneration",
        )
    spec = _build_comic_regeneration_spec(source, req.instruction)
    if not spec.get("prompt"):
        raise _comic_v2_http_error(
            400,
            department="工部",
            reason="没有找到原始生图提示词，无法安全重生成。",
            impact="没有资产身份证和原始提示词时，重生成图片很容易跑偏，人物、道具、场景一致性无法保证。",
            next_action="重新生成提示词包和基础资产图，或选择包含原始提示词的图片产物再重试。",
            stage="image_regeneration",
        )
    max_attempts = max(1, min(4, int(os.getenv("COMIC_IMAGE_MAX_ATTEMPTS", "2") or "2")))
    source_task_id = source.get("task_id") or str(uuid.uuid4())[:8]
    output_dir = (
        Path(__file__).parent.parent.parent
        / "output" / "workspaces" / source["workspace_id"] / "generated" / Path(source_task_id).name
    )
    index = int(str(uuid.uuid4().int)[:6])
    artifact, quality_row, errors = await _generate_reviewed_comic_image(
        source_task_id,
        source["workspace_id"],
        index,
        spec,
        output_dir,
        max_attempts,
        office_id=workspace.get("office_id", "comic"),
    )
    if not artifact:
        error_artifact_id = f"art_{str(uuid.uuid4())[:8]}_regenerate_error"
        config_manager.create_artifact(
            artifact_id=error_artifact_id,
            workspace_id=source["workspace_id"],
            task_id=source.get("task_id", ""),
            artifact_type="image_generation_error",
            title=f"{source.get('title', '图片')} 重生成失败",
            content="\n".join(["# 图片重生成失败", ""] + [f"- {error}" for error in errors]),
            metadata={"office_id": workspace.get("office_id", "comic"), "source_artifact_id": artifact_id, "error_count": len(errors)},
            created_by="xingbu",
        )
        return {"status": "failed", "artifact_id": error_artifact_id, "errors": errors}
    artifact["artifact_id"] = f"art_{str(uuid.uuid4())[:8]}_regenerated_image"
    artifact["title"] = f"{source.get('title', spec['title'])}（重生成）"
    artifact["metadata"]["source_artifact_id"] = artifact_id
    artifact["metadata"]["regeneration_instruction"] = req.instruction
    config_manager.create_artifact(
        artifact_id=artifact["artifact_id"],
        workspace_id=source["workspace_id"],
        task_id=source.get("task_id", ""),
        artifact_type=artifact["artifact_type"],
        title=artifact["title"],
        uri=artifact.get("uri", ""),
        content=artifact.get("content", ""),
        metadata=artifact.get("metadata", {}),
        created_by=artifact.get("created_by", ""),
    )
    _mark_artifact_invalidated(
        source,
        reason="superseded_by_regeneration",
        scope=f"image:{(source.get('metadata') or {}).get('source_id', '') or artifact_id}",
        replaced_by_artifact_id=artifact["artifact_id"],
        current_script_hash=artifact["metadata"].get("script_hash", ""),
        current_script_version=artifact["metadata"].get("script_version", 0),
    )
    return {
        "status": "completed",
        "artifact": artifact,
        "quality": quality_row,
        "errors": errors,
    }


@app.get("/api/browser/status")
async def get_browser_status_api():
    """Check whether the local capture browser is running."""
    return browser_status()


@app.post("/api/browser/start-login")
async def start_browser_login_api(req: BrowserStartRequest):
    """Open a visible browser window for the user to log in and persist cookies locally."""
    try:
        result = await open_login_page(req.url or "https://dy3.feigua.cn/")
    except BrowserCaptureError as exc:
        raise _research_http_error(
            400,
            department="兵部",
            reason=f"登录窗口打开失败：{exc}",
            impact="飞瓜登录无法完成，后续自动截图、榜单取证和证据入库都会暂停。",
            next_action="确认本机已安装 Chrome/Edge，关闭残留调试浏览器后重新点击“打开登录窗口”。",
            stage="browser_login",
        ) from exc
    return {
        **result,
        "note": "请在弹出的浏览器里登录平台。登录态会保存在本地浏览器资料目录。",
    }


@app.get("/api/browser/feigua-login-state")
async def get_feigua_login_state_api():
    """Check whether the visible Feigua browser appears logged in."""
    try:
        return await feigua_login_state()
    except BrowserCaptureError as exc:
        raise _research_http_error(
            400,
            department="兵部",
            reason=f"飞瓜登录状态检查失败：{exc}",
            impact="系统无法确认是否已经登录，截图取证不会继续执行。",
            next_action="先点击“打开登录窗口”，在弹出的浏览器里完成登录，再重新检查登录状态。",
            stage="browser_login",
        ) from exc


@app.post("/api/workspaces/{workspace_id}/capture-url")
async def capture_workspace_url_api(workspace_id: str, req: UrlCaptureRequest):
    """Capture a URL with local Chrome and save it as screenshot evidence."""
    if not config_manager.get_workspace(workspace_id):
        raise _missing_workspace_http_error(workspace_id)
    safe_stem = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", (req.title or "browser_capture")).strip("_")
    safe_stem = safe_stem[:60] or "browser_capture"
    evidence_id = str(uuid.uuid4())[:8]
    saved_name = f"{evidence_id}_{safe_stem}.png"
    evidence_dir = Path(__file__).parent.parent.parent / "output" / "workspaces" / workspace_id / "evidence"
    file_path = evidence_dir / saved_name
    try:
        result = await capture_url(
            url=req.url,
            output_path=file_path,
            wait_seconds=req.wait_seconds,
            full_page=req.full_page,
        )
    except BrowserCaptureError as exc:
        raise _research_http_error(
            400,
            department="兵部",
            reason=f"自动截图失败：{exc}",
            impact="页面证据不会被保存，后续证据表、截图识别和报告引用都会缺少该页面。",
            next_action="先点击“打开登录窗口”或确认浏览器调试端口可用；登录完成后重新自动截图。",
            stage="browser_capture",
        ) from exc

    artifact_id = f"art_ev_{evidence_id}"
    uri = f"/api/workspaces/{workspace_id}/files/evidence/{saved_name}"
    title = f"自动截图证据：{req.title or req.url}"
    content = "\n".join([
        f"页面：{req.url}",
        f"文件名：{saved_name}",
        f"大小：{result['size']} bytes",
        f"说明：{req.note or '本地浏览器自动截图，等待视觉模型识别。'}",
        "",
        "状态：已截图入库，可继续执行截图识别。",
    ])
    metadata = {
        "original_filename": saved_name,
        "stored_filename": saved_name,
        "content_type": "image/png",
        "size": result["size"],
        "note": req.note,
        "source_url": req.url,
        "evidence_kind": "browser_screenshot",
        "extraction_status": "pending_visual_model",
        "recommended_agents": ["hubu", "bingbu", "xingbu", "gongbu"],
    }
    config_manager.create_artifact(
        artifact_id=artifact_id,
        workspace_id=workspace_id,
        task_id="",
        artifact_type="screenshot_evidence",
        title=title,
        uri=uri,
        content=content,
        metadata=metadata,
        created_by="browser_capture",
    )
    _sync_workspace_evidence_artifacts(workspace_id)
    return {
        "artifact_id": artifact_id,
        "workspace_id": workspace_id,
        "uri": uri,
        "status": "captured",
        "metadata": metadata,
    }


@app.post("/api/workspaces/{workspace_id}/capture-feigua")
async def capture_workspace_feigua_api(workspace_id: str, req: FeiguaCaptureRequest):
    """Run the Feigua research capture skill for a keyword and save screenshots as evidence."""
    if not config_manager.get_workspace(workspace_id):
        raise _missing_workspace_http_error(workspace_id)
    keyword = (req.keyword or "").strip()
    if not keyword:
        raise _research_http_error(
            400,
            department="兵部",
            reason="缺少研究对象或关键词，无法开始飞瓜取证。",
            impact="兵部无法判断要搜索哪个商品、品牌或达人，飞瓜截图计划不会执行。",
            next_action="在研究对象里填写明确关键词，例如“民用无人机”“吹风机”或目标品牌名。",
            stage="feigua_capture",
        )

    result = await _capture_feigua_evidence(
        workspace_id=workspace_id,
        keyword=keyword,
        wait_seconds=req.wait_seconds,
        limit=req.limit,
    )
    return result


async def _capture_feigua_evidence(
    workspace_id: str,
    keyword: str,
    wait_seconds: int = 6,
    limit: int = 4,
    task_id: str = "",
    require_login: bool = False,
    login_timeout_seconds: int = 300,
) -> dict:
    """Capture Feigua pages into workspace evidence artifacts."""
    login_result: dict = {}
    if require_login:
        try:
            await open_login_page("https://dy3.feigua.cn/")
            login_result = await wait_for_feigua_login(timeout_seconds=login_timeout_seconds)
        except BrowserCaptureError as exc:
            login_result = {"status": "failed", "error": str(exc)}
        if login_result.get("status") != "logged_in":
            return {
                "workspace_id": workspace_id,
                "keyword": keyword,
                "status": "waiting_for_login",
                "created_count": 0,
                "created": [],
                "captures": [],
                "login": login_result,
                "note": "系统已打开飞瓜登录窗口，正在等待你在 Edge 中完成登录。登录完成后会自动继续取证。",
            }

    evidence_dir = Path(__file__).parent.parent.parent / "output" / "workspaces" / workspace_id / "evidence"
    try:
        captures = await capture_feigua_plan(
            keyword=keyword,
            output_dir=evidence_dir,
            wait_seconds=wait_seconds,
            limit=limit,
        )
    except BrowserCaptureError as exc:
        return {
            "workspace_id": workspace_id,
            "keyword": keyword,
            "status": "failed",
            "created_count": 0,
            "created": [],
            "captures": [],
            "error": str(exc),
            "note": "请确认本机已安装 Chrome/Edge，或先点击“打开登录窗口”。",
        }

    created = []
    for capture in captures:
        if capture.get("status") != "captured" or not capture.get("path"):
            continue
        file_path = Path(capture["path"])
        saved_name = file_path.name
        evidence_id = saved_name.split("_", 1)[0]
        artifact_id = f"art_ev_{evidence_id}"
        uri = f"/api/workspaces/{workspace_id}/files/evidence/{saved_name}"
        title = f"飞瓜自动截图：{keyword} - {capture.get('name', '页面')}"
        metadata = {
            "original_filename": saved_name,
            "stored_filename": saved_name,
            "content_type": "image/png",
            "size": capture.get("size", file_path.stat().st_size if file_path.exists() else 0),
            "note": capture.get("note", ""),
            "source_url": capture.get("url", ""),
            "evidence_kind": "feigua_browser_screenshot",
            "extraction_status": "pending_visual_model",
            "recommended_agents": ["hubu", "bingbu", "xingbu", "gongbu"],
        }
        config_manager.create_artifact(
            artifact_id=artifact_id,
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type="screenshot_evidence",
            title=title,
            uri=uri,
            content="\n".join([
                f"研究对象：{keyword}",
                f"页面：{capture.get('url', '')}",
                f"截图用途：{capture.get('note', '')}",
                f"文件名：{saved_name}",
                "",
                "状态：飞瓜自动截图已入库，等待视觉模型识别。",
            ]),
            metadata=metadata,
            created_by="feigua_capture_skill",
        )
        created.append({"artifact_id": artifact_id, "title": title, "uri": uri, "source_url": capture.get("url", "")})
    _sync_workspace_evidence_artifacts(workspace_id)
    return {
        "workspace_id": workspace_id,
        "keyword": keyword,
        "status": "captured" if created else "failed",
        "created_count": len(created),
        "created": created,
        "captures": captures,
        "login": login_result,
        "note": "如果截图停留在登录页，请先点击“打开登录窗口”完成飞瓜登录后重试。",
    }


@app.post("/api/workspaces/{workspace_id}/evidence/sync")
async def sync_workspace_evidence_api(workspace_id: str, req: EvidenceSyncRequest | None = None):
    """Merge screenshot evidence and extraction results into standard research artifacts."""
    if not config_manager.get_workspace(workspace_id):
        raise _missing_workspace_http_error(workspace_id)
    synced = _sync_workspace_evidence_artifacts(workspace_id)
    return {"workspace_id": workspace_id, "status": "synced", "artifact_count": len(synced), "artifacts": synced}


@app.post("/api/workspaces/{workspace_id}/evidence/extract-all")
async def extract_all_workspace_evidence_api(workspace_id: str):
    """Run vision extraction for every pending screenshot in a workspace."""
    if not config_manager.get_workspace(workspace_id):
        raise _missing_workspace_http_error(workspace_id)
    result = await _auto_extract_workspace_screenshots(workspace_id)
    return result


@app.post("/api/artifacts/{artifact_id}/extract")
async def extract_evidence_artifact_api(artifact_id: str, req: EvidenceExtractRequest):
    """Use a vision-capable department model to extract structured data from screenshot evidence."""
    return await _extract_evidence_artifact(
        artifact_id=artifact_id,
        agent_id=req.agent_id,
        instruction=req.instruction,
    )


async def _extract_evidence_artifact(
    artifact_id: str,
    agent_id: str = "hubu",
    instruction: str = "",
) -> dict:
    """Internal screenshot extraction helper used by manual and automatic flows."""
    artifact = config_manager.get_artifact(artifact_id)
    if not artifact:
        raise _research_http_error(
            404,
            department="刑部",
            reason=f"产物 {artifact_id} 不存在，无法执行截图识别。",
            impact="这张截图不会被转成结构化数据，后续报告也无法引用它。",
            next_action="回到截图证据区，重新上传截图或选择一个真实存在的截图证据。",
            stage="evidence_extraction",
        )
    if artifact.get("artifact_type") != "screenshot_evidence":
        raise _research_http_error(
            400,
            department="刑部",
            reason="当前产物不是截图证据，不能执行图片识别。",
            impact="模型无法从普通报告或其他产物里提取页面截图数据。",
            next_action="请选择 artifact_type 为 screenshot_evidence 的产物，或先上传截图证据。",
            stage="evidence_extraction",
        )

    workspace_id = artifact.get("workspace_id") or ""
    metadata = artifact.get("metadata") or {}
    stored_filename = Path(metadata.get("stored_filename") or "").name
    if not workspace_id or not stored_filename:
        raise _research_http_error(
            400,
            department="户部",
            reason="截图证据缺少工作空间或文件名信息。",
            impact="系统找不到原始截图文件，刑部无法进行视觉识别。",
            next_action="重新上传这张截图，让系统重新生成完整的证据记录。",
            stage="evidence_extraction",
        )
    file_path = Path(__file__).parent.parent.parent / "output" / "workspaces" / workspace_id / "evidence" / stored_filename
    if not file_path.exists():
        raise _research_http_error(
            404,
            department="户部",
            reason=f"截图文件 {stored_filename} 不存在或已被移动。",
            impact="截图无法预览和识别，报告中的证据链会缺少这一页。",
            next_action="重新上传截图，或重新执行自动截图后再识别。",
            stage="evidence_extraction",
        )

    agent_id = agent_id if agent_id in {"hubu", "bingbu", "xingbu", "gongbu"} else "hubu"
    model_config = config_manager.get_model_config(agent_id, office_id="research")
    image_base64 = base64.b64encode(file_path.read_bytes()).decode("ascii")
    system_prompt = (
        "你是研究办公室的截图数据识别员。只根据图片内容输出，禁止臆造。"
        "如果看不清或无法确认，请写待核验。"
    )
    user_prompt = "\n".join([
        "请识别这张市场调研截图，提取可用于报告的数据证据。",
        "优先输出 JSON，字段包括：source_hint、page_type、detected_tables、key_numbers、competitors、warnings、recommended_next_steps。",
        "detected_tables 每行尽量包含 name/rank/brand/product/price/sales/GMV/rating/source_text 等字段。",
        "key_numbers 每项包含 metric/value/context/evidence_text/confidence。",
        "competitors 每项包含 brand/product/price/sales/claim/confidence。",
        "所有不确定值必须标为待核验。",
        instruction.strip() if instruction else "",
    ]).strip()

    llm = LLMFactory.create(model_config)
    response = await llm.chat_with_vision(
        text=user_prompt,
        images=[image_base64],
        system=system_prompt,
    )

    status = "completed"
    content = response.content or ""
    if not content or content.startswith("[API"):
        status = "failed"
        content = content or "视觉模型没有返回可用内容。"

    extraction_id = f"art_ext_{str(uuid.uuid4())[:8]}"
    title = f"截图识别结果：{artifact.get('title', '').replace('截图证据：', '')}"
    extraction_metadata = {
        "source_artifact_id": artifact_id,
        "source_uri": artifact.get("uri", ""),
        "source_filename": metadata.get("original_filename", stored_filename),
        "agent_id": agent_id,
        "provider": model_config.provider,
        "model": model_config.model,
        "status": status,
        "tokens_used": response.tokens_used,
        "extraction_kind": "vision_screenshot",
    }
    config_manager.create_artifact(
        artifact_id=extraction_id,
        workspace_id=workspace_id,
        task_id=artifact.get("task_id") or "",
        artifact_type="screenshot_extraction",
        title=title,
        uri=artifact.get("uri", ""),
        content=content,
        metadata=extraction_metadata,
        created_by=agent_id,
    )
    synced = _sync_workspace_evidence_artifacts(workspace_id)
    config_manager.append_task_event(
        task_id=f"evidence_{artifact_id}",
        event_type="evidence_extracted",
        status=status,
        summary=f"Screenshot evidence extracted by {agent_id}",
        payload={
            "workspace_id": workspace_id,
            "source_artifact_id": artifact_id,
            "artifact_id": extraction_id,
            "agent_id": agent_id,
            "model": f"{model_config.provider}/{model_config.model}",
        },
    )
    return {
        "artifact_id": extraction_id,
        "workspace_id": workspace_id,
        "status": status,
        "content": content,
        "metadata": extraction_metadata,
        "synced_artifacts": len(synced),
    }


async def _auto_extract_workspace_screenshots(workspace_id: str, task_id: str = "") -> dict:
    """Run vision extraction for pending screenshot evidence in a workspace."""
    artifacts = config_manager.list_artifacts(workspace_id=workspace_id)
    extracted_sources = {
        (a.get("metadata") or {}).get("source_artifact_id")
        for a in artifacts
        if a.get("artifact_type") == "screenshot_extraction"
    }
    screenshots = [
        a for a in artifacts
        if a.get("artifact_type") == "screenshot_evidence"
        and a.get("artifact_id") not in extracted_sources
    ]
    results = []
    for shot in screenshots:
        try:
            result = await _extract_evidence_artifact(
                artifact_id=shot["artifact_id"],
                agent_id="hubu",
                instruction="这是自动取证流程的一部分。请优先识别榜单、商品、品牌、达人、价格、销量、GMV、热度、排名和页面权限状态。",
            )
            results.append({
                "source_artifact_id": shot["artifact_id"],
                "status": result.get("status"),
                "artifact_id": result.get("artifact_id"),
            })
        except Exception as exc:
            results.append({
                "source_artifact_id": shot.get("artifact_id"),
                "status": "failed",
                "error": str(exc),
            })
    _sync_workspace_evidence_artifacts(workspace_id)
    if task_id:
        config_manager.append_task_event(
            task_id=task_id,
            event_type="evidence_auto_extract_finished",
            status="completed" if any(r.get("status") == "completed" for r in results) else "needs_review",
            summary=f"Auto screenshot extraction finished: {len(results)} screenshots",
            payload={"workspace_id": workspace_id, "results": results},
        )
    return {"workspace_id": workspace_id, "count": len(results), "results": results}


def _sync_workspace_evidence_artifacts(workspace_id: str) -> list[dict]:
    artifacts = config_manager.list_artifacts(workspace_id=workspace_id)
    evidence_artifacts = build_evidence_artifacts(workspace_id, artifacts)
    for artifact in evidence_artifacts:
        config_manager.create_artifact(
            artifact_id=artifact["artifact_id"],
            workspace_id=workspace_id,
            task_id=artifact.get("task_id", ""),
            artifact_type=artifact["artifact_type"],
            title=artifact["title"],
            uri=artifact.get("uri", ""),
            content=artifact.get("content", ""),
            metadata=artifact.get("metadata", {}),
            created_by=artifact.get("created_by", ""),
        )
    return evidence_artifacts


def _comic_image_specs(result: dict, limit: int) -> list[dict]:
    """Build a small, cost-aware image queue from a comic package."""
    package = result.get("comic_package", {}) or {}
    script_binding = package.get("script_binding", {}) or {}
    specs: list[dict] = []
    for item in (package.get("characters") or []):
        specs.append({
            "kind": "character",
            "agent": "gongbu",
            "title": f"{item.get('id', 'character')} 人物设定图",
            "prompt": _clean_base_asset_image_prompt("character", item.get("image_prompt", "")),
            "source_id": item.get("id", ""),
            "binding": item.get("binding", {}),
            "script_binding": script_binding,
        })
        for spec in item.get("asset_specs", []) or []:
            specs.append(_comic_asset_image_spec(item, spec, "gongbu", script_binding, asset_family="character"))
    for item in (package.get("props") or []):
        for spec in item.get("asset_specs", []) or []:
            specs.append(_comic_asset_image_spec(item, spec, "gongbu", script_binding, asset_family="prop"))
    for item in (package.get("scenes") or []):
        specs.append({
            "kind": "scene",
            "agent": "gongbu",
            "title": f"{item.get('id', 'scene')} 场景概念图",
            "prompt": item.get("image_prompt", ""),
            "source_id": item.get("id", ""),
            "binding": item.get("binding", {}),
            "script_binding": script_binding,
        })
        for spec in item.get("asset_specs", []) or []:
            specs.append(_comic_asset_image_spec(item, spec, "gongbu", script_binding))
    return [spec for spec in specs if spec.get("prompt")][:limit]


def _comic_asset_image_spec(
    item: dict,
    asset_spec: dict,
    agent: str,
    script_binding: dict,
    asset_family: str = "",
) -> dict:
    source_id = item.get("id", "")
    kind = asset_spec.get("kind") or "asset"
    return {
        "kind": kind,
        "agent": agent,
        "title": f"{source_id} {asset_spec.get('label') or kind}",
        "prompt": _clean_base_asset_image_prompt(asset_family, asset_spec.get("prompt", "")),
        "source_id": f"{source_id}_{kind}",
        "binding": item.get("binding", {}),
        "script_binding": script_binding,
        "image_ref": asset_spec.get("image_ref", ""),
        "acceptance": asset_spec.get("acceptance", ""),
    }


def _clean_base_asset_image_prompt(asset_family: str, prompt: str) -> str:
    """Final hard gate before image generation for reusable base assets."""
    prompt = (prompt or "").strip()
    if asset_family == "character":
        guard = (
            "基础人物资产设定图，只生成单独角色参考，不生成剧情画面；"
            "纯白或近白色干净背景，工作室柔光，主体完整清晰；"
            "即使原提示词包含山路、街道、房间、战斗或剧情动作，也只保留人物外观、脸型、发型、服装主色、年龄感和标志物；"
            "负面提示词：禁止场景背景、禁止山路、禁止街道、禁止室内剧情现场、禁止其他人物、禁止手持剧情道具、禁止文字、禁止标签、禁止水印、禁止编号。"
        )
        return _append_generation_guard(prompt, guard)
    if asset_family == "prop":
        guard = (
            "基础道具资产设定图，只生成单独道具参考，不生成剧情画面；"
            "纯白或近白色干净背景，工作室柔光，展示形状、材质、颜色、尺寸、磨损状态和多角度结构；"
            "即使原提示词包含人物、手持、山路、街道、房间或剧情现场，也只保留道具本身；"
            "负面提示词：禁止人物手持、禁止人物入镜、禁止剧情现场、禁止场景背景、禁止文字、禁止标签、禁止水印、禁止编号。"
        )
        return _append_generation_guard(prompt, guard)
    return prompt


def _append_generation_guard(prompt: str, guard: str) -> str:
    if not prompt:
        return guard
    if "纯白或近白色干净背景" in prompt and "禁止场景背景" in prompt:
        return prompt
    return f"{prompt}。{guard}"


def _extract_comic_prompt_from_content(content: str) -> str:
    match = re.search(r"## 生图提示词\s*(.+?)(?:\n## |\Z)", content or "", re.DOTALL)
    return match.group(1).strip() if match else ""


def _agent_for_comic_image_kind(kind: str) -> str:
    return "gongbu"


def _comic_required_image_agents(result: dict) -> set[str]:
    return {
        _agent_for_comic_image_kind(spec.get("kind", ""))
        for spec in _comic_image_specs(result, limit=20)
        if spec.get("prompt")
    }


def _comic_model_readiness(office_id: str, result: dict) -> dict:
    labels = {"gongbu": "工部", "bingbu": "兵部"}
    readiness = {}
    for agent in sorted(_comic_required_image_agents(result)):
        cfg = config_manager.get_model_config(agent, office_id=office_id)
        ready = is_image_generation_config(cfg)
        readiness[agent] = {
            "ready": ready,
            "provider": cfg.provider,
            "model": cfg.model,
            "detail": "" if ready else (
                f"{labels.get(agent, agent)}需要生图模型，例如 provider=doubao、model=doubao-seedream-5；"
                f"当前是 provider={cfg.provider or '空'}、model={cfg.model or '空'}。"
            ),
        }
    return readiness


def _comic_production_image_config_issues(office_id: str) -> list[str]:
    if office_id != "comic_production":
        return []
    labels = {"gongbu": "工部", "bingbu": "兵部"}
    issues: list[str] = []
    for agent in ("gongbu", "bingbu"):
        cfg = config_manager.get_model_config(agent, office_id=office_id)
        if not is_image_generation_config(cfg):
            issues.append(
                f"{labels[agent]}需要生图模型：provider=doubao，model=doubao-seedream-5；"
                f"当前是 provider={cfg.provider or '空'}，model={cfg.model or '空'}。"
            )
        elif not (cfg.api_key or "").strip():
            issues.append(f"{labels[agent]}的生图 API Key 为空，请填写豆包/火山方舟 API Key。")
    return issues


def _build_comic_regeneration_spec(artifact: dict, instruction: str = "") -> dict:
    metadata = artifact.get("metadata") or {}
    kind = metadata.get("kind") or "character"
    prompt = _extract_comic_prompt_from_content(artifact.get("content", ""))
    if instruction.strip():
        prompt = "\n".join([
            prompt,
            "",
            f"用户本次修改要求：{instruction.strip()}",
            "保持原资产身份、画风方向、连续性规则和镜头用途，禁止偏离项目设定。",
        ]).strip()
    return {
        "kind": kind,
        "agent": _agent_for_comic_image_kind(kind),
        "title": artifact.get("title") or "重生成图片",
        "prompt": prompt,
        "source_id": metadata.get("source_id") or artifact.get("artifact_id", ""),
        "binding": metadata.get("binding") or {},
        "script_binding": {
            "script_hash": metadata.get("script_hash", ""),
            "script_version": metadata.get("script_version", 0),
            "confirmed": bool(metadata.get("script_confirmed")),
            "source_type": metadata.get("script_source_type", ""),
        },
    }


async def _generate_reviewed_comic_image(
    task_id: str,
    workspace_id: str,
    index: int,
    spec: dict,
    output_dir: Path,
    max_attempts: int,
    office_id: str = "comic_production",
) -> tuple[dict | None, dict | None, list[str]]:
    errors: list[str] = []
    office_id = _normalize_comic_office_id(office_id)
    cfg = config_manager.get_model_config(spec["agent"], office_id=office_id)
    if not is_image_generation_config(cfg):
        agent_label = {"gongbu": "工部", "bingbu": "兵部"}.get(spec["agent"], spec["agent"])
        return None, None, [
            f"{agent_label}需要生图模型才能生成“{spec['title']}”。"
            f"当前配置是 provider={cfg.provider or '空'}、model={cfg.model or '空'}；"
            "请在当前办公室的模型配置里改为 provider=doubao、model=doubao-seedream-5，并填写豆包/火山方舟 API Key。"
        ]
    prompt = spec["prompt"]
    image = None
    review = None
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        try:
            image = await asyncio.to_thread(
                generate_doubao_image,
                cfg,
                prompt,
                output_dir,
                f"{index:02d}_{spec['kind']}_{spec['source_id']}",
            )
        except ImageGenerationError as exc:
            if attempt >= max_attempts:
                errors.append(f"{spec['title']} 第{attempt}次生成失败: {exc}")
                break
            await asyncio.sleep(min(2 * attempt, 6))
            continue
        review_cfg = config_manager.get_model_config("xingbu", office_id=office_id)
        try:
            review = await review_comic_image(review_cfg, image.path, {**spec, "prompt": prompt})
        except Exception as exc:
            errors.append(f"{spec['title']} 视觉质检失败: {exc}")
            review = None
            break
        if not should_retry_image(review) or attempt >= max_attempts:
            break
        prompt = build_revised_prompt(prompt, review, attempt=attempt + 1)
    if image is None:
        return None, None, errors
    review_status = review.status if review else "needs_review"
    review_score = review.score if review else 0
    review_issues = review.issues if review else ["未完成自动视觉检查"]
    review_fix = review.revision_prompt if review else ""
    filename = Path(image.path).name
    artifact = {
        "artifact_id": f"art_{task_id}_generated_image_{index}",
        "task_id": task_id,
        "artifact_type": "generated_image",
        "title": spec["title"],
        "uri": f"/api/workspaces/{workspace_id}/files/generated/{Path(task_id).name}/{filename}",
        "content": "\n".join([
            f"# {spec['title']}",
            "",
            f"- 来源：{spec['kind']} / {spec['source_id']}",
            f"- Provider：{image.provider}",
            f"- Model：{image.model}",
            f"- Size：{image.size}",
            f"- 质检结果：{review_status}",
            f"- 质检分数：{review_score}",
            f"- 生成次数：{attempt}",
            "",
            "## 生图提示词",
            image.prompt,
            "",
            "## 刑部视觉检查",
            "；".join(review_issues) if review_issues else "未发现明显问题。",
            "",
            "## 修正提示词",
            review_fix or "无需修正。",
        ]),
        "metadata": {
            "office_id": office_id,
            "kind": spec["kind"],
            "source_id": spec["source_id"],
            "binding": spec.get("binding", {}),
            "script_hash": (spec.get("script_binding") or {}).get("script_hash", ""),
            "script_version": (spec.get("script_binding") or {}).get("script_version", 0),
            "script_confirmed": bool((spec.get("script_binding") or {}).get("confirmed")),
            "script_source_type": (spec.get("script_binding") or {}).get("source_type", ""),
            "path": image.path,
            "provider": image.provider,
            "model": image.model,
            "source_url": image.source_url,
            "attempts": attempt,
            "quality_review": {
                "status": review_status,
                "score": review_score,
                "issues": review_issues,
                "revision_prompt": review_fix,
            },
        },
        "created_by": spec["agent"],
    }
    quality_row = {
        "title": spec["title"],
        "source_id": spec["source_id"],
        "status": review_status,
        "score": review_score,
        "attempts": attempt,
        "issues": review_issues,
        "revision_prompt": review_fix,
    }
    return artifact, quality_row, errors


async def _generate_comic_images(task_id: str, workspace_id: str, result: dict, office_id: str = "comic_production") -> list[dict]:
    """Generate preview images for the comic office and return artifact dicts."""
    office_id = _normalize_comic_office_id(office_id)
    default_limit = "40" if office_id == "comic_production" else "12"
    hard_limit = 60 if office_id == "comic_production" else 20
    limit = max(0, min(hard_limit, int(os.getenv("COMIC_IMAGE_LIMIT", default_limit) or default_limit)))
    max_attempts = max(1, min(4, int(os.getenv("COMIC_IMAGE_MAX_ATTEMPTS", "2") or "2")))
    if limit <= 0:
        return []
    output_dir = (
        Path(__file__).parent.parent.parent
        / "output" / "workspaces" / workspace_id / "generated" / Path(task_id).name
    )
    artifacts: list[dict] = []
    quality_rows: list[dict] = []
    errors: list[str] = []
    specs = list(_comic_image_specs(result, limit))
    total = len(specs)
    completed = 0
    failed = 0
    for index, spec in enumerate(specs, start=1):
        config_manager.append_task_event(
            task_id=task_id,
            event_type="comic_image_item_started",
            status="running",
            summary=f"正在生成第 {index}/{total} 张：{spec.get('title', spec.get('source_id', '图片'))}",
            payload={
                "workspace_id": workspace_id,
                "index": index,
                "total": total,
                "source_id": spec.get("source_id", ""),
                "kind": spec.get("kind", ""),
                "completed": completed,
                "failed": failed,
            },
        )
        artifact, quality_row, image_errors = await _generate_reviewed_comic_image(
            task_id, workspace_id, index, spec, output_dir, max_attempts, office_id=office_id
        )
        errors.extend(image_errors)
        if artifact:
            artifacts.append(artifact)
            completed += 1
            config_manager.append_task_event(
                task_id=task_id,
                event_type="comic_image_item_completed",
                status="completed",
                summary=f"第 {index}/{total} 张已完成：{spec.get('title', spec.get('source_id', '图片'))}",
                payload={
                    "workspace_id": workspace_id,
                    "index": index,
                    "total": total,
                    "source_id": spec.get("source_id", ""),
                    "kind": spec.get("kind", ""),
                    "completed": completed,
                    "failed": failed,
                },
            )
        else:
            failed += 1
            config_manager.append_task_event(
                task_id=task_id,
                event_type="comic_image_item_failed",
                status="failed",
                summary=f"第 {index}/{total} 张生成失败：{spec.get('title', spec.get('source_id', '图片'))}",
                payload={
                    "workspace_id": workspace_id,
                    "index": index,
                    "total": total,
                    "source_id": spec.get("source_id", ""),
                    "kind": spec.get("kind", ""),
                    "completed": completed,
                    "failed": failed,
                    "errors": image_errors,
                },
            )
        if quality_row:
            quality_rows.append(quality_row)
    if quality_rows:
        artifacts.append({
            "artifact_id": f"art_{task_id}_image_quality_report",
            "task_id": task_id,
            "artifact_type": "image_quality_report",
            "title": "图片一致性质检报告",
            "uri": "",
            "content": _format_comic_quality_report(quality_rows),
            "metadata": {"office_id": office_id, "review_count": len(quality_rows)},
            "created_by": "xingbu",
        })
    if errors:
        artifacts.append({
            "artifact_id": f"art_{task_id}_image_generation_errors",
            "task_id": task_id,
            "artifact_type": "image_generation_error",
            "title": "图片生成错误记录",
            "uri": "",
            "content": "\n".join(["# 图片生成错误记录", ""] + [f"- {error}" for error in errors]),
            "metadata": {"office_id": office_id, "error_count": len(errors)},
            "created_by": "xingbu",
        })
    result.setdefault("comic_package", {})["image_quality_summary"] = {
        "expected": total,
        "generated": completed,
        "failed": failed,
        "reviews": quality_rows,
    }
    return artifacts


def _build_comic_word_canvas_artifact(
    task_id: str,
    workspace_id: str,
    result: dict,
    image_artifacts: list[dict],
    office_id: str = "comic_production",
) -> dict | None:
    """Generate the docx canvas and return a replacement word_canvas artifact."""
    office_id = _normalize_comic_office_id(office_id)
    package = result.get("comic_package", {}) or {}
    output_dir = Path(__file__).parent.parent.parent / "output" / "workspaces" / workspace_id / "delivery"
    try:
        docx_path = build_comic_word_canvas(package, image_artifacts, output_dir)
    except Exception as exc:
        return {
            "artifact_id": f"art_{task_id}_word_canvas",
            "task_id": task_id,
            "artifact_type": "word_canvas",
            "title": f"{package.get('title', 'AI漫剧')} - Word画布生成失败",
            "uri": "",
            "content": f"# Word画布生成失败\n\n{exc}",
            "metadata": {"office_id": office_id, "error": str(exc)},
            "created_by": "gongbu",
        }
    filename = docx_path.name
    return {
        "artifact_id": f"art_{task_id}_word_canvas",
        "task_id": task_id,
        "artifact_type": "word_canvas",
        "title": f"{package.get('title', 'AI漫剧')} - Word制片画布",
        "uri": f"/api/workspaces/{workspace_id}/files/delivery/{filename}",
        "content": "\n".join([
            "# Word制片画布",
            "",
            "已生成 .docx 交付文档。",
            f"下载链接：/api/workspaces/{workspace_id}/files/delivery/{filename}",
            "",
            "文档内容按镜头组织，展示画面内容、人物、场景、道具、镜头画面提示词、视频生成提示词和负面提示词。",
            "",
            "新增平台执行表：逐镜列出参考资产、视频时长、平台提示词、镜头运动、动作重点和失败重试建议，方便交给 Libtv 或其他视频生成平台继续制作。",
        ]),
        "metadata": {"office_id": office_id, "path": str(docx_path)},
        "created_by": "gongbu",
    }


def _format_comic_quality_report(rows: list[dict]) -> str:
    lines = [
        "# 图片一致性质检报告",
        "",
        "| 资产 | 状态 | 分数 | 生成次数 | 问题 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if row.get("issues"):
            issues = "；".join(row.get("issues") or [])
        elif row.get("status") == "pass":
            issues = "自动视觉检查通过"
        else:
            issues = "尚未完成有效视觉检查，需要人工复核"
        lines.append(
            f"| {row.get('title', '')} | {row.get('status', '')} | {row.get('score', 0)} | "
            f"{row.get('attempts', 1)} | {issues} |"
        )
    return "\n".join(lines)


@app.post("/api/tasks/{task_id}/recover-artifacts")
async def recover_task_artifacts_api(task_id: str):
    """Recover research artifacts from a task result or generated markdown file."""
    record = config_manager.get_task_run(task_id) or config_manager.get_task_result(task_id)
    if not record:
        raise _research_http_error(
            404,
            department="尚书省",
            reason=f"任务 {task_id} 不存在，无法恢复产物。",
            impact="系统找不到这次调研的执行记录，也无法从记录里重建报告、数据表或来源清单。",
            next_action="从历史记录选择真实存在的任务；如果任务是旧进程中断的，请重新提交调研工单。",
            stage="artifact_recovery",
        )

    workspace_id = ""
    for event in reversed(record.get("events", [])):
        payload = event.get("payload") or {}
        if payload.get("workspace_id"):
            workspace_id = payload["workspace_id"]
            break
    if not workspace_id:
        raise _research_http_error(
            400,
            department="尚书省",
            reason="没有找到这个任务所属的工作空间。",
            impact="恢复出的产物没有项目可归档，前端也无法在对应办公室展示。",
            next_action="重新提交一次调研任务，或先确认历史任务记录里是否包含 workspace_id。",
            stage="artifact_recovery",
        )

    result = record.get("result") or {}
    final_report = result.get("final_report", "")
    report_path = None
    if _is_unusable_report(final_report):
        output_dir = Path(__file__).parent.parent.parent / "output" / task_id
        candidates = sorted(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if output_dir.exists() else []
        if candidates:
            report_path = candidates[0]
            final_report = report_path.read_text(encoding="utf-8")
    if not final_report:
        raise _research_http_error(
            404,
            department="礼部",
            reason="没有找到可恢复的报告正文。",
            impact="无法重建报告、图表建议、截图计划和老板简报等交付物。",
            next_action="检查任务是否真正完成；如果任务中断或模型没有产出正文，请重新运行调研任务。",
            stage="artifact_recovery",
        )

    title = result.get("plan", {}).get("title") if isinstance(result.get("plan"), dict) else ""
    title = title or _extract_markdown_title(final_report) or f"Recovered report {task_id}"
    recovered_result = {
        **result,
        "status": "completed",
        "task_id": task_id,
        "plan": {**(result.get("plan") if isinstance(result.get("plan"), dict) else {}), "title": title},
        "final_report": final_report,
    }
    if report_path:
        recovered_result["recovered_from_file"] = str(report_path)

    artifacts = build_research_artifacts(task_id, recovered_result)
    quality = assess_research_package(artifacts)
    artifacts.append({
        "artifact_id": f"art_{task_id}_quality_1",
        "task_id": task_id,
        "artifact_type": "quality_report",
        "title": "研究材料包验收",
        "content": _format_quality_report(quality),
        "metadata": quality,
        "created_by": "xingbu",
    })
    config_manager.delete_artifacts_for_task(task_id)
    for artifact in artifacts:
        config_manager.create_artifact(
            artifact_id=artifact["artifact_id"],
            workspace_id=workspace_id,
            task_id=task_id,
            artifact_type=artifact["artifact_type"],
            title=artifact["title"],
            content=artifact.get("content", ""),
            metadata=artifact.get("metadata", {}),
            created_by=artifact.get("created_by", ""),
        )
    config_manager.save_task_record(task_id, record.get("user_request", ""), record.get("template_id", ""), "completed", recovered_result)
    config_manager.update_task_run(task_id, "completed", current_phase="completed", result=recovered_result, completed=True)
    config_manager.append_task_event(
        task_id=task_id,
        event_type="artifacts_recovered",
        status="completed",
        summary="Recovered research artifacts from existing output",
        payload={"workspace_id": workspace_id, "artifact_count": len(artifacts), "quality": quality},
    )
    return {
        "task_id": task_id,
        "workspace_id": workspace_id,
        "status": "completed",
        "artifact_count": len(artifacts),
        "quality": quality,
    }


# ============================================================
# 任务 API
# ============================================================

@app.post("/api/tasks")
async def create_task(req: TaskRequest):
    """创建并执行任务 (异步后台)"""
    task_id = str(uuid.uuid4())[:8]
    office = get_office(req.office_id or "research")
    workspace = config_manager.get_workspace(req.workspace_id) if req.workspace_id else {}
    if _is_comic_office_id(office.id) and workspace and _is_comic_office_id(workspace.get("office_id")):
        office = get_office(workspace.get("office_id"))
    if _is_comic_office_id(office.id):
        if not req.workspace_id:
            raise _comic_v2_http_error(
                400,
                department="内阁",
                reason="还没有选择已确认故事的漫剧项目。",
                impact="尚书省无法接收生产任务，后续资产拆解、图片生成和 Word 画布都不会启动。",
                next_action="先在 AI 漫剧制片室选择项目，完成故事确认后再点击开始生产。",
                stage="production_start",
            )
        if not workspace or workspace.get("office_id") != office.id:
            raise _comic_v2_http_error(
                404,
                department="尚书省",
                reason=f"漫剧工作空间 {req.workspace_id} 不存在，或不属于当前办公室。",
                impact="生产任务无法归档到正确项目，可能导致串项目或历史记录丢失。",
                next_action="回到 AI 漫剧制片室重新选择项目；如果项目不存在，请重新创建并确认故事。",
                stage="production_start",
            )
        confirmed_artifact = _latest_workspace_artifact_by_type(req.workspace_id, "confirmed_script")
        if not confirmed_artifact:
            raise _comic_v2_http_error(
                400,
                department="内阁",
                reason="当前项目还没有确认故事。",
                impact="中书省和门下省没有稳定的故事依据，无法继续拆解人物、道具、场景和提示词。",
                next_action="先完成主创对话，确认故事后再生成资产拆解和制片包。",
                stage="production_start",
            )
        req.user_request = _request_with_server_confirmed_script(req.user_request, confirmed_artifact)
        image_config_issues = (
            _comic_production_image_config_issues(office.id)
            if office.id != "comic_production" or _asset_review_approved(req.workspace_id)
            else []
        )
        if image_config_issues:
            raise _comic_v2_http_error(
                400,
                department="工部 / 兵部 / 刑部",
                reason="图片生产或质检所需模型配置不完整：" + "；".join(image_config_issues),
                impact="即使启动任务，也会在生成图片或视觉质检阶段失败。",
                next_action="到模型页面测试并补齐工部生图模型、兵部/刑部视觉模型的 API Key 和模型名称。",
                stage="production_start",
            )
    workspace_id = req.workspace_id or f"ws_{task_id}"
    if not config_manager.get_workspace(workspace_id):
        config_manager.create_workspace(
            workspace_id=workspace_id,
            office_id=office.id,
            title=req.user_request[:80] or "Untitled workspace",
            brief=req.user_request,
        )
    config_manager.create_task_run(task_id, req.user_request, req.template_id or "")
    config_manager.append_task_event(
        task_id=task_id,
        event_type="task_created",
        status="queued",
        summary="Task accepted by Web API",
        payload={
            "template_id": req.template_id or "",
            "office_id": office.id,
            "workspace_id": workspace_id,
        },
    )

    # 后台运行任务, 带错误回调
    bg_task = _schedule_background_task(_run_task(
        task_id,
        req.user_request,
        req.template_id,
        office_id=office.id,
        workspace_id=workspace_id,
    ))
    bg_task.add_done_callback(_on_task_done)

    return {
        "task_id": task_id,
        "workspace_id": workspace_id,
        "office_id": office.id,
        "status": "started",
    }


def _schedule_background_task(coro):
    return asyncio.create_task(coro)


def _on_task_done(t: asyncio.Task):
    """捕获后台任务的未处理异常"""
    if t.cancelled():
        return
    exc = t.exception()
    if exc:
        import traceback
        err_msg = f"[Background Task] UNCAUGHT: {exc}\n{traceback.format_tb(exc.__traceback__)}"
        print(err_msg)
        with open("web_errors.log", "a", encoding="utf-8") as f:
            f.write(f"{'='*60}\n{err_msg}\n")


async def _run_task(
    task_id: str,
    user_request: str,
    template_id: str = None,
    office_id: str = "research",
    workspace_id: str = "",
):
    """后台执行三省六部流程 + 实时推送进度"""
    try:
        office = get_office(office_id)
        config_manager.update_task_run(task_id, "running", current_phase="preparing")
        config_manager.append_task_event(
            task_id=task_id,
            event_type="task_started",
            status="running",
            summary="Background task started",
            payload={"office_id": office.id, "workspace_id": workspace_id},
        )

        # 如果有模板, 使用模板的 prompt
        if template_id:
            template = config_manager.get_template(template_id)
            prompt_template = template.get("default_prompt", "{user_input}")
            user_request = prompt_template.replace("{user_input}", user_request)
            config_manager.append_task_event(
                task_id=task_id,
                event_type="template_applied",
                status="running",
                summary=f"Template applied: {template_id}",
                payload={"template_id": template_id},
            )
        elif office.default_template and not _is_comic_office_id(office.id):
            user_request = office.default_template.replace("{user_input}", user_request)
            config_manager.append_task_event(
                task_id=task_id,
                event_type="office_template_applied",
                status="running",
                summary=f"Office template applied: {office.id}",
                payload={"office_id": office.id},
            )

        if _is_comic_office_id(office.id):
            config_manager.update_task_run(task_id, "running", current_phase="comic_preproduction")
            config_manager.append_task_event(
                task_id=task_id,
                event_type="comic_preproduction_started",
                status="running",
                summary="AI comic pre-production package generation started",
                payload={"office_id": office.id, "workspace_id": workspace_id},
            )
            result = build_comic_result(task_id=task_id, user_request=user_request)
            if office.id == "comic_production":
                config_manager.update_task_run(task_id, "running", current_phase="comic_prompt_preflight")
                config_manager.append_task_event(
                    task_id=task_id,
                    event_type="comic_prompt_preflight_started",
                    status="running",
                    summary="Prompt writing and Xingbu preflight review started before human asset review",
                    payload={"office_id": office.id, "workspace_id": workspace_id},
                )
                result = await enhance_comic_prompts_llm(result, _comic_prompt_model_configs(office.id))
                prompt_generation = (result.get("comic_package", {}) or {}).get("prompt_generation", {})
                config_manager.append_task_event(
                    task_id=task_id,
                    event_type="comic_prompt_preflight_completed",
                    status="running",
                    summary="Prompt writing and preflight review completed",
                    payload={
                        "office_id": office.id,
                        "workspace_id": workspace_id,
                        "mode": prompt_generation.get("mode", ""),
                        "quality_review": prompt_generation.get("quality_review", {}),
                    },
                )
            final_status = result.get("status", "completed")
            artifacts = build_comic_artifacts(task_id, result)
            if office.id == "comic_production":
                asset_review_already_approved = _asset_review_approved(workspace_id)
                artifacts.extend(build_production_handoff_artifacts(task_id, result))
                model_readiness = _comic_model_readiness(office.id, result)
                asset_review_status = "approved" if asset_review_already_approved else "pending"
                chain_state = build_production_chain_state(
                    result.get("comic_package", {}) or {},
                    model_readiness=model_readiness,
                    asset_review_status=asset_review_status,
                )
                artifacts.append({
                    "artifact_id": f"art_{task_id}_production_chain_state",
                    "task_id": task_id,
                    "artifact_type": "production_chain_state",
                    "title": "多 Agent 制片链状态",
                    "uri": "",
                    "content": format_production_chain_state(chain_state),
                    "metadata": {
                        "office_id": office.id,
                        "overall_status": chain_state.get("overall_status", ""),
                        "asset_review_status": chain_state.get("asset_review_status", ""),
                        "current_department": chain_state.get("current_department", ""),
                        "next_action": chain_state.get("next_action", ""),
                        "human_action_required": chain_state.get("human_action_required", False),
                        "stage_summary": chain_state.get("stage_summary", ""),
                        "departments": chain_state.get("departments", []),
                        "quality_gate": chain_state.get("quality_gate", {}),
                        "model_readiness": model_readiness,
                    },
                    "created_by": "shangshu",
                })
                for artifact in artifacts:
                    if artifact.get("artifact_type") == "asset_review_package" and asset_review_already_approved:
                        artifact["metadata"] = {
                            **(artifact.get("metadata") or {}),
                            "requires_human_review": True,
                            "review_status": "approved",
                        }
                if not asset_review_already_approved:
                    for artifact in artifacts:
                        metadata = dict(artifact.get("metadata") or {})
                        metadata["office_id"] = office.id
                        config_manager.create_artifact(
                            artifact_id=artifact["artifact_id"],
                            workspace_id=workspace_id,
                            task_id=task_id,
                            artifact_type=artifact["artifact_type"],
                            title=artifact["title"],
                            uri=artifact.get("uri", ""),
                            content=artifact.get("content", ""),
                            metadata=metadata,
                            created_by=artifact.get("created_by", ""),
                        )
                    result.setdefault("comic_package", {})["generated_image_count"] = 0
                    result.setdefault("comic_package", {})["asset_review_required"] = True
                    config_manager.save_task_record(task_id, user_request, template_id or "", "needs_review", result)
                    config_manager.update_task_run(
                        task_id,
                        "needs_review",
                        current_phase="asset_review_pending",
                        result=result,
                        completed=True,
                    )
                    config_manager.append_task_event(
                        task_id=task_id,
                        event_type="comic_asset_review_required",
                        status="needs_review",
                        summary="Asset split package is ready for human review before image generation",
                        payload={"workspace_id": workspace_id},
                    )
                    await _broadcast_task(task_id, {
                        "type": "completed",
                        "task_id": task_id,
                        "result": {
                            "status": "needs_review",
                            "plan_title": result.get("plan", {}).get("title", ""),
                            "final_report": "资产拆解审核包已生成。请先审核人物、道具、场景和分镜输入，通过后再继续生成图片和 Word 画布。",
                        },
                    })
                    return
            config_manager.update_task_run(task_id, "running", current_phase="comic_image_generation")
            config_manager.append_task_event(
                task_id=task_id,
                event_type="comic_image_generation_started",
                status="running",
                summary="AI comic preview image generation started",
                payload={"workspace_id": workspace_id},
            )
            image_artifacts = await _generate_comic_images(task_id, workspace_id, result, office_id=office.id)
            artifacts.extend(image_artifacts)
            if office.id == "comic_production":
                chain_state = build_production_chain_state(
                    result.get("comic_package", {}) or {},
                    model_readiness=model_readiness,
                    asset_review_status="approved",
                )
                for artifact in artifacts:
                    if artifact.get("artifact_type") != "production_chain_state":
                        continue
                    artifact["content"] = format_production_chain_state(chain_state)
                    artifact["metadata"] = {
                        **(artifact.get("metadata") or {}),
                        "overall_status": chain_state.get("overall_status", ""),
                        "asset_review_status": chain_state.get("asset_review_status", ""),
                        "current_department": chain_state.get("current_department", ""),
                        "next_action": chain_state.get("next_action", ""),
                        "human_action_required": chain_state.get("human_action_required", False),
                        "stage_summary": chain_state.get("stage_summary", ""),
                        "departments": chain_state.get("departments", []),
                        "quality_gate": chain_state.get("quality_gate", {}),
                    }
                result.setdefault("comic_package", {})["production_chain_state"] = chain_state
                if chain_state.get("quality_gate", {}).get("status") != "passed":
                    final_status = "needs_review"
                    result["status"] = "needs_review"
            word_artifact = _build_comic_word_canvas_artifact(task_id, workspace_id, result, image_artifacts, office_id=office.id)
            if word_artifact:
                artifacts = [
                    word_artifact if artifact.get("artifact_type") == "word_canvas" else artifact
                    for artifact in artifacts
                ]
            result.setdefault("comic_package", {})["generated_image_count"] = len([
                artifact for artifact in image_artifacts
                if artifact.get("artifact_type") == "generated_image"
            ])
            for artifact in artifacts:
                metadata = dict(artifact.get("metadata") or {})
                metadata["office_id"] = office.id
                config_manager.create_artifact(
                    artifact_id=artifact["artifact_id"],
                    workspace_id=workspace_id,
                    task_id=task_id,
                    artifact_type=artifact["artifact_type"],
                    title=artifact["title"],
                    uri=artifact.get("uri", ""),
                    content=artifact.get("content", ""),
                    metadata=metadata,
                    created_by=artifact.get("created_by", ""),
                )
            config_manager.save_task_record(task_id, user_request, template_id or "", final_status, result)
            config_manager.update_task_run(
                task_id,
                final_status,
                current_phase="visual_review_pending" if final_status == "needs_review" else "completed",
                result=result,
                completed=True,
            )
            config_manager.append_task_event(
                task_id=task_id,
                event_type="comic_artifacts_created",
                status=final_status,
                summary=(
                    "漫剧制片包已生成，部分图片等待视觉审核"
                    if final_status == "needs_review"
                    else "漫剧制片包已生成并通过质量闸门"
                ),
                payload={
                    "workspace_id": workspace_id,
                    "artifact_count": len(artifacts),
                    "generated_image_count": result.get("comic_package", {}).get("generated_image_count", 0),
                },
            )
            await _broadcast_task(task_id, {
                "type": "completed",
                "task_id": task_id,
                "result": {
                    "status": final_status,
                    "plan_title": result.get("plan", {}).get("title", ""),
                    "final_report": result.get("final_report", ""),
                },
            })
            return

        if workspace_id and needs_platform_evidence(user_request, office.id):
            keyword = research_capture_keyword(user_request)
            config_manager.update_task_run(task_id, "running", current_phase="feigua_evidence_capture")
            config_manager.append_task_event(
                task_id=task_id,
                event_type="feigua_capture_started",
                status="running",
                summary=f"Opening Feigua login and waiting for user login: {keyword}",
                payload={"workspace_id": workspace_id, "keyword": keyword},
            )
            capture_result = await _capture_feigua_evidence(
                workspace_id=workspace_id,
                keyword=keyword,
                wait_seconds=8,
                limit=4,
                task_id=task_id,
                require_login=True,
                login_timeout_seconds=300,
            )
            capture_status = capture_result.get("status", "unknown")
            config_manager.append_task_event(
                task_id=task_id,
                event_type="feigua_capture_finished",
                status=capture_status,
                summary=f"Feigua evidence capture finished: {capture_status}",
                payload={
                    "workspace_id": workspace_id,
                    "keyword": keyword,
                    "created_count": capture_result.get("created_count", 0),
                    "error": capture_result.get("error", ""),
                    "login": capture_result.get("login", {}),
                    "note": capture_result.get("note", ""),
                },
            )
            if capture_result.get("created_count", 0):
                config_manager.update_task_run(task_id, "running", current_phase="evidence_extraction")
                config_manager.append_task_event(
                    task_id=task_id,
                    event_type="evidence_auto_extract_started",
                    status="running",
                    summary="Auto extracting Feigua screenshot evidence",
                    payload={"workspace_id": workspace_id, "created_count": capture_result.get("created_count", 0)},
                )
                extraction_result = await _auto_extract_workspace_screenshots(workspace_id, task_id=task_id)
                evidence_context = format_workspace_evidence_context(
                    config_manager.list_artifacts(workspace_id=workspace_id)
                )
                evidence_lines = [
                    "",
                    "【飞瓜截图证据已入库】",
                    f"研究对象：{keyword}",
                    f"截图数量：{capture_result.get('created_count', 0)}",
                    f"截图识别任务数：{extraction_result.get('count', 0)}",
                    "报告必须引用这些截图证据和识别结果；如果截图停留在登录页、入口页、说明页或数据不可见，必须标记为待核验，禁止写成已获得真实榜单数据。",
                    evidence_context,
                ]
                user_request += "\n" + "\n".join(evidence_lines)
            else:
                user_request += (
                    "\n\n【飞瓜取证未完成】系统已打开飞瓜登录窗口，但尚未形成可用截图。"
                    "报告中必须把飞瓜/抖音平台数据标为待登录或待核验，禁止编造榜单、销量、GMV。"
                )

        config_manager.update_task_run(task_id, "running", current_phase="agent_workflow")
        config_manager.append_task_event(
            task_id=task_id,
            event_type="agent_workflow_started",
            status="running",
            summary="Agent workflow started",
            payload={"office_id": office.id, "workspace_id": workspace_id},
        )
        engine = _get_engine(office_id=office.id)
        try:
            result = await asyncio.wait_for(
                engine.run(user_request, task_id=task_id),
                timeout=AGENT_WORKFLOW_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            config_manager.append_task_event(
                task_id=task_id,
                event_type="agent_workflow_timeout",
                status="fallback",
                summary=(
                    "Agent workflow timed out; generated an evidence-based "
                    "research handoff instead."
                ),
                payload={
                    "office_id": office.id,
                    "workspace_id": workspace_id,
                    "timeout_seconds": AGENT_WORKFLOW_TIMEOUT_SECONDS,
                },
            )
            result = build_evidence_fallback_result(
                task_id=task_id,
                workspace_id=workspace_id,
                user_request=user_request,
                artifacts=config_manager.list_artifacts(workspace_id=workspace_id),
                reason="agent_workflow_timeout",
            )
        result = _recover_unusable_final_report(task_id, result)
        final_status = result.get("status", "unknown")
        if _is_unusable_report(result.get("final_report", "")):
            final_status = "failed"
            result["status"] = "failed"
            result["error"] = result.get("error") or "最终报告生成失败或模型返回 API 错误。"
        config_manager.append_task_event(
            task_id=task_id,
            event_type="agent_workflow_finished",
            status=final_status,
            summary=f"Agent workflow finished with status: {final_status}",
            payload={"office_id": office.id, "workspace_id": workspace_id},
        )

        # 推送完成事件
        await _broadcast_task(task_id, {
            "type": "completed",
            "task_id": task_id,
            "result": {
                "status": final_status,
                "plan_title": result.get("plan", {}).get("title", ""),
                "final_report": result.get("final_report", ""),
            },
        })

        # 保存到历史
        config_manager.save_task_record(task_id, user_request, template_id or "", final_status, result)
        config_manager.update_task_run(
            task_id,
            final_status,
            current_phase="completed" if final_status == "completed" else "finished",
            result=result,
            completed=True,
        )
        config_manager.append_task_event(
            task_id=task_id,
            event_type="task_finished",
            status=final_status,
            summary=f"Task finished with status: {final_status}",
        )
        if workspace_id:
            if office.id == "research":
                config_manager.update_task_run(task_id, final_status, current_phase="artifact_packaging")
                config_manager.append_task_event(
                    task_id=task_id,
                    event_type="artifact_packaging_started",
                    status=final_status,
                    summary="Research artifact packaging started",
                    payload={"workspace_id": workspace_id},
                )
                artifacts = build_research_artifacts(task_id, result)
                existing_workspace_artifacts = config_manager.list_artifacts(workspace_id=workspace_id)
                quality = assess_research_package(existing_workspace_artifacts + artifacts)
                artifacts.append({
                    "artifact_id": f"art_{task_id}_quality_1",
                    "task_id": task_id,
                    "artifact_type": "quality_report",
                    "title": "研究材料包验收",
                    "content": _format_quality_report(quality),
                    "metadata": quality,
                    "created_by": "xingbu",
                })
                for artifact in artifacts:
                    config_manager.create_artifact(
                        artifact_id=artifact["artifact_id"],
                        workspace_id=workspace_id,
                        task_id=task_id,
                        artifact_type=artifact["artifact_type"],
                        title=artifact["title"],
                        content=artifact.get("content", ""),
                        metadata=artifact.get("metadata", {}),
                        created_by=artifact.get("created_by", ""),
                    )
            else:
                final_report = result.get("final_report", "")
                if final_report:
                    config_manager.create_artifact(
                        artifact_id=f"art_{task_id}_report",
                        workspace_id=workspace_id,
                        task_id=task_id,
                        artifact_type="report",
                        title=result.get("plan", {}).get("title", "Final report"),
                        content=final_report,
                        metadata={"status": final_status},
                        created_by="gongbu",
                    )

            if office.id == "research":
                config_manager.append_task_event(
                    task_id=task_id,
                    event_type="artifacts_created",
                    status=final_status,
                    summary="Research office artifacts created",
                    payload={"workspace_id": workspace_id, "quality": quality},
                )
                config_manager.update_task_run(task_id, final_status, current_phase="completed", completed=True)

    except Exception as e:
        import traceback
        err_msg = f"[Task {task_id}] ERROR: {e}\n{traceback.format_exc()}"
        print(err_msg)
        with open("web_errors.log", "a", encoding="utf-8") as f:
            f.write(f"{'='*60}\n{err_msg}\n")
        await _broadcast_task(task_id, {
            "type": "error",
            "task_id": task_id,
            "error": str(e),
        })
        config_manager.update_task_run(
            task_id,
            "failed",
            current_phase="error",
            error=str(e),
            result={"status": "failed", "error": str(e)},
            completed=True,
        )
        config_manager.append_task_event(
            task_id=task_id,
            event_type="task_failed",
            status="failed",
            summary=str(e),
            payload={
                "office_id": office_id,
                "workspace_id": workspace_id,
                "department": "尚书省 / 刑部",
                "stage": "agent_workflow" if office_id == "research" else "error",
                "impact": (
                    "研究报告没有完成，可能只保留了已经上传或自动截取的证据材料。"
                    if office_id == "research"
                    else "任务没有完成，最终交付物不会生成。"
                ),
                "next_action": (
                    "先检查模型配置和已有证据；如果已有截图、数据表或草稿，可以点击恢复动作整理已有研究产出。"
                    if office_id == "research"
                    else "查看日志和最后失败阶段，修复后重新执行任务。"
                ),
                "retry_action": (
                    {
                        "label": "整理已有研究产出",
                        "method": "POST",
                        "path": f"/api/tasks/{task_id}/recover-artifacts",
                    }
                    if office_id == "research"
                    else {}
                ),
            },
        )


def _format_quality_report(quality: dict) -> str:
    lines = [
        f"状态: {quality.get('status')}",
        f"分数: {quality.get('score')}",
        "",
        "缺失产物:",
    ]
    missing = quality.get("missing_artifacts") or []
    lines.extend([f"- {item}" for item in missing] or ["- 无"])
    lines.extend(["", "提醒:"])
    warnings = quality.get("warnings") or []
    lines.extend([f"- {item}" for item in warnings] or ["- 无"])
    return "\n".join(lines)


def _extract_markdown_title(text: str) -> str:
    for line in (text or "").splitlines():
        clean = line.strip()
        if clean.startswith("# "):
            return clean.lstrip("#").strip()
    return ""


def _is_unusable_report(text: str) -> bool:
    clean = (text or "").strip()
    return not clean or clean.startswith("[API错误]") or clean.startswith("[API閿欒]")


def _recover_unusable_final_report(task_id: str, result: dict) -> dict:
    """Replace unusable final_report with the latest generated markdown when possible."""
    result = dict(result or {})
    final_report = result.get("final_report", "")
    if not _is_unusable_report(final_report):
        return result
    recovered, path = _latest_markdown_output(task_id)
    if recovered and not _is_unusable_report(recovered):
        result["final_report"] = recovered
        result.setdefault("metadata", {})
        if isinstance(result["metadata"], dict):
            result["metadata"]["recovered_from_markdown"] = str(path)
        result["status"] = "completed"
    return result


def _latest_markdown_output(task_id: str) -> tuple[str, Path | None]:
    output_dir = Path(__file__).parent.parent.parent / "output" / task_id
    candidates = sorted(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if output_dir.exists() else []
    if not candidates:
        return "", None
    path = candidates[0]
    return path.read_text(encoding="utf-8"), path


@app.get("/api/tasks/history")
async def get_history(limit: int = 20):
    """获取任务历史"""
    history = []
    for item in config_manager.get_task_history(limit):
        history.append(_enrich_history_item(item))
    return {"history": history}


@app.get("/api/tasks/{task_id}/artifacts/{artifact_id}/download")
async def download_history_artifact_api(task_id: str, artifact_id: str):
    """Download archived artifact content from history, even when it has no file URI."""
    artifact = config_manager.get_artifact(artifact_id)
    if not artifact or artifact.get("task_id") != task_id:
        raise HTTPException(status_code=404, detail="历史产物不存在或不属于这个任务。")
    content = artifact.get("content") or json.dumps(artifact.get("metadata") or {}, ensure_ascii=False, indent=2)
    filename = _history_artifact_filename(artifact)
    try:
        parsed = json.loads(content)
        return JSONResponse(
            parsed,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except (TypeError, json.JSONDecodeError):
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8" if filename.endswith(".md") else "text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@app.get("/api/tasks/{task_id}/comic-v2-trace.json")
async def download_comic_v2_history_trace_api(task_id: str):
    """Download the comic-production V2 trace as a reproducible JSON artifact."""
    artifacts = config_manager.list_artifacts(task_id=task_id)
    word_canvas = next((
        a for a in reversed(artifacts)
        if a.get("artifact_type") in {"word_canvas", "comic_v2_word_canvas"}
    ), None)
    trace = _comic_v2_history_trace(artifacts, word_canvas)
    if not trace:
        raise HTTPException(status_code=404, detail="这个任务没有可下载的 AI 漫剧 V2 追溯记录。")
    return JSONResponse(
        trace,
        headers={"Content-Disposition": f'attachment; filename="{task_id}_comic_v2_trace.json"'},
    )


def _workspace_id_from_task_run(record: dict) -> str:
    for event in record.get("events", []) or []:
        payload = event.get("payload") or {}
        workspace_id = payload.get("workspace_id") or ""
        if workspace_id:
            return workspace_id
    return ""


def _history_artifact_filename(artifact: dict) -> str:
    artifact_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", artifact.get("artifact_id") or "artifact").strip("_")
    artifact_type = artifact.get("artifact_type") or ""
    content = artifact.get("content") or ""
    if artifact_type.endswith("_package") or artifact_type.endswith("_manifest") or content.lstrip().startswith(("{", "[")):
        suffix = ".json"
    elif artifact_type in {"report", "standard_report", "briefing"} or content.lstrip().startswith("#"):
        suffix = ".md"
    else:
        suffix = ".txt"
    return f"{artifact_id}{suffix}"


def _summarize_history_artifact(artifact: dict) -> dict:
    content = artifact.get("content") or ""
    metadata = artifact.get("metadata") or {}
    task_id = artifact.get("task_id", "")
    artifact_id = artifact.get("artifact_id", "")
    return {
        "artifact_id": artifact_id,
        "artifact_type": artifact.get("artifact_type", ""),
        "title": artifact.get("title", ""),
        "uri": artifact.get("uri", ""),
        "download_uri": f"/api/tasks/{task_id}/artifacts/{artifact_id}/download" if task_id and artifact_id else "",
        "created_by": artifact.get("created_by", ""),
        "created_at": artifact.get("created_at", ""),
        "metadata": {
            "office_id": metadata.get("office_id", ""),
            "source_id": metadata.get("source_id", ""),
            "shot_id": metadata.get("shot_id", ""),
        },
        "content_preview": content[:500],
    }


def _comic_v2_history_trace(artifacts: list[dict], word_canvas: dict | None) -> dict:
    if not word_canvas or word_canvas.get("artifact_type") != "comic_v2_word_canvas":
        return {}
    word_meta = word_canvas.get("metadata") or {}
    handoff_manifest = next(
        (a for a in reversed(artifacts) if a.get("artifact_type") == "comic_v2_handoff_manifest"),
        {},
    )
    prompt_package = next(
        (a for a in reversed(artifacts) if a.get("artifact_type") == "comic_v2_prompt_package"),
        {},
    )
    visual_review = next(
        (a for a in reversed(artifacts) if a.get("artifact_type") == "comic_v2_visual_review"),
        {},
    )
    handoff_meta = handoff_manifest.get("metadata") or {}
    prompt_meta = prompt_package.get("metadata") or {}
    review_meta = visual_review.get("metadata") or {}
    image_assets = [
        _comic_v2_history_image_asset(a)
        for a in artifacts
        if a.get("artifact_type") == "comic_v2_generated_image"
    ]
    prompt_quality: dict = {}
    if prompt_package:
        try:
            prompt_payload = json.loads(prompt_package.get("content") or "{}")
        except (TypeError, json.JSONDecodeError):
            prompt_payload = {}
        prompt_quality = audit_prompt_package(prompt_payload)
    quality_benchmark = handoff_meta.get("quality_benchmark") or word_meta.get("quality_benchmark") or {}
    claim_level = claim_level_from_benchmark(quality_benchmark) if quality_benchmark else ""
    image_production_evidence = _comic_v2_image_production_evidence(image_assets, quality_benchmark)
    return {
        "story_id": word_meta.get("story_id", ""),
        "story_version": word_meta.get("story_version", 0),
        "style_id": word_meta.get("style_id", ""),
        "style_version": word_meta.get("style_version", 0),
        "manifest_version": word_meta.get("manifest_version") or prompt_meta.get("manifest_version", 0),
        "handoff_manifest_uri": handoff_manifest.get("uri", "") or word_meta.get("handoff_manifest_uri", ""),
        "handoff_manifest_title": handoff_manifest.get("title", ""),
        "production_lineage": handoff_meta.get("production_lineage") or [],
        "shots": handoff_meta.get("shots") or [],
        "quality_benchmark": quality_benchmark,
        "claim_level": claim_level,
        "claim_upgrade_checklist": claim_upgrade_checklist(claim_level, quality_benchmark) if quality_benchmark else [],
        "prompt_package_title": prompt_package.get("title", ""),
        "asset_prompt_count": prompt_meta.get("asset_prompt_count", 0),
        "shot_prompt_count": prompt_meta.get("shot_prompt_count", 0),
        "prompt_quality": prompt_quality,
        "prompt_quality_status": prompt_quality.get("status", ""),
        "image_production_evidence": image_production_evidence,
        "image_assets": image_assets,
        "image_asset_count": len(image_assets),
        "visual_review": {
            "title": visual_review.get("title", ""),
            "production_ready": bool(review_meta.get("production_ready")),
            "record_count": review_meta.get("record_count", 0),
            "failure_count": review_meta.get("failure_count", 0),
        },
        "delivery_audit": word_meta.get("audit") or {},
    }


def _comic_v2_image_production_evidence(image_assets: list[dict], quality_benchmark: dict | None = None) -> dict:
    """Summarize whether history images can support real production-quality claims."""
    benchmark = quality_benchmark or {}
    total = len(image_assets)
    providers = sorted({str(item.get("provider") or "").strip() for item in image_assets if item.get("provider")})
    models = sorted({str(item.get("model") or "").strip() for item in image_assets if item.get("model")})
    uses_fixture = "fixture" in {provider.lower() for provider in providers}
    real_model_images = [
        item for item in image_assets
        if str(item.get("provider") or "").strip()
        and str(item.get("provider") or "").strip().lower() != "fixture"
    ]
    reviewed = [
        item for item in image_assets
        if item.get("review_status") or item.get("review_handoff_ready")
    ]
    passed = [
        item for item in image_assets
        if item.get("review_status") == "pass" and item.get("review_handoff_ready")
    ]
    failed = [
        item for item in reviewed
        if item.get("review_status") and item.get("review_status") != "pass"
        or (item.get("review_status") and not item.get("review_handoff_ready"))
    ]
    if not total:
        evidence_level = "missing_images"
        summary = "历史记录里没有可审计的图片资产。"
    elif total and uses_fixture and len(real_model_images) == 0:
        evidence_level = "fixture_only"
        summary = "图片来自固定样例，只能证明结构，不能证明真实模型画质。"
    elif len(real_model_images) == total and len(passed) == total:
        evidence_level = "model_reviewed"
        summary = "所有图片都有真实模型来源并通过视觉质检。"
    elif real_model_images:
        evidence_level = "model_partial"
        summary = "已有真实模型图片记录，但视觉质检或来源记录还没有完全闭环。"
    else:
        evidence_level = "mixed_or_unknown"
        summary = "图片来源混合或缺少 provider/model，不能支撑真实质量声明。"
    benchmark_verified = bool(benchmark.get("production_quality_verified"))
    benchmark_image_summary = benchmark.get("image_quality_summary") or {}
    return {
        "total_images": total,
        "providers": providers,
        "models": models,
        "uses_fixture": uses_fixture,
        "real_model_image_count": len(real_model_images),
        "reviewed_image_count": len(reviewed),
        "review_passed_image_count": len(passed),
        "review_failed_image_count": len(failed),
        "usable_image_count": int(benchmark_image_summary.get("usable_images") or len(passed)),
        "waste_or_rework_image_count": int(
            benchmark_image_summary.get("waste_or_rework_images")
            if benchmark_image_summary
            else max(0, total - len(passed))
        ),
        "waste_or_rework_rate": float(
            benchmark_image_summary.get("waste_or_rework_rate")
            if benchmark_image_summary
            else (round(max(0, total - len(passed)) / total, 4) if total else 0)
        ),
        "regenerate_image_count": int(benchmark_image_summary.get("regenerate_image_count") or 0),
        "rerun_visual_review_count": int(benchmark_image_summary.get("rerun_visual_review_count") or 0),
        "regenerate_prompt_count": int(benchmark_image_summary.get("regenerate_prompt_count") or 0),
        "failed_image_ids": list(benchmark_image_summary.get("failed_image_ids") or []),
        "rework_instructions": list(benchmark_image_summary.get("rework_instructions") or []),
        "evidence_level": evidence_level,
        "supports_real_quality_claim": evidence_level == "model_reviewed" and benchmark_verified,
        "summary": summary,
        "next_action": _comic_v2_image_production_next_action(evidence_level, benchmark_verified),
    }


def _comic_v2_image_production_next_action(evidence_level: str, benchmark_verified: bool) -> str:
    if evidence_level == "missing_images":
        return "先生成图片资产，再进入刑部视觉质检。"
    if evidence_level == "fixture_only":
        return "用真实模型重新生成图片，并保留 provider、model、image_id 和质检记录。"
    if evidence_level == "model_reviewed" and benchmark_verified:
        return "保留当前 manifest、图片记录和质量基准，作为真实质量声明证据。"
    if evidence_level == "model_reviewed":
        return "图片证据已足够，继续重跑质量基准并写入 handoff manifest。"
    if evidence_level == "model_partial":
        return "补齐失败图片的重试、视觉质检或 provider/model 记录。"
    return "复核图片来源，清理 fixture/未知来源后重新生成质量基准。"


def _comic_v2_history_image_asset(artifact: dict) -> dict:
    metadata = artifact.get("metadata") or {}
    review = metadata.get("review") or {}
    return {
        "artifact_id": artifact.get("artifact_id", ""),
        "title": artifact.get("title", ""),
        "uri": artifact.get("uri", ""),
        "image_id": metadata.get("image_id", ""),
        "asset_id": metadata.get("asset_id", ""),
        "image_kind": metadata.get("image_kind", ""),
        "production_role": metadata.get("production_role", ""),
        "clean_background_required": bool(metadata.get("clean_background_required", False)),
        "usage_contract": list(metadata.get("usage_contract") or []),
        "reference_policy": metadata.get("reference_policy", ""),
        "status": metadata.get("status", ""),
        "attempts": int(metadata.get("attempts") or 0),
        "provider": metadata.get("provider", ""),
        "model": metadata.get("model", ""),
        "prompt_hash": metadata.get("prompt_hash", ""),
        "is_identity_baseline": bool(metadata.get("is_identity_baseline")),
        "reference_image_ids": list(metadata.get("reference_image_ids") or []),
        "review_status": review.get("status", ""),
        "review_handoff_ready": bool(review.get("handoff_ready", False)),
        "review_recovery_action": review.get("recovery_action", ""),
        "review_recovery_focus": review.get("recovery_focus", ""),
        "review_recovery_reason": review.get("recovery_reason", ""),
        "review_rework_label": review.get("rework_label", ""),
        "review_operator_steps": list(review.get("operator_steps") or []),
    }


def _comic_v2_image_evidence_recovery_action(image_evidence: dict, prompt_count: int = 0) -> dict:
    """Return the safest recovery action for incomplete image-production evidence."""
    if not image_evidence or image_evidence.get("supports_real_quality_claim"):
        return {}
    evidence_level = str(image_evidence.get("evidence_level") or "")
    if evidence_level not in {"missing_images", "fixture_only", "model_partial", "mixed_or_unknown"}:
        return {}
    if evidence_level == "missing_images" and prompt_count <= 0:
        return {
            "label": "先补提示词包再生成图片",
            "action": "regenerate_prompts",
            "focus": "prompts",
            "expected_stage": "prompt_planning",
            "preserves": ["confirmed_story", "asset_manifest"],
            "clears": ["prompt_package", "image_production", "delivery"],
            "operator_steps": ["回到提示词规划", "生成资产和镜头提示词", "再进入图片生产"],
            "description": "历史记录没有图片，也没有可复用的提示词数量，先退回提示词阶段更安全。",
        }
    label = {
        "missing_images": "生成缺失的图片证据",
        "fixture_only": "用真实模型重做图片证据",
        "model_partial": "补齐失败或未质检的图片",
        "mixed_or_unknown": "重做来源不明的图片证据",
    }.get(evidence_level, "重做图片证据")
    return {
        "label": label,
        "action": "regenerate_images",
        "focus": "images",
        "expected_stage": "image_generation",
        "preserves": ["confirmed_story", "asset_manifest", "prompt_package"],
        "clears": ["image_production", "delivery"],
        "operator_steps": ["保留故事、资产和提示词", "用真实模型重新生成基础资产图", "重跑刑部视觉质检和质量基准"],
        "description": image_evidence.get("next_action") or "当前图片证据不足以支撑真实质量声明，需要回到图片生产阶段补齐。",
    }


def _history_delivery_summary(enriched: dict) -> dict:
    trace = enriched.get("comic_v2_trace") or {}
    workspace_id = enriched.get("workspace_id") or ""
    word_uri = enriched.get("word_canvas_uri") or ""
    handoff_uri = enriched.get("handoff_manifest_uri") or trace.get("handoff_manifest_uri") or ""
    artifact_types = {
        artifact.get("artifact_type")
        for artifact in enriched.get("artifacts") or []
        if artifact.get("artifact_type")
    }
    legacy_package = bool(enriched.get("legacy_comic_package"))
    downloadable_files = []
    if enriched.get("workspace_export_uri"):
        downloadable_files.append("完整归档包")
    if word_uri:
        downloadable_files.append("Word 制片画布")
    if handoff_uri:
        downloadable_files.append("引用清单")
    if "comic_v2_prompt_package" in artifact_types:
        downloadable_files.append("提示词包")
    elif "prompt_package" in artifact_types:
        downloadable_files.append("旧版提示词包")
    if {"comic_v2_generated_image", "generated_image"} & artifact_types:
        downloadable_files.append("图片资产")
    if enriched.get("comic_v2_trace_uri"):
        downloadable_files.append("追溯记录")

    audit = trace.get("delivery_audit") or {}
    asset_count = int(audit.get("asset_count") or trace.get("visual_review", {}).get("record_count") or 0)
    shot_count = int(audit.get("shot_count") or trace.get("shot_prompt_count") or 0)
    prompt_count = int(trace.get("asset_prompt_count") or 0) + int(trace.get("shot_prompt_count") or 0)
    prompt_quality = trace.get("prompt_quality") or {}
    prompt_quality_status = prompt_quality.get("status") or ""
    prompt_quality_issue_count = int(prompt_quality.get("issue_count") or 0)
    visual_review = trace.get("visual_review") or {}
    quality_benchmark = trace.get("quality_benchmark") or {}
    image_evidence = trace.get("image_production_evidence") or {}
    requires_quality_benchmark = bool(trace) or bool(
        {"comic_v2_word_canvas", "comic_v2_handoff_manifest"} & artifact_types
    )
    benchmark_ready = bool(quality_benchmark.get("package_quality_ready")) if quality_benchmark else True
    production_ready = bool(visual_review.get("production_ready") or audit.get("handoff_ready")) and benchmark_ready
    failure_count = int(visual_review.get("failure_count") or 0)

    missing_items = []
    if not word_uri:
        missing_items.append("Word 制片画布")
    if not legacy_package and not handoff_uri and enriched.get("office_id") == "comic_production":
        missing_items.append("引用清单")
    if asset_count <= 0 and trace:
        missing_items.append("资产统计")
    if shot_count <= 0 and trace:
        missing_items.append("镜头卡")
    if prompt_quality_status == "needs_review":
        missing_items.append("提示词质量门禁")
    if not legacy_package and requires_quality_benchmark and not quality_benchmark:
        missing_items.append("制片包质量基准")
    elif quality_benchmark and not benchmark_ready:
        missing_items.append("制片包质量基准")
    if image_evidence and not image_evidence.get("supports_real_quality_claim"):
        if image_evidence.get("evidence_level") in {"missing_images", "fixture_only", "model_partial", "mixed_or_unknown"}:
            missing_items.append("图片生产证据")
    if legacy_package:
        missing_items.append("V3 引用与质量清单")
    if failure_count > 0:
        missing_items.append("视觉质检问题")

    if legacy_package:
        status = "partial"
        next_action = "这是旧版制片包：Word 和旧材料仍可下载，但无法证明故事、资产、图片、镜头和质检属于同一版本。继续生产时建议用当前 V2 流程重新生成。"
    elif missing_items:
        status = "needs_review"
        if "制片包质量基准" in missing_items:
            next_action = quality_benchmark.get("next_action") or "先处理制片包质量基准中的阻塞项，再重新生成交付物。"
        elif "提示词质量门禁" in missing_items:
            next_action = "先重新生成提示词，或退回资产拆解修正人物、道具、场景，再继续图片和 Word 制片画布生产。"
        else:
            next_action = "先补齐缺失项或重新生成 Word 制片画布，再交给下游生产。"
    elif word_uri and production_ready:
        status = "ready"
        next_action = "制片包可以交给下游图片、视频或剪辑平台继续生产。"
    elif word_uri:
        status = "partial"
        next_action = "已有 Word 制片画布，但建议先检查引用清单和视觉质检结果。"
    else:
        status = "pending"
        next_action = "等待生成可下载交付物。"

    recovery_actions = []
    benchmark_recovery = quality_benchmark.get("recommended_recovery") or {}
    benchmark_action = str(benchmark_recovery.get("action") or "")
    image_evidence_recovery = _comic_v2_image_evidence_recovery_action(image_evidence, prompt_count)
    if workspace_id and not legacy_package and not benchmark_action and image_evidence_recovery:
        recovery_actions.append({
            "label": image_evidence_recovery["label"],
            "method": "POST",
            "path": f"/api/workspaces/{workspace_id}/comic/v2/quality/recover",
            "body": {"action": image_evidence_recovery["action"]},
            "workspace_id": workspace_id,
            "office_id": enriched.get("office_id") or "comic_production",
            "focus": image_evidence_recovery["focus"],
            "expected_stage": image_evidence_recovery["expected_stage"],
            "preserves": image_evidence_recovery["preserves"],
            "clears": image_evidence_recovery["clears"],
            "operator_steps": image_evidence_recovery["operator_steps"],
            "description": image_evidence_recovery["description"],
        })
    if workspace_id and not legacy_package and not benchmark_ready and benchmark_action in {
        "revise_assets",
        "regenerate_prompts",
        "regenerate_images",
        "rebuild_delivery",
    }:
        recovery_actions.append({
            "label": benchmark_recovery.get("label") or "按质量问题退回处理",
            "method": "POST",
            "path": f"/api/workspaces/{workspace_id}/comic/v2/quality/recover",
            "body": {"action": benchmark_action},
            "workspace_id": workspace_id,
            "office_id": enriched.get("office_id") or "",
            "focus": benchmark_recovery.get("focus") or "workspace",
            "expected_stage": benchmark_recovery.get("expected_stage") or "",
            "preserves": benchmark_recovery.get("preserves") or [],
            "clears": benchmark_recovery.get("clears") or [],
            "operator_steps": benchmark_recovery.get("operator_steps") or [],
            "description": benchmark_recovery.get("description") or "",
        })
    elif workspace_id and not legacy_package and "制片包质量基准" in missing_items and not quality_benchmark:
        recovery_actions.append({
            "label": "补齐 V3 引用与质量清单",
            "method": "POST",
            "path": f"/api/workspaces/{workspace_id}/comic/v2/quality/recover",
            "body": {"action": "rebuild_delivery"},
            "workspace_id": workspace_id,
            "office_id": enriched.get("office_id") or "comic_production",
            "focus": "delivery",
        })
    if workspace_id and not legacy_package and ("Word 制片画布" in missing_items or "引用清单" in missing_items):
        recovery_actions.append({
            "label": "重新生成 Word 制片画布",
            "method": "POST",
            "path": f"/api/workspaces/{workspace_id}/comic/v2/delivery/build",
            "workspace_id": workspace_id,
            "office_id": enriched.get("office_id") or "",
            "focus": "delivery",
        })
    if workspace_id and not legacy_package and "视觉质检问题" in missing_items and not benchmark_action:
        recovery_actions.append({
            "label": "重新生成并质检基础资产图",
            "method": "POST",
            "path": f"/api/workspaces/{workspace_id}/comic/v2/images/generate",
            "workspace_id": workspace_id,
            "office_id": enriched.get("office_id") or "",
            "focus": "images",
        })
    if workspace_id and not legacy_package and "提示词质量门禁" in missing_items and not benchmark_action:
        recovery_actions.append({
            "label": "重新生成提示词",
            "method": "POST",
            "path": f"/api/workspaces/{workspace_id}/comic/v2/prompts/plan",
            "workspace_id": workspace_id,
            "office_id": enriched.get("office_id") or "",
            "focus": "prompts",
        })
    if workspace_id and status in {"pending", "needs_review"} and not recovery_actions:
        recovery_actions.append({
            "label": "回到项目继续处理",
            "method": "GET",
            "path": f"/api/workspaces/{workspace_id}",
            "workspace_id": workspace_id,
            "office_id": "comic_production",
            "focus": "workspace",
        })
    return {
        "status": status,
        "asset_count": asset_count,
        "shot_count": shot_count,
        "prompt_count": prompt_count,
        "prompt_quality_status": prompt_quality_status,
        "prompt_quality_issue_count": prompt_quality_issue_count,
        "prompt_quality_summary": prompt_quality.get("summary", ""),
        "package_quality_score": int(quality_benchmark.get("package_quality_score") or 0),
        "package_quality_claim": "legacy_unverifiable" if legacy_package else quality_benchmark.get("status", ""),
        "package_quality_ready": False if legacy_package else benchmark_ready,
        "production_quality_verified": bool(quality_benchmark.get("production_quality_verified")),
        "package_quality_summary": (
            "旧版制片包没有 V3 引用与质量清单，只能下载留档，不能证明跨产物一致性。"
            if legacy_package
            else quality_benchmark.get("summary", "")
        ),
        "legacy_package": legacy_package,
        "visual_review_status": "passed" if production_ready and failure_count == 0 else "needs_review",
        "downloadable_files": downloadable_files,
        "missing_items": missing_items,
        "next_action": next_action,
        "recovery_actions": recovery_actions,
    }


def _enrich_history_item(item: dict) -> dict:
    task_id = item.get("task_id", "")
    artifacts = config_manager.list_artifacts(task_id=task_id) if task_id else []
    run_record = config_manager.get_task_run(task_id) if task_id else {}
    workspace_id = ""
    if artifacts:
        workspace_id = artifacts[0].get("workspace_id") or ""
    if not workspace_id and run_record:
        workspace_id = _workspace_id_from_task_run(run_record)
    workspace = config_manager.get_workspace(workspace_id) if workspace_id else {}
    word_canvas = next((
        a for a in reversed(artifacts)
        if a.get("artifact_type") in {"word_canvas", "comic_v2_word_canvas"}
    ), None)
    downloadable_word_canvas = next((
        a for a in reversed(artifacts)
        if a.get("artifact_type") in {"word_canvas", "comic_v2_word_canvas"} and a.get("uri")
    ), None)
    handoff_manifest = next((
        a for a in reversed(artifacts)
        if a.get("artifact_type") == "comic_v2_handoff_manifest" and a.get("uri")
    ), None)
    report_record = config_manager.get_task_result(task_id) if task_id else {}
    result = report_record.get("result") or run_record.get("result") or {}
    final_report = result.get("final_report") or ""
    enriched = dict(item)
    trace = _comic_v2_history_trace(artifacts, word_canvas)
    legacy_comic_package = bool(
        word_canvas
        and word_canvas.get("artifact_type") == "word_canvas"
        and workspace.get("office_id") in {"comic", "comic_production"}
    )
    enriched.update({
        "workspace_id": workspace_id,
        "workspace_title": workspace.get("title", ""),
        "office_id": workspace.get("office_id", ""),
        "artifact_count": len(artifacts),
        "artifacts": [_summarize_history_artifact(a) for a in artifacts],
        "word_canvas_uri": downloadable_word_canvas.get("uri", "") if downloadable_word_canvas else "",
        "word_canvas_title": word_canvas.get("title", "") if word_canvas else "",
        "handoff_manifest_uri": handoff_manifest.get("uri", "") if handoff_manifest else "",
        "handoff_manifest_title": handoff_manifest.get("title", "") if handoff_manifest else "",
        "workspace_export_uri": f"/api/workspaces/{workspace_id}/export" if workspace_id else "",
        "current_phase": run_record.get("current_phase", ""),
        "updated_at": run_record.get("updated_at", ""),
        "completed_at": run_record.get("completed_at", ""),
        "final_report_preview": final_report[:1200],
        "comic_v2_trace": trace,
        "legacy_comic_package": legacy_comic_package,
        "comic_v2_trace_uri": f"/api/tasks/{task_id}/comic-v2-trace.json" if trace else "",
    })
    enriched["delivery_summary"] = _history_delivery_summary(enriched)
    return enriched


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """查询任务详情（含完整结果和最终报告）"""
    record = config_manager.get_task_run(task_id) or config_manager.get_task_result(task_id)
    if not record:
        raise _research_http_error(
            404,
            department="尚书省",
            reason=f"任务 {task_id} 不存在或已被清理。",
            impact="无法读取任务进度、事件日志或最终报告，历史详情页也无法恢复这次执行。",
            next_action="从历史列表选择真实存在的任务；如果任务被中断或清理，请重新提交工单。",
            stage="task_lookup",
        )
    return record


@app.get("/api/tasks/{task_id}/report")
async def get_task_report(task_id: str):
    """获取任务的最终报告"""
    record = config_manager.get_task_result(task_id)
    if not record:
        raise _research_http_error(
            404,
            department="尚书省",
            reason=f"任务 {task_id} 不存在或已被清理。",
            impact="无法读取任务进度、事件日志或最终报告，历史详情页也无法恢复这次执行。",
            next_action="从历史列表选择真实存在的任务；如果任务被中断或清理，请重新提交工单。",
            stage="task_lookup",
        )
    result = record.get("result", {})
    final_report = result.get("final_report", "")
    return {
        "task_id": task_id,
        "status": record.get("status"),
        "user_request": record.get("user_request"),
        "report": final_report or "(无最终报告)",
        "plan": result.get("plan", {}),
        "results": result.get("results", []),
    }


# ============================================================
# 配置 API
# ============================================================

@app.get("/api/config")
async def get_config():
    """获取不包含明文凭据的公开配置。"""
    return _public_full_config(config_manager.load_yaml())


def _public_model_config(config: dict | None) -> dict:
    source = dict(config or {})
    has_api_key = bool(str(source.pop("api_key", "") or "").strip())
    source["has_api_key"] = has_api_key
    source["api_key_hint"] = "已配置" if has_api_key else "未配置"
    return source


def _public_full_config(config: dict | None) -> dict:
    public = dict(config or {})
    public["models"] = {
        agent_id: _public_model_config(model)
        for agent_id, model in (public.get("models", {}) or {}).items()
    }
    public["office_models"] = {
        office_id: {
            agent_id: _public_model_config(model)
            for agent_id, model in (models or {}).items()
        }
        for office_id, models in (public.get("office_models", {}) or {}).items()
    }
    return public


@app.get("/api/config/models")
async def get_models(office_id: str = ""):
    """获取模型配置；传 office_id 时返回该办公室的有效配置。"""
    config = config_manager.load_yaml()
    global_models = config.get("models", {}) or {}
    if not office_id:
        return {
            "models": {agent_id: _public_model_config(model) for agent_id, model in global_models.items()},
            "office_id": "",
        }
    scoped_models = ((config.get("office_models", {}) or {}).get(office_id, {}) or {})
    agent_ids = set(global_models) | set(scoped_models)
    effective = {
        agent_id: {**(global_models.get(agent_id, {}) or {}), **(scoped_models.get(agent_id, {}) or {})}
        for agent_id in agent_ids
    }
    return {
        "models": {agent_id: _public_model_config(model) for agent_id, model in effective.items()},
        "office_id": office_id,
        "scope": "office",
        "inherits_from_global": True,
    }


@app.put("/api/config/models/{agent_id}")
async def update_model(agent_id: str, update: ModelConfigUpdate, office_id: str = ""):
    """更新某个部门的模型配置；传 office_id 时只更新该办公室。"""
    config = config_manager.load_yaml()
    if office_id:
        models = config.setdefault("office_models", {}).setdefault(office_id, {})
    else:
        models = config.setdefault("models", {})
    agent_config = models.setdefault(agent_id, {})
    warnings = []

    if update.provider is not None:
        previous_provider = agent_config.get("provider")
        agent_config["provider"] = update.provider.strip()
        if previous_provider and previous_provider != update.provider and update.api_key is None:
            agent_config["api_key"] = ""
            warnings.append("Provider changed; previous API key was cleared to avoid cross-provider mismatch.")
    if update.model is not None:
        agent_config["model"] = update.model.strip()
    if update.api_key is not None:
        agent_config["api_key"] = update.api_key.strip()
    if update.api_base is not None:
        agent_config["api_base"] = update.api_base.strip()
    if update.temperature is not None:
        agent_config["temperature"] = update.temperature
    if update.max_tokens is not None:
        agent_config["max_tokens"] = update.max_tokens

    config_manager.save_yaml(config)
    return {
        "status": "ok",
        "agent": agent_id,
        "office_id": office_id,
        "config": _public_model_config(agent_config),
        "warnings": warnings,
    }


@app.post("/api/config/models/{agent_id}/test")
async def test_model(agent_id: str, office_id: str = ""):
    """Run a lightweight connectivity probe for one office-scoped department."""
    if agent_id not in AGENT_IDS:
        raise _system_http_error(
            404,
            department="模型配置",
            reason=f"未知部门或 Agent：{agent_id}。",
            impact="系统无法测试这个模型配置，也无法判断该部门是否可用。",
            next_action="请选择页面上已有的部门，例如中书省、门下省、工部、刑部等，再点击测试。",
            stage="model_test",
        )
    config = config_manager.get_model_config(agent_id, office_id=office_id)
    return await probe_model_connectivity(agent_id, office_id, config)


@app.post("/api/config/models/test")
async def test_models(office_id: str = ""):
    """Run lightweight connectivity probes for all departments in one office."""
    results = []
    for agent_id in AGENT_IDS:
        config = config_manager.get_model_config(agent_id, office_id=office_id)
        results.append(await probe_model_connectivity(agent_id, office_id, config))
    return {
        "office_id": office_id,
        "status": "ok" if all(item["status"] == "ok" for item in results) else "needs_attention",
        "results": results,
    }


@app.get("/api/config/system")
async def get_system_config():
    """获取系统配置"""
    sys_conf = config_manager.get_system_config()
    return {
        "max_zhongshu_menxia_rounds": sys_conf.max_zhongshu_menxia_rounds,
        "max_bingbu_xingbu_retries": sys_conf.max_bingbu_xingbu_retries,
        "max_orchestrator_loops": sys_conf.max_orchestrator_loops,
        "similarity_threshold": sys_conf.similarity_threshold,
    }


# ============================================================
# 提示词 API
# ============================================================

@app.get("/api/prompts")
async def list_prompts():
    """列出所有部门的提示词状态"""
    agents = ["zhongshu", "menxia", "shangshu", "libu", "hubu", "libu_comm", "bingbu", "xingbu", "gongbu"]
    custom = config_manager.list_custom_prompts()
    return {
        "agents": [
            {
                "id": a,
                "name": AgentId[a.upper()].value if a.upper() in AgentId.__members__ else a,
                "is_custom": a in custom,
                "preview": config_manager.get_prompt(a)[:100] + "...",
            }
            for a in agents
        ]
    }


@app.get("/api/prompts/{agent}")
async def get_prompt(agent: str):
    """获取某部门的完整 System Prompt"""
    return {"agent": agent, "text": config_manager.get_prompt(agent)}


@app.put("/api/prompts/{agent}")
async def update_prompt(agent: str, update: PromptUpdate):
    """更新某部门的 System Prompt"""
    config_manager.save_prompt(agent, update.text)
    return {"status": "ok", "agent": agent}


@app.delete("/api/prompts/{agent}")
async def delete_prompt(agent: str):
    """删除自定义提示词,回退默认"""
    config_manager.delete_prompt(agent)
    return {"status": "ok", "agent": agent, "note": "已回退到默认提示词"}


# ============================================================
# 工具 API
# ============================================================

@app.get("/api/tools")
async def list_tools():
    """列出所有可用工具"""
    from src.tools import tool_registry
    defs = tool_registry.get_definitions()
    tools = []
    for d in defs:
        func = d.get("function", {})
        params = func.get("parameters", {})
        tools.append({
            "name": func.get("name", ""),
            "description": func.get("description", ""),
            "parameters": list(params.get("properties", {}).keys()) if params.get("properties") else [],
        })
    return {"tools": tools}


@app.post("/api/tools/upload")
async def upload_tool(file: UploadFile = File(...)):
    """上传自定义工具文件"""
    content = await file.read()
    path = config_manager.tools_dir / file.filename
    path.write_bytes(content)
    return {"status": "ok", "filename": file.filename}

# ============================================================
# 模板 API
# ============================================================

@app.get("/api/templates")
async def list_templates():
    """列出所有模板"""
    return {"templates": config_manager.list_templates()}


@app.post("/api/templates")
async def create_template(tpl: TemplateCreate):
    """创建自定义模板"""
    config_manager.save_template(tpl.id, {
        "name": tpl.name,
        "description": tpl.description,
        "default_prompt": tpl.default_prompt,
    })
    return {"status": "ok", "id": tpl.id}


@app.post("/api/templates/upload")
async def upload_template(file: UploadFile = File(...)):
    """上传自定义模板文件"""
    content = await file.read()
    path = config_manager.templates_dir / file.filename
    path.write_bytes(content)
    return {"status": "ok", "filename": file.filename}

# ============================================================
# WebSocket — 实时推送
# ============================================================

@app.websocket("/ws/tasks/{task_id}")
async def ws_task(websocket: WebSocket, task_id: str):
    """订阅某个任务的实时进度"""
    await websocket.accept()
    active_ws.setdefault(task_id, []).append(websocket)
    try:
        while True:
            # 保持连接, 等待客户端消息 (心跳)
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_ws[task_id].remove(websocket)


@app.websocket("/ws/court")
async def ws_court(websocket: WebSocket):
    """订阅朝堂事件的全局广播"""
    await websocket.accept()
    court_ws.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        court_ws.remove(websocket)


async def _broadcast_task(task_id: str, data: dict):
    """向订阅某任务的所有客户端推送"""
    if task_id in active_ws:
        for ws in active_ws[task_id]:
            try:
                await ws.send_json(data)
            except Exception:
                pass


async def _broadcast_court(data: dict):
    """向订阅朝堂的所有客户端推送"""
    for ws in court_ws:
        try:
            await ws.send_json(data)
        except Exception:
            pass


# ============================================================
# 文件下载
# ============================================================

@app.get("/api/tasks/{task_id}/files")
async def list_task_files(task_id: str):
    """列出任务生成的所有文件"""
    from pathlib import Path
    output_dir = Path(__file__).parent.parent.parent / "output" / task_id
    if not output_dir.exists():
        return {"task_id": task_id, "files": []}
    files = []
    for f in sorted(output_dir.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(output_dir.parent))
            files.append({"name": f.name, "path": rel, "size": f.stat().st_size})
    return {"task_id": task_id, "files": files}


@app.get("/api/tasks/{task_id}/download/{filename:path}")
async def download_task_file(task_id: str, filename: str):
    """下载任务产出的文件"""
    from pathlib import Path
    filepath = Path(__file__).parent.parent.parent / "output" / task_id / filename
    if not filepath.exists():
        raise _research_http_error(
            404,
            department="礼部",
            reason=f"任务文件 {filename} 不存在或已被清理。",
            impact="用户无法下载这份历史交付物，报告或画布引用也会失效。",
            next_action="回到历史记录下载仍存在的交付文件；如果文件已清理，请重新生成该任务产物。",
            stage="task_file_download",
        )
    return FileResponse(str(filepath), filename=filename)


# ============================================================
# 静态文件
# ============================================================

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ============================================================
# 启动
# ============================================================

def start_server(host: str = "0.0.0.0", port: int = 8080):
    """启动 Web 服务器"""
    import uvicorn
    import io, sys
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

    print(f"""
╔══════════════════════════════════════════════════════╗
║        三个臭皮匠 - 多 Agent 办公室                    ║
║                                                      ║
║  服务已启动: http://{host}:{port}                      ║
║  配置面板: http://{host}:{port}/#config              ║
║  API 文档: http://{host}:{port}/docs                ║
║                                                      ║
║  按 Ctrl+C 停止服务                                  ║
╚══════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
