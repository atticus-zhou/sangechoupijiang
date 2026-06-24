# Comic Production V2 Live Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the isolated comic-production V2 contracts into the default, human-reviewable production chain from confirmed story to audited Word canvas.

**Architecture:** Keep V2 logic under `src/comic_office/v2/` and expose narrow FastAPI transition endpoints. Every transition reads server-owned workspace state, writes a versioned artifact and an event, and blocks on explicit human or quality gates. The legacy workflow remains a fallback until browser and full-regression verification pass.

**Tech Stack:** Python 3, FastAPI, LiteLLM, dataclasses, python-docx, unittest, vanilla JavaScript.

---

### Task 1: Online contract planner and visual-bible review

**Files:**
- Create: `src/comic_office/v2/planner.py`
- Create: `tests/test_comic_v2_planner.py`
- Modify: `src/comic_office/v2/pipeline.py`
- Modify: `src/web/app.py`
- Modify: `tests/test_comic_v2_pipeline.py`

- [x] Write failing tests proving the planner preserves the confirmed story, rejects API-error or malformed JSON responses, and builds a validated contract from structured model output.
- [x] Run `python -m unittest tests.test_comic_v2_planner -v` and verify failure because the planner module is absent.
- [x] Implement `plan_contract()` with injected LLM support, `parse_json_object()`, contract validation, and explicit `planning_failed` errors without rule fallback.
- [x] Write failing API tests proving planning reads the server-owned confirmed script and uses `office_id=comic_production`, `agent=zhongshu`.
- [x] Implement `/comic/v2/plan-confirmed`, `/comic/v2/visual-bible/approve`, and `/comic/v2/visual-bible/revise`; revisions increment `style_version` and invalidate downstream state.
- [x] Run focused tests and commit the slice.

### Task 2: Evidence-backed asset planning and human review

**Files:**
- Create: `src/comic_office/v2/asset_planner.py`
- Create: `tests/test_comic_v2_asset_planner.py`
- Modify: `src/comic_office/v2/pipeline.py`
- Modify: `src/web/app.py`
- Modify: `tests/test_web_comic_api.py`

- [x] Write failing tests for evidence-grounded characters, props, and scenes; reject invented assets and missing evidence.
- [x] Implement online asset planning through the configured `zhongshu` model and validation through `build_asset_manifest()`.
- [x] Write failing tests for approve and revise transitions, including no-op revision rejection and manifest version increment.
- [x] Implement `/assets/plan`, `/assets/approve`, and `/assets/revise`, persisting a versioned manifest artifact and user-visible events.
- [x] Run focused tests and commit the slice.

### Task 3: Prompt directing, image generation, and cross-image review

**Files:**
- Create: `src/comic_office/v2/production.py`
- Create: `tests/test_comic_v2_production.py`
- Modify: `src/comic_office/v2/pipeline.py`
- Modify: `src/web/app.py`
- Modify: `tests/test_comic_image_pipeline.py`

- [ ] Write failing tests proving each asset and shot receives its own model-generated prompt bound to story, style, and asset versions.
- [ ] Implement prompt batches using `gongbu`, rejecting malformed model output instead of silently substituting templates.
- [ ] Write failing tests proving character/prop images use clean white backgrounds, scenes use spatial views, and generation records image IDs and reference IDs.
- [ ] Integrate the existing image provider behind V2 generation records.
- [ ] Write failing tests for `xingbu` cross-image review with approved identity references, previous accepted images, retries, and explicit human override.
- [ ] Implement production and review transitions, run focused tests, and commit the slice.

### Task 4: Audited Word delivery

**Files:**
- Modify: `src/comic_office/v2/word_canvas.py`
- Create: `src/comic_office/v2/delivery.py`
- Create: `tests/test_comic_v2_delivery.py`
- Modify: `src/web/app.py`

- [ ] Write failing tests that block delivery on missing approved images, stale references, missing prompt cards, or structural audit errors.
- [ ] Build the final package from approved V2 records and generate one asset or shot per readable page.
- [ ] Persist the DOCX artifact and expose a workspace download endpoint.
- [ ] Render a representative DOCX, inspect every page, run focused tests, and commit the slice.

### Task 5: Human-facing workflow and default cutover

**Files:**
- Modify: `src/web/static/js/app.js`
- Modify: `src/web/static/index.html`
- Modify: `src/web/static/css/style.css`
- Modify: `tests/test_frontend_comic_routing.py`

- [ ] Write failing source-level and API-contract tests for immediate loading, visible failures, visual-bible review, concise asset inventory, revision feedback, production progress, and download.
- [ ] Implement context actions against V2 endpoints while keeping detailed prompts collapsed by default.
- [ ] Verify workspace switching clears stale state immediately.
- [ ] Switch “确认故事并开始生成” to V2 only after all downstream actions are reachable; retain a legacy recovery action for existing V1 projects.
- [ ] Run focused frontend tests and commit the slice.

### Task 6: End-to-end verification and publication

**Files:**
- Modify: `scripts/verify_comic_v2_delivery.py`
- Modify: `README.md`

- [ ] Run the deterministic V2 verifier and full unittest suite.
- [ ] Start the local server and complete a browser test as a user: confirm story, review/revise visual bible, review/revise assets, generate, observe review, and download Word.
- [ ] Inspect logs, generated images, and every rendered Word page; record any blocker as a failing regression test before fixing it.
- [ ] Run `git diff --check`, scan tracked files for secrets, commit, and push `codex/comic-quality-overhaul`.
- [ ] Confirm other offices still use isolated model configuration and routes.
