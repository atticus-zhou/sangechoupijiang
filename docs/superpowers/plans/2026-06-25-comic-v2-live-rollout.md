# Comic Production V2 Live Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the isolated comic-production V2 contracts into the default, human-reviewable production chain from confirmed story to audited Word canvas.

**Architecture:** Keep V2 logic under `src/comic_office/v2/` and expose narrow FastAPI transition endpoints. Every transition reads server-owned workspace state, writes a versioned artifact and an event, and blocks on explicit human or quality gates. Legacy V1 task and recovery paths remain available for existing projects while new confirmed stories enter V2 by default.

**Tech Stack:** Python 3, FastAPI, LiteLLM, dataclasses, python-docx, unittest, vanilla JavaScript.

---

### Task 1: Online Contract Planner And Visual-Bible Review

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

### Task 2: Evidence-Backed Asset Planning And Human Review

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

### Task 3: Prompt Directing, Image Generation, And Cross-Image Review

**Files:**
- Create: `src/comic_office/v2/production.py`
- Create: `tests/test_comic_v2_production.py`
- Modify: `src/comic_office/v2/pipeline.py`
- Modify: `src/web/app.py`
- Modify: `tests/test_comic_image_pipeline.py`

- [x] Write failing tests proving each asset and shot receives its own model-generated prompt bound to story, style, and asset versions.
- [x] Implement prompt batches using `gongbu`, rejecting malformed model output instead of silently substituting templates.
- [x] Write failing tests proving character and prop images use clean white backgrounds, scenes use spatial views, and generation records image IDs and reference IDs.
- [x] Integrate the existing image provider behind V2 generation records.
- [x] Write failing tests for `xingbu` cross-image review with approved identity references, previous accepted images, retries, and explicit human override.
- [x] Implement production and review transitions, run focused tests, and commit the slice.

### Task 4: Audited Word Delivery

**Files:**
- Modify: `src/comic_office/v2/word_canvas.py`
- Create: `src/comic_office/v2/delivery.py`
- Create: `tests/test_comic_v2_delivery.py`
- Modify: `src/web/app.py`

- [x] Write failing tests that block delivery on missing approved images, stale references, missing prompt cards, or structural audit errors.
- [x] Build the final package from approved V2 records and generate one asset or shot per readable page.
- [x] Persist the DOCX artifact and expose a workspace download endpoint.
- [x] Run focused tests and structural DOCX audit; LibreOffice/`soffice` was unavailable locally, so visual PNG render QA is deferred to a machine with the renderer.

### Task 5: Human-Facing Workflow And Default Cutover

**Files:**
- Modify: `src/web/static/js/app.js`
- Modify: `src/web/static/index.html`
- Modify: `src/web/static/css/style.css`
- Modify: `tests/test_frontend_comic_routing.py`

- [x] Write failing source-level and API-contract tests for immediate loading, visible failures, visual-bible review, concise asset inventory, revision feedback, production progress, and download.
- [x] Implement context actions against V2 endpoints while keeping detailed prompts collapsed by default.
- [x] Verify workspace switching clears stale state immediately.
- [x] Switch the confirmed-story production action to V2 after downstream actions became reachable; retain legacy task and recovery paths for existing V1 projects.
- [x] Run focused frontend tests and commit the slice.

### Task 6: End-To-End Verification And Publication

**Files:**
- Modify: `scripts/verify_comic_v2_delivery.py`
- Modify: `README.md`

- [x] Run the deterministic V2 verifier and full unittest suite.
- [x] Add and run `python scripts/verify_comic_v2_user_flow.py` to verify the user-style API flow: confirmed story, visual-bible revision, visual approval, asset planning, asset revision, asset approval, prompt planning, image generation, delivery build, Word download, and auditable events.
- [x] Start the local server and browser-inspect a retained V2 workspace, verifying the visible `ready_for_handoff` state, delivery audit, embedded-image count, and Word download link.
- [x] Start the local server and complete a browser test as a user: confirm story, review/revise visual bible, review/revise assets, generate, observe review, and download Word.
- [ ] Inspect logs, generated images, and every rendered Word page; record any blocker as a failing regression test before fixing it.
- [ ] Run `git diff --check`, scan tracked files for secrets, commit, and push `codex/comic-quality-overhaul`.
- [x] Confirm other offices still use isolated model configuration and routes through existing tests.
