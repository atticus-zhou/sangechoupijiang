# 三个臭皮匠

三个臭皮匠是一个本地优先的多 Agent 协作工作台。它把复杂任务拆成不同“办公室”，再由一组分工明确的 Agent 协同完成，让用户拿到可审核、可追踪、可下载的交付物，而不是只拿到一段聊天回复。

> 当前状态：早期产品原型。适合本地体验、作品展示和继续二次开发，还不是可以直接托管给陌生用户使用的 SaaS。

## 项目亮点

- 办公室式产品形态：不同业务进入不同办公室，避免一个入口里堆满所有功能。
- 多 Agent 分工：用“三省六部”的协作框架拆分规划、审核、生产、质检和交付。
- 办公室隔离：研究办公室、AI 漫剧制片办公室等场景拥有独立的模型配置、代码链路、产物和历史记录。
- 可交付产物：目标不是生成聊天文本，而是生成报告、截图证据、提示词包、制片画布和 Word 文档。
- 本地优先：配置、历史和生成文件默认留在本机，避免把用户 API Key 或运行产物提交到仓库。

## 现在能做什么

### 研究办公室

面向市场调研、竞品分析、数据证据、截图归档和报告交付。它适合把“我要调研某个产品/行业”拆成资料收集、证据整理、图表建议和老板可读报告。

### AI 漫剧制片办公室

面向 AI 漫剧前期制片包。确认故事后默认进入 V2 制片链：

1. 和主创对话官确认故事方向，或接收完整剧本。
2. 中书省生成故事合同和视觉母版。
3. 用户审核视觉母版，必要时退回修改。
4. 中书省和门下省拆解人物、道具、场景，并用原文证据约束，防止凭空增加资产。
5. 用户审核资产拆解，必要时按意见重拆。
6. 生成专属资产提示词和镜头提示词。
7. 生成基础资产图，并进行跨图一致性质检。
8. 输出页面式 Word 制片画布，交给下游视频生成或剪辑平台使用。

V2 的目标交付不是一部成片，而是一份可生产的制片包：人物图、道具图、场景图、镜头提示词、视频提示词、资产引用链路和 Word 画布。生成 Word 时会同时生成一份 `*_handoff_manifest.json`，用于追踪故事版本、视觉母版、资产 ID、图片记录、镜头引用和 Word 文件之间的对应关系。

生成完成后，历史页可以下载 Word 画布，也可以查看制片追溯：故事版本、风格版本、资产版本、提示词数量、视觉质检结果和交付审计。这样后续修改时能知道这份画布来自哪一版故事、哪一版资产拆解和哪一次图片质检。

## 快速开始

建议第一次下载后先跑本地自检，它不会调用真实模型，也不会打印 API Key：

```powershell
python scripts/doctor.py
```

它会检查 Python、配置文件、数据库、输出目录，显示研究办公室和 AI 漫剧制片办公室的可用状态，并列出 AI 漫剧制片办公室的文本、生图、视觉质检等能力，告诉你下一步该补什么。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.yaml config.yaml
python run.py --port 8080
```

然后打开：

```text
http://127.0.0.1:8080/
```

## 模型配置

复制 `config.example.yaml` 为 `config.yaml` 后，再填写自己的模型服务。推荐用环境变量保存密钥：

```powershell
$env:DEEPSEEK_API_KEY="your-key"
$env:DASHSCOPE_API_KEY="your-key"
$env:ARK_API_KEY="your-key"
```

也可以只在本地 `config.yaml` 里填写。`config.yaml` 已被 `.gitignore` 忽略，不会提交到 GitHub。

打开网页后，模型页面会显示每个部门需要的模型类型、职责、缺失影响和下一步建议。每个部门都有测试按钮，建议先测试通过再进入工作台，避免做到一半才发现某个部门无法调用模型。

工作台也会做启动检查：缺少文本模型时会阻止故事/规划，缺少生图模型时会提示只能先生成提示词，缺少视觉模型时会提示可以生图但不能自动质检。

AI 漫剧制片办公室推荐模型类型：

| 部门 | 推荐能力 | 示例方向 |
| --- | --- | --- |
| 内阁 / 中书省 / 门下省 / 尚书省 / 吏部 / 户部 / 礼部 | 文本规划与结构化输出 | DeepSeek、Qwen、GPT |
| 兵部 | 文本镜头 / 视频提示词 | DeepSeek、Qwen、GPT |
| 刑部 | 图片理解 / 视觉质检 | Qwen VL、GPT 多模态、Gemini 多模态 |
| 工部 | 生图 + 文本组装 | 生图模型加文本模型 |

办公室之间的模型配置按 `office_models` 隔离，例如：

```yaml
office_models:
  comic_production:
    zhongshu:
      provider: deepseek
      model: deepseek-chat
      api_key: ${DEEPSEEK_API_KEY}
    bingbu:
      provider: deepseek
      model: deepseek-chat
      api_key: ${DEEPSEEK_API_KEY}
    gongbu:
      provider: doubao
      model: doubao-seedream-5
      api_key: ${ARK_API_KEY}
    xingbu:
      provider: dashscope
      model: qwen-vl-plus
      api_key: ${DASHSCOPE_API_KEY}
