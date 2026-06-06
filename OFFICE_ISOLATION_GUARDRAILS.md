# Office Isolation Guardrails

This project can show the same department labels in different offices. Examples
include the shared display departments represented by agent keys such as `hubu`,
`gongbu`, `xingbu`, and `bingbu`. Those labels are display names only. Backend
code, configuration namespaces, artifacts, and execution contexts must be scoped
by office.

## First Priority Rule

Every new office must be isolated before feature work continues.

- Office-specific code lives in an office module, for example `src/research_office/`.
- Office-specific model settings live under `office_models.<office_id>.<agent_key>`.
- `models.<agent_key>` is only a global fallback/default template.
- Office UI model pages must pass `office_id` on every model config read and write.
- Office task execution must instantiate the engine with `office_id`.
- Direct calls to `get_model_config` in office-specific paths must include `office_id`.
- Repeated display department names must not imply shared API keys or shared providers.

## Current Research Office Contract

The research office uses:

- Office id: `research`
- Model namespace: `office_models.research`
- Frontend model config constant: `MODEL_OFFICE_ID = 'research'`
- Execution entry: `SanShengLiuBu(office_id='research')`

Changing research office API keys must not change another office's API keys.
Changing a future comic office's `gongbu` key must not change research office
`gongbu`.

## Required Checks Before Adding An Office

Run these checks before and after adding a new office:

```powershell
Select-String -Path src\**\*.py -Pattern 'get_model_config\(|/api/config/models|office_models|office_id=.*model|config\["models"\]|setdefault\("models"'
Select-String -Path src\web\static\js\app.js,src\web\static\index.html -Pattern 'MODEL_OFFICE_ID|/api/config/models|loadModels|updateModel|office_id='
D:\python\python.exe -m unittest discover -s tests
```

The expected result is that office-specific reads and writes use `office_id`,
while global `models` access remains only as a fallback/default path.

## Test Requirement

Each new office should add or update tests proving:

- The same display agent key can have different provider/model/API key per office.
- The task engine passes the correct `office_id` into all agents.
- The frontend/API layer saves office-specific settings into `office_models`.
