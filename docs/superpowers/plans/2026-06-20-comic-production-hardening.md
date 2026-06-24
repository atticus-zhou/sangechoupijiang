# AI Comic Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the comic office secure, style-consistent, observable, and honest about production quality.

**Architecture:** Add small pure helpers for credential redaction, visual style contracts, batch progress and image quality gating. Keep the existing workflow and API routes, but pass the new contracts through package metadata, image specs, task events and production-chain state.

**Tech Stack:** Python 3, FastAPI, unittest, vanilla JavaScript, SQLite-backed config manager.

---

### Task 1: Protect model credentials

**Files:** `src/web/app.py`, `src/web/static/js/app.js`, `tests/test_model_connectivity_api.py`

- [ ] Add a failing API test asserting model reads never return the stored key and expose `has_api_key=true`.
- [ ] Run `D:\python\python.exe -m unittest tests.test_model_connectivity_api -v` and confirm failure.
- [ ] Add `_public_model_config()` and apply it to GET/PUT responses; update the password field to show no returned secret and preserve the key when blank.
- [ ] Re-run the model API tests and confirm they pass.

### Task 2: Add a global visual style contract

**Files:** `src/comic_office/workflow.py`, `src/comic_artifacts.py`, `tests/test_comic_office_workflow.py`

- [ ] Add a failing test for an ancient-fantasy package requiring one shared `style_id`, ancient costume/material/architecture anchors, and modern-element exclusions on every character, prop and scene prompt.
- [ ] Run the focused test and confirm failure.
- [ ] Implement `build_visual_style_contract()` and apply the contract after asset enrichment and prompt enhancement.
- [ ] Include the contract in `comic_package` and the human asset review artifact.
- [ ] Re-run focused workflow tests and confirm they pass.

### Task 3: Make image generation isolated and observable

**Files:** `src/web/app.py`, `src/web/static/js/app.js`, `tests/test_comic_image_pipeline.py`, `tests/test_frontend_comic_routing.py`

- [ ] Add failing tests asserting output paths include `task_id` and per-image start/completion/failure events are recorded.
- [ ] Run focused tests and confirm failure.
- [ ] Generate into `generated/<task_id>/`, include `task_id` in delivery image resolution, and append progress events with index, total, source ID and counts.
- [ ] Render progress events in the comic stage board.
- [ ] Re-run focused tests and confirm they pass.

### Task 4: Enforce an honest visual quality gate

**Files:** `src/comic_office/production_chain.py`, `src/web/app.py`, `src/comic_artifacts.py`, `tests/test_comic_production_chain.py`, `tests/test_comic_image_pipeline.py`

- [ ] Add failing tests proving a batch with `needs_review`, score 0 or missing review blocks handoff and prevents Xingbu completion.
- [ ] Run focused tests and confirm failure.
- [ ] Extend `build_production_quality_gate()` with image quality summaries and change Xingbu/UI status to `waiting_for_human` or `blocked`.
- [ ] Report review failures accurately instead of “no obvious issue”.
- [ ] Re-run focused tests and confirm they pass.

### Task 5: Improve prompt enhancement resilience

**Files:** `src/comic_office/workflow.py`, `tests/test_comic_office_workflow.py`

- [ ] Add failing tests for JSON wrapped in fences/prose and for preserving style contracts after LLM enhancement.
- [ ] Run focused tests and confirm failure.
- [ ] Normalize candidate JSON, retry only invalid structured output, and keep explicit fallback metadata.
- [ ] Re-run focused tests and confirm they pass.

### Task 6: Align story readiness and episode count

**Files:** `src/comic_office/workflow.py`, `tests/test_comic_office_workflow.py`, `tests/test_web_comic_api.py`

- [ ] Add failing tests proving a complete full script with an ending can confirm without another question and a three-episode request produces three episode outlines.
- [ ] Run focused tests and confirm failure.
- [ ] Derive readiness from validated script content and normalize outlines to the requested episode count without rewriting the story.
- [ ] Re-run focused tests and confirm they pass.

### Task 7: Integrated verification

**Files:** all files above

- [ ] Run `D:\python\python.exe -m unittest tests.test_model_connectivity_api tests.test_comic_office_workflow tests.test_comic_image_pipeline tests.test_comic_production_chain tests.test_frontend_comic_routing tests.test_web_comic_api -v`.
- [ ] Run `rg -n "不要" src` and confirm no matches.
- [ ] Restart the local server and verify `/api/offices` returns HTTP 200.
- [ ] Review `git diff --check` and summarize any remaining production risks.
