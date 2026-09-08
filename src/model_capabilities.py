"""Machine-readable model capability requirements for offices.

This module is intentionally no-key and side-effect free. It only reads the
public capability matrix used by docs, first-run checks, and office preflight.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = REPO_ROOT / "docs" / "MODEL_CAPABILITY_MATRIX.json"


@lru_cache(maxsize=1)
def load_model_capability_matrix() -> dict[str, Any]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def get_office_capability_contract(office_id: str) -> dict[str, Any]:
    normalized = "comic_production" if office_id == "comic" else office_id
    matrix = load_model_capability_matrix()
    office = (matrix.get("offices") or {}).get(normalized, {})
    return {
        "schema": matrix.get("schema"),
        "source": "docs/MODEL_CAPABILITY_MATRIX.json",
        "office_id": normalized,
        "office_name": office.get("office_name", normalized),
        "minimum_mode": office.get("minimum_mode", ""),
        "full_mode": office.get("full_mode", ""),
        "minimum_ready_when": office.get("minimum_ready_when", ""),
        "full_ready_when": office.get("full_ready_when", ""),
        "departments": list(office.get("departments") or []),
        "capability_kinds": matrix.get("capability_kinds") or {},
        "safe_key_rule": matrix.get("safe_key_rule", ""),
    }


def summarize_office_capability_contract(office_id: str) -> dict[str, Any]:
    contract = get_office_capability_contract(office_id)
    departments = contract.get("departments") or []
    capability_counts: dict[str, int] = {}
    for department in departments:
        capability = str(department.get("required_capability") or "unknown")
        capability_counts[capability] = capability_counts.get(capability, 0) + 1
    return {
        "schema": contract.get("schema"),
        "source": contract.get("source"),
        "office_id": contract.get("office_id"),
        "office_name": contract.get("office_name"),
        "minimum_mode": contract.get("minimum_mode"),
        "full_mode": contract.get("full_mode"),
        "department_count": len(departments),
        "capability_counts": capability_counts,
        "minimum_ready_when": contract.get("minimum_ready_when"),
        "full_ready_when": contract.get("full_ready_when"),
    }


def _public_provider_examples(capability: dict[str, Any]) -> list[dict[str, Any]]:
    provider_labels = {
        "deepseek": "DeepSeek 本地密钥",
        "dashscope": "千问/DashScope 本地密钥",
        "openai": "OpenAI 本地密钥",
        "doubao": "豆包/火山方舟本地密钥",
    }
    public_examples: list[dict[str, Any]] = []
    for provider in capability.get("provider_examples") or []:
        copied = dict(provider)
        provider_name = str(copied.get("provider") or "")
        copied.pop("api_key_env", None)
        copied["local_secret_label"] = provider_labels.get(provider_name, "本地密钥")
        public_examples.append(copied)
    return public_examples


def _department_setup_card(
    office_id: str,
    department: dict[str, Any],
    capability_kinds: dict[str, Any],
) -> dict[str, Any]:
    capability_kind = str(department.get("required_capability") or "unknown")
    capability = capability_kinds.get(capability_kind) or {}
    config_path = (
        f"office_models.{office_id}.{department.get('department_id')}"
        if capability_kind != "browser_or_human_evidence"
        else ""
    )
    return {
        "department_id": department.get("department_id", ""),
        "display_name": department.get("display_name", ""),
        "required_capability": capability_kind,
        "capability_label": capability.get("label", capability_kind),
        "capability_means": capability.get("means", ""),
        "config_path_hint": config_path,
        "human_test_label": department.get("human_test_label", ""),
        "missing_impact": department.get("missing_impact", ""),
        "required_for": list(department.get("required_for") or []),
        "model_page_hint": department.get("model_page_hint", ""),
        "provider_examples": _public_provider_examples(capability),
        "next_step": (
            department.get("model_page_hint")
            or f"在模型页测试{department.get('display_name', department.get('department_id', '该部门'))}。"
        ),
    }


def build_model_setup_guide() -> dict[str, Any]:
    """Build a public, no-key setup guide for first-run model configuration."""
    matrix = load_model_capability_matrix()
    capability_kinds = matrix.get("capability_kinds") or {}
    offices: list[dict[str, Any]] = []
    for office_id, office in (matrix.get("offices") or {}).items():
        departments = [
            _department_setup_card(office_id, department, capability_kinds)
            for department in office.get("departments") or []
        ]
        text_departments = [
            item
            for item in departments
            if item.get("required_capability") == "text"
        ]
        non_text_departments = [
            item
            for item in departments
            if item.get("required_capability") != "text"
        ]
        offices.append(
            {
                "office_id": office_id,
                "office_name": office.get("office_name", office_id),
                "minimum_mode": office.get("minimum_mode", ""),
                "full_mode": office.get("full_mode", ""),
                "no_key_demo": {
                    "title": "公开无 Key 演示",
                    "requires_api_key": False,
                    "calls_real_models": False,
                    "what_user_can_do": "查看固定样例、下载交付物、理解产品边界。",
                },
                "minimum_setup": {
                    "title": "最小可跑配置",
                    "requires_api_key": True,
                    "required_departments": text_departments,
                    "ready_when": office.get("minimum_ready_when", ""),
                },
                "full_setup": {
                    "title": "完整生产配置",
                    "requires_api_key": True,
                    "required_departments": departments,
                    "extra_departments_after_minimum": non_text_departments,
                    "ready_when": office.get("full_ready_when", ""),
                },
                "common_misfills": _office_common_misfills(office_id),
            }
        )
    return {
        "schema": "three_cobblers_model_setup_guide_v1",
        "source": "docs/MODEL_CAPABILITY_MATRIX.json",
        "public_safe": True,
        "requires_api_key_to_view": False,
        "calls_real_models": False,
        "writes_workspace": False,
        "safe_key_rule": matrix.get("safe_key_rule", ""),
        "offices": offices,
    }


def _office_common_misfills(office_id: str) -> list[dict[str, str]]:
    if office_id == "comic_production":
        return [
            {
                "mistake": "把生图模型填到兵部",
                "why_bad": "兵部负责镜头执行卡、动作链和视频提示词，需要文本模型。",
                "correct_action": "兵部填 DeepSeek、千问文本或 GPT 文本；工部再填生图模型。",
            },
            {
                "mistake": "把文本模型填到工部后期待生成图片",
                "why_bad": "工部在 AI 漫剧制片办公室是生图槽位，文本模型只能写提示词。",
                "correct_action": "工部填豆包 Seedream、Qwen Image、MiniMax Image 等生图模型。",
            },
            {
                "mistake": "把普通文本千问填到刑部后期待看图",
                "why_bad": "刑部要做图片一致性质检，需要视觉理解模型。",
                "correct_action": "刑部填 Qwen VL、GPT 多模态或其他视觉理解模型。",
            },
        ]
    if office_id == "research":
        return [
            {
                "mistake": "把研究办公室工部当成普通 API Key 槽位",
                "why_bad": "研究办公室工部代表截图、浏览器或人工证据能力，不是纯文本模型能力。",
                "correct_action": "通过登录后的浏览器、人工上传截图或平台导出文件补证据。",
            }
        ]
    return []
