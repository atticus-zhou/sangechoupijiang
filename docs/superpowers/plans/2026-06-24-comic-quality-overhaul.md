# AI Comic Quality Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an isolated V2 comic-production pipeline that preserves the confirmed story, traces every asset to evidence, performs reference-aware visual review, and exports a page-based production canvas.

**Architecture:** New focused modules under `src/comic_office/v2/` own contracts, manifests, prompts, review payloads, and delivery. Existing web routes and V1 workflow remain available; a small adapter opts new comic-production workspaces into V2 without changing other offices.

**Tech Stack:** Python 3, dataclasses, FastAPI, python-docx, unittest, vanilla JavaScript.

---

### Task 1: Creative contract and visual bible

**Files:**
- Create: `src/comic_office/v2/__init__.py`
- Create: `src/comic_office/v2/contracts.py`
- Create: `tests/test_comic_v2_contracts.py`

- [ ] **Step 1: Write failing tests for immutable story and shared versions**

```python
class ComicV2ContractTests(unittest.TestCase):
    def test_contract_preserves_source_story_verbatim(self):
        story = "第一行。\n第二行，包含原始标点。"
        bundle = build_contract_bundle(story, {"title": "测试", "genre": "古风幻想"})
        self.assertEqual(bundle.creative.source_story, story)
        self.assertEqual(bundle.creative.source_hash, story_hash(story))

    def test_visual_bible_and_creative_contract_share_versions(self):
        bundle = build_contract_bundle("完整故事。", {"title": "测试", "genre": "古风幻想"})
        self.assertEqual(bundle.creative.story_version, 1)
        self.assertEqual(bundle.visual.style_version, 1)
        self.assertEqual(bundle.visual.story_id, bundle.creative.story_id)

    def test_invalid_planner_payload_blocks_formal_contract(self):
        with self.assertRaises(ContractValidationError):
            build_contract_bundle("完整故事。", {}, planner_payload={"theme": ""})
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_comic_v2_contracts -v`

Expected: import failure for `src.comic_office.v2.contracts`.

- [ ] **Step 3: Implement typed contracts and deterministic IDs**

`contracts.py` must define frozen dataclasses `CreativeContract`, `VisualBible`, and `ContractBundle`, plus `story_hash()`, `build_contract_bundle()`, `validate_contract_bundle()`, and `to_dict()`. `source_story` is copied exactly. IDs derive from SHA-256 of source text and version; no random ID may change across retries.

- [ ] **Step 4: Run focused and existing workflow tests**

Run: `python -m unittest tests.test_comic_v2_contracts tests.test_comic_office_workflow -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comic_office/v2 tests/test_comic_v2_contracts.py
git commit -m "feat: add comic creative contracts"
```

### Task 2: Evidence-backed asset manifest and revision versions

**Files:**
- Create: `src/comic_office/v2/asset_manifest.py`
- Create: `tests/test_comic_v2_asset_manifest.py`

- [ ] **Step 1: Write failing tests for evidence and revisions**

```python
def test_asset_without_source_evidence_is_rejected(self):
    with self.assertRaises(ManifestValidationError):
        build_asset_manifest(bundle, [{"type": "prop", "name": "不存在的剑", "evidence": ""}])

def test_revision_applies_user_request_and_changes_hash(self):
    first = build_asset_manifest(bundle, valid_assets)
    second = revise_asset_manifest(first, "补充裂纹月灯", [moon_lamp_payload])
    self.assertNotEqual(first.manifest_hash, second.manifest_hash)
    self.assertEqual(second.version, first.version + 1)
    self.assertIn("裂纹月灯", [item.name for item in second.items])

def test_noop_revision_is_rejected(self):
    with self.assertRaises(NoManifestChangeError):
        revise_asset_manifest(first, "重新拆解", valid_assets)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_comic_v2_asset_manifest -v`

Expected: import failure for `asset_manifest`.

- [ ] **Step 3: Implement manifest types and validation**

Define frozen `AssetEvidence`, `AssetPlan`, and `AssetManifest`. Each item stores stable `asset_id`, `asset_type`, `name`, `evidence_quote`, `scene_ids`, `story_purpose`, `visual_locks`, `allowed_changes`, `planned_images`, and `review_status`. Character plans default to `three_view` and `expression_sheet`; prop plans to `turnaround` and `state_sheet`; scene plans to `wide`, `top_down`, and `camera_angles`.

- [ ] **Step 4: Verify focused tests**

