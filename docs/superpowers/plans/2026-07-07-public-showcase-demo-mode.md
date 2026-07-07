# Public Showcase And No-Key Demo Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public-facing product showcase and a no-key demo entry so external viewers can understand the AI comic production office without configuring model API keys.

**Architecture:** Keep the real local production chain unchanged. Add a read-only demo API that serves fixed fixture-backed project data, and add a hall-level showcase section that links to the demo without touching model configuration, workspaces, or production endpoints.

**Tech Stack:** FastAPI, static HTML/CSS/vanilla JavaScript, existing `tests/fixtures/comic_v2_sample.json`, Python `unittest`.

---

### Task 1: Public Showcase Entry

**Files:**
- Modify: `src/web/static/index.html`
- Modify: `src/web/static/js/app.js`
- Modify: `src/web/static/css/style.css`
- Test: `tests/test_frontend_comic_routing.py`

- [ ] Add a hall-level showcase block above office cards with product positioning, real/local mode explanation, GitHub-safe API key note, and a no-key demo button.
- [ ] Ensure the page still opens in office hall mode and existing office cards keep their current routes.
- [ ] Add tests that assert the showcase ids, button handler, and no-key copy exist.

### Task 2: Read-Only Demo API

**Files:**
- Modify: `src/web/app.py`
- Test: `tests/test_office_preflight.py` or a new focused web API test

- [ ] Add `GET /api/demo/comic-production` that returns fixed demo metadata from `tests/fixtures/comic_v2_sample.json`.
- [ ] Include stage list, sample project title, source story preview, asset count, shot count, artifact cards, and explicit `mode: "no_key_demo"`.
- [ ] Include `uses_real_models: false`, `writes_workspace: false`, and `api_key_required: false`.
- [ ] Do not call `config_manager.get_model_config`, LLM providers, image providers, or workspace mutation methods.

### Task 3: Demo Page Rendering

**Files:**
- Modify: `src/web/static/index.html`
- Modify: `src/web/static/js/app.js`
- Modify: `src/web/static/css/style.css`
- Test: `tests/test_frontend_comic_routing.py`

- [ ] Add a `page-demo` section that shows the fixed project, production stages, assets, shots, and delivery cards.
- [ ] Add `loadComicDemo()` and route `navigate('demo_comic')`.
- [ ] Render a clear banner: "不消耗 API Key，不调用真实模型".
- [ ] Provide a button back to the office hall and a button to enter the real AI comic production office.

### Task 4: Readiness And Documentation

**Files:**
- Modify: `src/product_readiness.py`
- Modify: `tests/test_comic_production_readiness.py`
- Modify: `README.md`
- Modify: `docs/PRODUCT_EVOLUTION_TASKLIST.md`

- [ ] Add no-key demo evidence to product readiness once the demo API and UI exist.
- [ ] Update README with the difference between demo mode, local real mode, and future SaaS mode.
- [ ] Mark the first demo-mode checklist items complete only if backed by tests.

### Task 5: Verification And Commit

**Commands:**
- `D:\python\python.exe -m unittest tests.test_frontend_comic_routing tests.test_office_preflight tests.test_comic_production_readiness -q`
- `D:\python\python.exe scripts\verify_product_readiness.py --format markdown --run-e2e`
- `D:\python\python.exe scripts\check_no_secrets.py`
- `git diff --check`
- `D:\python\python.exe -m unittest discover -s tests -q`

- [ ] Commit each coherent slice.
- [ ] Push `codex/comic-quality-overhaul`.
