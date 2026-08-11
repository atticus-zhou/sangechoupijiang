# New Office Starter Checklist

This checklist turns a future office idea into a public-demo-ready, locally
reproducible, and isolated product surface. It is mirrored in
`list_office_extension_blueprint()` and audited by
`python scripts/verify_office_extension_governance.py --format markdown`.

Do not promote a new office to the main hall until every item has concrete
evidence.

## Start From The Empty Skeleton

Before copying any existing office implementation, read `/api/offices/protocols`
or call `list_office_creation_template()` and start from:

- Offline command:

  ```powershell
  python scripts/export_office_creation_template.py --format markdown
  python scripts/export_office_creation_template.py --format json --output docs/new-office-template.local.json
  ```

  The command does not call models, read API keys, or write a workspace. It
  exports the same creation template and extension blueprint that the protocol
  API exposes, so a new office can be planned before any route or UI is copied.

- `office_profile_skeleton`: the minimum `OfficeProfile` shape for a new
  office, including office-scoped duties, model requirements, schema gates,
  recovery actions, and the `preserves` / `clears` contract for retries.
- `public_demo_contract_skeleton`: the minimum no-key public demo shape,
  including visitor path, proof points, downloadable deliverables, reading
  guide, interview script, post-run validation, public claim report, and public
  safety boundaries.

The skeleton exists to prevent accidental reuse of another office's
`office_id`, model config, workspace state, history, artifacts, recovery
actions, or public claims. Fill the skeleton first, then implement code.

| Step | Phase | Question | Evidence |
| --- | --- | --- | --- |
| 1 | product | What painful job does this office finish for a human user? | One-paragraph user job, expected input, expected output, and why this should be an office instead of one prompt. |
| 2 | safety | What must this office not claim or not touch? | Public safety boundaries, forbidden claims, and forbidden assets such as API keys, cookies, browser profiles, runtime output, and user data. |
| 3 | isolation | Which model config, workspace, history, artifacts, and output paths are scoped by `office_id`? | Tests proving shared display department names do not share API keys, providers, workspace state, artifacts, or recovery actions. |
| 4 | workflow | Where should the human review or correct the workflow before expensive generation continues? | Named checkpoints, preserved fields, cleared fields, and recovery action per rejected stage. |
| 5 | demo | What downloadable sample proves the office produces more than UI text? | At least one no-key sample deliverable, a manifest or audit file, and a reading guide explaining what each file proves. |
| 6 | quality | How does the office prevent free-form model output from becoming an unverifiable blob? | Schema gates, post-run validation commands, failure states, preserved fields, cleared fields, and retry endpoints. |
| 7 | public_demo | Can a stranger understand and verify the office without an API key? | `viewer_path`, `proof_points`, `downloadable_deliverables`, `deliverable_reading_guide`, `interview_demo_script`, `post_run_validation`, `public_claim_report`, and `public_safety_boundaries`. |
| 8 | release | Which single command proves the office is safe to show or honestly blocked? | Office-specific tests plus `verify_office_isolation`, `verify_public_demo_mode`, `verify_office_extension_governance`, `verify_release_readiness`, and `check_no_secrets`. |

## Promotion Rule

An office can be visible in the public product story only when it has:

- A unique `OfficeProfile`.
- Office-scoped model configuration under `office_models.<office_id>`.
- A no-key demo that calls no real models and writes no user workspace files.
- Downloadable sample deliverables with a reading guide.
- A public claim report that separates allowed claims, forbidden claims, missing evidence, and the recovery path for upgrading a demo claim into a real-run claim.
- Schema or artifact gates for long-running stages.
- Human-readable failure and recovery states.
- History or lineage evidence for the final deliverable.
- Public safety boundaries and forbidden claims.
- Tests and release gates that prove the above.

If an item is missing, keep the office as an internal draft and show a clear
"not ready" reason instead of presenting it as production-ready.