Run: `python -m unittest tests.test_comic_v2_asset_manifest tests.test_comic_v2_contracts -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comic_office/v2/asset_manifest.py tests/test_comic_v2_asset_manifest.py
git commit -m "feat: add evidence backed comic assets"
```

### Task 3: Prompt director and executable shot cards

**Files:**
- Create: `src/comic_office/v2/prompt_director.py`
- Create: `tests/test_comic_v2_prompt_director.py`

- [ ] **Step 1: Write failing tests for base assets and shots**

```python
def test_base_asset_prompt_has_no_story_action(self):
    plan = build_asset_prompt_plan(character, visual_bible)
    self.assertEqual(plan.purpose, "identity_reference")
    self.assertIn("纯白或近白色干净背景", plan.generator_prompt)
    self.assertNotIn("冲向", plan.generator_prompt)

def test_shot_card_references_approved_assets(self):
    shot = build_shot_card(scene, [character], [prop], visual_bible)
    self.assertEqual(shot.reference_asset_ids, (character.asset_id, prop.asset_id, scene.asset_id))
    self.assertTrue(shot.action_chain)
    self.assertTrue(shot.retry_strategy)

def test_prompt_failure_has_no_silent_rule_fallback(self):
    result = parse_prompt_director_response("not-json")
    self.assertEqual(result.status, "prompt_failed")
    self.assertFalse(result.production_ready)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_comic_v2_prompt_director -v`

Expected: import failure for `prompt_director`.

- [ ] **Step 3: Implement prompt plans and shot cards**

Define `PromptPlan`, `GeneratorPrompt`, `ShotCard`, and `PromptDirectorResult`. Negative prompts are stored separately and rendered at the end using `禁止`. Prompt parsing must return an explicit blocked result on malformed model output.

- [ ] **Step 4: Verify focused tests**

Run: `python -m unittest tests.test_comic_v2_prompt_director tests.test_comic_v2_asset_manifest -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comic_office/v2/prompt_director.py tests/test_comic_v2_prompt_director.py
git commit -m "feat: add comic prompt director"
```

### Task 4: Reference-aware visual review

**Files:**
- Create: `src/comic_office/v2/visual_review.py`
- Create: `tests/test_comic_v2_visual_review.py`

- [ ] **Step 1: Write failing tests for review claims**

```python
def test_review_without_reference_cannot_claim_consistency(self):
    request = build_visual_review_request(current_image="current.png", reference_images=[])
    result = normalize_visual_review({"status": "pass", "identity_consistency": 95}, request)
    self.assertEqual(result.consistency_status, "not_evaluated")
    self.assertFalse(result.handoff_ready)

def test_low_identity_score_blocks_handoff(self):
    request = build_visual_review_request("current.png", ["char-approved.png"])
    result = normalize_visual_review(valid_payload(identity_consistency=62), request)
    self.assertEqual(result.status, "fail")
    self.assertFalse(result.handoff_ready)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_comic_v2_visual_review -v`

Expected: import failure for `visual_review`.

- [ ] **Step 3: Implement multidimensional review**

Review dimensions are `identity_consistency`, `style_consistency`, `era_media`, `spatial_structure`, `asset_purity`, `anatomy`, and `purpose_fit`. The request carries current image, approved identity images, previous accepted image, visual-bible summary, and acceptance criteria. Handoff requires every applicable dimension to meet 80 and at least one reference for consistency claims.

- [ ] **Step 4: Verify focused tests**

Run: `python -m unittest tests.test_comic_v2_visual_review tests.test_comic_quality -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/comic_office/v2/visual_review.py tests/test_comic_v2_visual_review.py
git commit -m "feat: add reference aware visual review"
```

### Task 5: Page-based Word production canvas

**Files:**
- Create: `src/comic_office/v2/word_canvas.py`
- Create: `tests/test_comic_v2_word_canvas.py`

- [ ] **Step 1: Write failing structural tests**

```python
def test_canvas_uses_page_sections_not_nine_column_table(self):
    path = build_word_canvas_v2(package, images, tmp_path)
    doc = Document(path)
    self.assertFalse(any(len(table.columns) >= 9 for table in doc.tables))
    self.assertIn("视觉母版", all_text(doc))
    self.assertIn("SHOT-01", all_text(doc))

def test_each_asset_and_shot_has_a_dedicated_heading(self):
    path = build_word_canvas_v2(package, images, tmp_path)
    headings = heading_texts(Document(path))
    self.assertIn("CHAR-01", "\n".join(headings))
    self.assertIn("SHOT-01", "\n".join(headings))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_comic_v2_word_canvas -v`