```

## 办公室协议

每个办公室都必须声明自己的产品协议，避免后续新增办公室时变成临时拼出来的半成品入口。协议来源在 `src/offices.py`，也可以通过接口读取：

```text
GET /api/offices/protocols
```

工作空间运行时状态可以通过下面接口读取：

```text
GET /api/workspaces/{workspace_id}/runtime-status
```

它会返回当前阶段、最近任务、产物完成度、缺失产物、人工审核节点和可恢复动作。AI 漫剧制片办公室的工作台会把这部分显示为“当前状态”面板，用来回答三个问题：现在谁在干活、还缺什么、失败后从哪里继续。

协议包含：

- 输入类型：例如灵感、完整剧本、已有角色设定、第三方平台截图或已有资料。
- 输出类型：例如 Word 制片画布、提示词包、资产身份证、阶段调研报告、来源清单和截图计划。
- 模型需求：说明每个部门需要文本模型、视觉模型还是生图模型，以及缺失后会影响哪一步。
- 人工审核节点：说明哪些阶段必须让用户确认，例如故事确认、视觉母版审核、资产拆解审核和交付审核。
- 产物规则：所有关键产物都要有 `artifact_id`，并在 metadata 中保留来源、版本、责任 Agent 和引用链路。
- 失败恢复：每个办公室要声明 `recovery_actions`，让 UI 能告诉用户卡在哪一步、可以重试哪个动作。
- 新办公室模板：接口同时返回 `creation_template`，用于约束后续办公室必须补齐哪些字段和上线门槛。

这个协议是后续扩展新办公室的硬门槛。一个办公室只有同时具备输入、输出、模型需求、人工审核节点、产物规则和验收标准，才应该进入公开演示或真实使用链路。产物写入 SQLite 前会执行运行时校验：缺少 `artifact_id` 会被拒绝，缺少来源、版本、责任 Agent 或引用链路时会按工作区和任务上下文补齐后再保存。

新办公室进入公开展示前，还必须满足 `creation_template.required_launch_gates` 中的上线门槛：`no_key_demo`、`model_preflight`、`end_to_end_test`、`sample_delivery`、`failure_recovery`、`history_trace`、`readme_documentation` 和 `secret_scan`。这条规则的目的不是增加形式，而是确保每个办公室都能被陌生用户试用、被开发者复现、在失败时恢复，并且不会把模型配置或历史产物串到其他办公室。

## 固定验证

不配置任何真实 API Key，也可以运行确定性 V2 交付验证：

```powershell
python scripts/verify_comic_v2_delivery.py
```

这个脚本验证 Word 制片画布的结构、资产 ID、镜头 ID、图片嵌入和交付审计。

还可以运行完整用户式 V2 流程验证：

```powershell
python scripts/verify_comic_v2_user_flow.py
```

这个脚本会通过真实 FastAPI 端点模拟用户链路：确认故事、退回视觉母版、审核资产、退回资产、生成提示词、生成图片、构建 Word、下载交付文件。它使用确定性假模型和占位图片，不消耗真实 API Key。

如果要检查当前真实本地产品是否具备主力办公室的基础上线条件，可以运行：

```powershell
python scripts/verify_product_readiness.py --format markdown
```

这个脚本不会调用模型，只会审计仓库内的证据：完整工作流状态、可下载交付物、模型预检、端到端验证、历史追溯、无 Key 演示入口、办公室协议、产物协议运行时校验、任务失败恢复计划、README 和失败处理策略。

任务失败或后台中断时，任务详情和办公室时间线会展示恢复计划：失败阶段、责任部门、影响、下一步建议，以及可用时的继续处理按钮。

如果要做更深一层的真实产品验收，可以加上运行时验证：

```powershell
python scripts/verify_product_readiness.py --format markdown --run-e2e
```

这会额外跑一遍确定性的 Word 交付链路和模拟用户操作链路，确认流程能到达 `ready_for_handoff`，能生成图片记录，并且能下载 Word 制片画布。它仍然使用假模型和占位图片，不消耗真实 API Key。

仓库保留两套稳定样例：

- `tests/fixtures/comic_v2_sample.json`：AI 漫剧制片办公室样例，可用于验证资产、图片、镜头提示词和 Word 画布。
- `tests/fixtures/research_sample.json`：研究办公室阶段性报告样例，可用于验证报告、来源、截图清单、数据表和竞品表。

启动本地服务后，首页的无 Key 演示入口会加载固定样例，不会读取或消耗真实 API Key。AI 漫剧制片办公室演示提供样例 Word 制片画布和资产引用清单下载；研究办公室演示提供阶段调研报告和来源、数据、截图计划清单下载。

样例项目验证：

```powershell
python -m unittest tests.test_sample_project_fixtures -q
```

运行完整测试：

```powershell
python -m unittest discover -s tests -q
```

## 安全说明

这个仓库不应该包含真实 API Key、登录 Cookie、浏览器 Profile、运行历史和生成文件。

默认忽略：

- `config.yaml`
- `.env`
- `user_data/`
- `output/`
- `*.log`
- `*.db`
- `*.sqlite3`
- `*.docx`

提交或公开仓库前可以运行：

```powershell
python scripts/check_no_secrets.py
```

如果要公开部署，不要把自己的 API Key 暴露给访问者。当前推荐方式是公开页面只开放固定样例演示模式；真实生产继续走本地模式，由使用者填写自己的 Key 后再调用对应供应商模型。

更完整的公开展示、本地真实模式和未来 SaaS 模式边界见 [docs/DEPLOYMENT_MODES.md](docs/DEPLOYMENT_MODES.md)。

## 当前限制

- 这是本地优先原型，长期任务队列、权限、计费、多用户账号体系还没有完整 SaaS 化。
- 自动截图和第三方平台操作依赖本地浏览器状态、账号权限和页面变化。
- AI 漫剧制片包已经能导出结构化 Word 画布，但图片一致性、镜头质量和平台适配仍需要继续打磨。
- 所有 AI 产物都建议人工复核后再交付。

## 项目愿景

三个臭皮匠希望成为一个“办公室式”的 AI 协作平台：用户不需要面对一堆模型参数，而是进入某个办公室，提交目标，和一组有分工的 Agent 一起把事情做完。

## Agent Output Schema Gate

The comic-production V2 pipeline now declares model-output gates in
`src/comic_office/v2/output_schemas.py`. The enforced gates currently include
`comic_contract`, `visual_revision`, `asset_manifest`, and
`asset_manifest_revision`, `asset_prompt_set`, `shot_cards`, and
`image_review_result`;
`src/comic_office/v2/planner.py`, `src/comic_office/v2/asset_planner.py`, and
`src/comic_office/v2/production.py` must validate model JSON through those gates
before the production chain continues.