Expected: import failure for `word_canvas`.

- [ ] **Step 3: Implement page-based builder**

Build portrait pages with reusable helpers for cover, story, visual bible, asset identity page, continuity page, shot card, and handoff checklist. Use explicit table widths no larger than two columns, Microsoft YaHei, restrained indigo/silver/vermilion palette, page numbers, and image captions. Return a `DocumentAudit` containing image count, shot count, missing references, and structural errors.

- [ ] **Step 4: Verify focused tests**

Run: `python -m unittest tests.test_comic_v2_word_canvas -v`

Expected: all pass and generated DOCX reopens with python-docx.

- [ ] **Step 5: Commit**

```powershell
git add src/comic_office/v2/word_canvas.py tests/test_comic_v2_word_canvas.py
git commit -m "feat: add page based comic canvas"
```

### Task 6: V2 orchestration adapter and honest UI state

**Files:**
- Create: `src/comic_office/v2/pipeline.py`
- Modify: `src/web/app.py`
- Modify: `src/web/static/js/app.js`
- Create: `tests/test_comic_v2_pipeline.py`
- Modify: `tests/test_web_comic_api.py`
- Modify: `tests/test_frontend_comic_routing.py`

- [ ] **Step 1: Write failing integration tests**

```python
def test_v2_pipeline_blocks_between_human_checkpoints(self):
    state = ComicProductionV2.start(confirmed_story, planner_payload)
    self.assertEqual(state.stage, "visual_bible_review")
    self.assertFalse(state.can_generate_images)

def test_story_change_invalidates_assets_and_shots(self):
    state = completed_state()
    changed = state.replace_story("修改后的完整故事")
    self.assertEqual(changed.assets_status, "stale")
    self.assertEqual(changed.shots_status, "stale")

def test_api_exposes_current_object_and_next_action(self):
    response = client.get(f"/api/workspaces/{workspace_id}/comic/v2/status")
    self.assertIn("current_object", response.json())
    self.assertIn("next_action", response.json())
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest tests.test_comic_v2_pipeline tests.test_web_comic_api tests.test_frontend_comic_routing -v`

Expected: missing pipeline and endpoint failures.

- [ ] **Step 3: Implement V2 state machine and adapter**

Stages are `story_confirmed`, `visual_bible_review`, `asset_review`, `prompt_review`, `image_generation`, `visual_review`, `document_generation`, `ready_for_handoff`, and explicit failure states. API responses always include stage, current Agent, current object, completed/total, blocking reason, and next action. Only `office_id=comic_production` can opt into V2.

- [ ] **Step 4: Add minimal frontend state rendering**

Use the existing stage board. Do not redesign the page. Render the V2 stage label, current object, progress, blocking reason, and one context-appropriate action. A click immediately enters loading state and then refreshes status without requiring project switching.

- [ ] **Step 5: Run integration and full regression tests**

Run: `python -m unittest tests.test_comic_v2_contracts tests.test_comic_v2_asset_manifest tests.test_comic_v2_prompt_director tests.test_comic_v2_visual_review tests.test_comic_v2_word_canvas tests.test_comic_v2_pipeline tests.test_comic_office_workflow tests.test_comic_image_pipeline tests.test_comic_production_chain tests.test_frontend_comic_routing tests.test_web_comic_api -v`

Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add src/comic_office/v2 src/web/app.py src/web/static/js/app.js tests
git commit -m "feat: integrate comic production v2"
```

### Task 7: End-to-end sample and delivery verification

**Files:**
- Create: `tests/fixtures/comic_v2_sample.json`
- Create: `scripts/verify_comic_v2_delivery.py`
- Modify: `README.md`

- [ ] **Step 1: Add a fixed ancient-fantasy sample**

The fixture contains a complete story, visual bible planner payload, evidence-backed assets, one approved reference image path per required asset, and two shot cards. It must not contain API keys or generated binary files.

- [ ] **Step 2: Add deterministic delivery verification**

The script builds the V2 package and DOCX, reopens it, verifies all asset and shot IDs, counts embedded images, rejects nine-column tables, and exits nonzero on missing references.

- [ ] **Step 3: Run full verification**

Run: `python scripts/verify_comic_v2_delivery.py`

Expected: `V2 delivery verified` and exit 0.

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 4: Commit**

```powershell
git add tests/fixtures/comic_v2_sample.json scripts/verify_comic_v2_delivery.py README.md
git commit -m "docs: verify comic production v2"
```
