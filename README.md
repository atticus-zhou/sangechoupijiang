# 三个臭皮匠

三个臭皮匠是一个本地优先的多 Agent 协作工作台。它把复杂任务拆成不同“办公室”，再由一组分工明确的 Agent 协同完成，让用户拿到可审核、可追溯、可下载的交付物，而不是只拿到一段聊天回复。

> 当前状态：早期产品原型。适合本地体验、作品展示和继续二次开发，还不是可以直接托管给陌生用户使用的 SaaS。

## 项目亮点

- 办公室式产品形态：不同业务进入不同办公室，避免一个入口里堆满所有功能。
- 多 Agent 分工：用“三省六部”的协作框架拆分规划、审核、生产、质检和交付。
- 办公室隔离：研究办公室、AI 漫剧制片办公室等场景拥有独立的模型配置、工作区、产物和历史记录。
- 可交付产物：目标不是生成聊天文本，而是生成报告、截图证据、提示词包、制片画布和 Word 文档。
- 本地优先：配置、历史和生成文件默认留在本机，避免把用户 API Key 或运行产物提交到仓库。

## 现在能做什么

### 研究办公室

面向市场调研、竞品分析、数据证据、截图归档和报告交付。它适合把“我要调研某个产品或行业”拆成资料收集、证据整理、图表建议和老板可读报告。

当前公开展示边界是阶段性交付：研究办公室演示提供阶段调研报告、来源、数据、截图计划清单，但不伪装成全自动飞瓜会员级抓取。

### AI 漫剧制片办公室

面向 AI 漫剧前期制片包。确认故事后默认进入 V2 制片链：

1. 和主创对话官确认故事方向，或接收完整剧本。
2. 中书省生成故事合同和视觉母版。
3. 用户审核视觉母版，必要时退回修改。
4. 中书省和门下省拆解人物、道具、场景，并用原文证据约束，防止凭空增加资产。
5. 用户审核资产拆解，必要时按意见重拆。
6. 生成专属资产提示词和镜头提示词。
7. 生成基础资产图，并进行跨图一致性和视觉质检。
8. 输出页面式 Word 制片画布，交给下游视频生成或剪辑平台使用。

V2 的目标交付不是一部成片，而是一份可生产的制片包：人物图、道具图、场景图、镜头提示词、视频提示词、资产引用链路和 Word 画布。生成 Word 时会同时生成 `*_handoff_manifest.json`，用于追踪故事版本、视觉母版、资产 ID、图片记录、镜头引用和 Word 文件之间的对应关系。

历史页可以下载 Word 画布，也可以查看制片追溯：故事版本、风格版本、资产版本、提示词数量、视觉质检结果和交付审计。追溯 JSON 还会暴露 `image_production_evidence` 和 `image_quality_summary`，用来区分当前图片证据是固定样例、缺图、部分真实模型，还是已经通过真实模型视觉质检；同时记录可用图、废片/返工图、返工率、失败图片 ID 和 `rework_instructions`。

## 三类读者怎么体验

- 面试官：先看首页的无 Key 演示入口和样例交付物。重点看 AI 漫剧制片办公室如何把故事、资产、提示词、图片记录和 Word 画布连成一份可追溯交付包；这条路径不需要 API Key，也不会调用真实模型。
- 开发者：先跑 `python scripts/verify_first_run_readiness.py --format markdown` 和 `python scripts/doctor.py`，再按 README 配置本地环境。需要扩展新办公室时，先看 `/api/offices/protocols`、上线门禁和隔离验证，不要复制一套临时代码。
- 普通用户：先通过固定样例确认产品能交付什么；真正创作或调研时，再进入本地真实模式，填写自己的 Key 并在本机运行。不要在公开页面、个人网站或 Vercel 展示页上传自己的 API Key、Cookie、登录态、用户数据或运行产物。

## 快速开始

第一次下载后先跑本地自检，它不会调用真实模型，也不会打印 API Key：

```powershell
python scripts/doctor.py
```

再跑第一次运行清单。它会把公开演示、本地真实使用和开发者扩展三条路径分开说明：

```powershell
python scripts/verify_productization_status.py --format markdown
python scripts/verify_release_readiness.py --format markdown
python scripts/verify_first_run_readiness.py --format markdown
```

这些命令会检查 Python、配置文件、数据库、输出目录，显示研究办公室和 AI 漫剧制片办公室的可用状态，并列出 AI 漫剧制片办公室的文本、生图、视觉质检等能力。

如果只想放到个人网站或 Vercel 展示，不需要启动真实 FastAPI 后端。可以导出一个不调用真实模型的静态展示包：

```powershell
python scripts/export_public_showcase.py
python scripts/verify_static_public_showcase.py --format markdown
```

输出目录是 `dist/public-showcase/index.html`。部署细节见 [docs/STATIC_SHOWCASE_DEPLOYMENT.md](docs/STATIC_SHOWCASE_DEPLOYMENT.md)。
静态展示包会同时带上交付物阅读顺序、3 分钟面试演示脚本和复现与验收清单，访客可以直接看到应该运行哪些 no-key 检查命令，以及每条命令通过后证明什么。

本地真实使用路径：

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

如果第一次运行卡住，先看 `verify_first_run_readiness.py` 输出里的 **Common First-run Failures**。常见问题包括依赖未安装、`config.yaml` 缺失、模型预检失败、8080 端口占用、误把公开演示当成本地真实模式等。

`doctor.py` 还会展示 **Office launch gates（办公室上线门禁）**，说明无 Key 演示、模型预检、端到端测试、样例交付、失败恢复、历史追溯、schema gate、README 文档和 secret scan 是否已经达标。

## 第一次使用应该怎么走

推荐顺序：

1. 先跑无 Key 演示，确认固定样例、流程状态、下载物和公开安全边界。
2. 再进入本地真实模式，复制 `config.example.yaml` 为 `config.yaml`。
3. 在模型页面为每个部门先点测试按钮。
4. 从最小可跑配置开始：先让文本部门通过测试，验证故事、资产拆解、镜头和提示词草案能跑起来。
5. 再补完整制片配置：工部生图模型和刑部视觉理解模型都通过测试后，才开始完整制片。
6. 生成后去历史页下载 Word、图片、清单、提示词包和追溯记录。
7. 如果历史追溯显示图片证据仍是 fixture、缺图或未完整质检，不要把它当成真实画质样例；先看 `image_quality_summary` 里的废片/返工数量和 `rework_instructions`，再用历史页推荐的 `regenerate_images`、重新质检或重写提示词恢复动作补跑真实图片和视觉质检。

常见首次运行问题可以直接看：

```powershell
python scripts/verify_first_run_readiness.py --format markdown
```

它会把依赖缺失、`config.yaml` 未创建、模型预检失败、8080 端口占用、公开部署误用真实模式等问题列成可执行恢复步骤。若 Codex Windows 桌面端反复弹出 `codex-windows-sandbox-setup.exe` 并提示“找不到指定的模块”，这通常是 Codex 应用沙箱组件或安装状态问题，不是本项目代码报错；先重启、更新或重装 Codex，本地项目仍可用 `python run.py --port 8080` 运行。

模型台阶可以这样理解：

| 阶段 | 需要什么 | 通过后能做什么 |
| --- | --- | --- |
| 公开无 Key 演示 | 不需要模型 | 查看固定样例、下载五份交付物、阅读 quick-start 和安全边界 |
| 最小可跑配置 | 文本部门通过测试 | 聊故事、锁定剧本方向、拆资产、生成镜头和提示词草案 |
| 完整制片配置 | 工部生图模型 + 刑部视觉理解模型通过测试 | 生成基础资产图、执行视觉质检、输出完整 Word 制片画布和 handoff manifest |

### 样例交付物怎么看

- AI 漫剧 Word 制片画布：给人看的主交付物。
- `handoff_manifest.json`：给系统看的引用清单，记录 story、asset、prompt、image、shot 和 Word 的版本关系。
- AI 漫剧真实生产声明报告：说明固定样例能公开证明什么、不能宣称什么，避免把 demo 说成真实画质验证。
- 研究办公室阶段报告：用于展示人机协作调研如何保留证据缺口，而不是假装全自动。
- Deliverable reading guide 和下游生产 quick-start：告诉面试官或新开发者应该从哪几份文件理解产品价值，以及 Word 之后如何继续交给视频平台或剪辑流程。

## 模型配置

详细说明见 [docs/MODEL_CONFIGURATION.md](docs/MODEL_CONFIGURATION.md)。

核心原则：

- `office_models` 会覆盖全局 `models`。
- 没配置的部门会继续使用全局 `models` 里的同名部门。
- 不同办公室的模型配置、工作区、历史和产物必须隔离。
- 文本模型、生图模型和视觉理解模型是不同能力，不要混填。

### AI 漫剧制片办公室推荐能力

| 部门 | 需要的能力 | 说明 |
| --- | --- | --- |
| 中书省 | 文本规划 | 故事合同、视觉母版、资产拆解 |
| 门下省 | 文本审核 | 检查故事、资产、镜头和交付是否遗漏或跑偏 |
| 尚书省 | 文本调度 | 阶段调度、状态记录、下一步判断 |
| 吏部 | 文本连续性 | 人物、道具、场景身份稳定 |
| 户部 | 文本结构化 | 资产台账和资源引用 |
| 礼部 | 文本交付 | 面向人的交付说明和阅读指南 |
| 兵部 | 文本镜头 / 视频提示词 | 镜头、动作链、视频提示词和执行计划 |
| 刑部 | 文本质检 + 视觉理解 | 结构质检、视觉质检和风险说明 |
| 工部 | 生图 + 文本组装，也就是图片生成模型加文本模型 | 基础资产图生成、Word 制片画布组装 |

最小示例：

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
      api_key: ${DOUBAO_API_KEY}
    xingbu:
      provider: qwen
      model: qwen-vl-max
      api_key: ${DASHSCOPE_API_KEY}
```

## 办公室协议

办公室协议集中在 `src/offices.py`，并通过 `/api/offices/protocols` 暴露。协议 API 会返回 `creation_template`，新办公室必须补齐：

- 输入类型和输出类型。
- Agent 分工。
- 人工审核节点。
- artifact contract。
- schema gate。
- recovery_actions。
- 验收标准。
- `required_demo_contract`，包括 `viewer_path`、proof points、下载物、阅读指南、`interview_demo_script` 和公开安全边界。

新办公室进入公开展示前，还必须满足 `creation_template.required_launch_gates` 中的上线门槛：`no_key_demo`、`model_preflight`、`end_to_end_test`、`sample_delivery`、`failure_recovery`、`history_trace`、`schema_gate`、`readme_documentation` 和 `secret_scan`。

同一个接口还会返回 `extension_blueprint`，把新办公室从注册到上线拆成可执行步骤：注册 `OfficeProfile`、隔离运行时状态、建立无 Key demo、接入 schema/recovery、补文档和验证命令。新增办公室时先按这份蓝图走，不要直接复制研究办公室或漫剧办公室的临时代码。完整执行协议见 `docs/OFFICE_EXTENSION_PROTOCOL.md`，扩展治理脚本会检查这份文档没有丢失关键边界。

查看单个办公室的上线门禁：

```text
GET /api/offices/{office_id}/launch-gates
```

查看工作空间运行时状态：

```text
GET /api/workspaces/{workspace_id}/runtime-status
```

它会展示当前阶段、最近任务、产物完成度、缺失产物、人工审核节点和恢复动作。

开始真实 AI 漫剧生产前，可以先检查主力办公室是否具备完整生产条件：

```text
GET /api/offices/comic_production/real-production-readiness
```

这个接口会说明当前配置是否达到 `ready_for_real_run`，或只能进入 `limited_planning_only`。

## 公开演示和部署边界

公开展示推荐只开放无 Key 演示模式：

- 不读取 `config.yaml`。
- 不调用真实模型。
- 不写入用户本地工作区。
- 不暴露个人 API Key。
- 不让访客提交真实生产任务。

部署边界见：

- [docs/DEPLOYMENT_MODES.md](docs/DEPLOYMENT_MODES.md)
- [docs/PUBLIC_RELEASE_HANDOFF.md](docs/PUBLIC_RELEASE_HANDOFF.md)
- [docs/PRODUCTIZATION_STATUS.md](docs/PRODUCTIZATION_STATUS.md)
- [docs/REAL_PRODUCTION_CLAIMS.md](docs/REAL_PRODUCTION_CLAIMS.md)

## 验证命令

样例项目验证：

```powershell
python -m unittest tests.test_sample_project_fixtures -q
```

本地全量测试：

```powershell
python -m unittest discover -s tests -q
```

每次开发改动后的统一检查：

```powershell
python scripts/verify_development_checklist.py --format markdown
```

公开交接或大范围重构前，再跑更严格版本：

```powershell
python scripts/verify_development_checklist.py --format markdown --run-tests --require-clean
```

单项发布门禁：

```powershell
python scripts/verify_public_docs_readability.py --format markdown
python scripts/verify_release_readiness.py --format markdown
python scripts/verify_model_configuration_guidance.py --format markdown
python scripts/verify_office_isolation.py --format markdown
python scripts/verify_office_extension_governance.py --format markdown
python scripts/verify_public_demo_mode.py --format markdown
python scripts/verify_research_office_readiness.py --format markdown
python scripts/verify_product_readiness.py --format markdown --run-e2e
python scripts/check_no_secrets.py
```

AI 漫剧交付验证：

```powershell
python scripts/verify_comic_v2_delivery.py --format markdown
python scripts/verify_comic_v2_user_flow.py
python scripts/verify_comic_v2_downstream_handoff.py --format markdown
python scripts/verify_comic_v2_production_benchmark.py --format markdown
python scripts/verify_comic_real_production_claim.py --format markdown
```

## 安全说明

公开仓库不应包含真实 API Key、登录 Cookie、浏览器 Profile、运行历史或生成文件。

默认忽略：

- `config.yaml`
- `.env`
- `user_data/`
- `output/`
- `*.log`
- `*.db`
- `*.sqlite3`
- `*.docx`

提交或公开仓库前务必运行：

```powershell
python scripts/check_no_secrets.py
```

如果要公开部署，不要把自己的 API Key 暴露给访问者。当前推荐方式是公开页面只开放固定样例演示模式；真实生产留在本地模式，让使用者填写自己的 Key 后再调用对应模型。

## 真实生产声明

真实 AI 漫剧跑完后，不要直接把生成包描述为生产级质量。先检查 handoff manifest：

```powershell
python scripts/verify_comic_real_production_claim.py --manifest output/your_project/xxx_handoff_manifest.json --format markdown
```

不带 `--manifest` 时，命令审计固定无 Key 样例，应该返回 `demo_structure_only`。这表示样例可以证明流程、谱系、Word 画布和下游交付结构，但不能宣称真实模型画质已经验证。

历史页的追溯接口 `/api/tasks/{task_id}/comic-v2-trace.json` 会返回 `image_production_evidence` 和 `image_quality_summary`。当它显示 `fixture_only`、`missing_images`、`model_partial` 或 `mixed_or_unknown` 时，说明当前制片包只能证明结构或部分流程，不能证明真实画质。`image_quality_summary` 会列出 total/usable/waste-or-rework、返工率、失败图片 ID 和 `rework_instructions`；返工指令会说明某张图应该补跑视觉质检、保留提示词重新生图，还是退回提示词重写。此时可以对 `/api/workspaces/{workspace_id}/comic/v2/quality/recover` 提交 `{"action":"regenerate_images"}`：系统会保留已确认故事、资产拆解、提示词包和旧交付记录，把项目退回图片生成/质检阶段，用真实模型重新补齐图片证据。

## 当前边界

可以公开展示：

- 办公室大厅和产品定位。
- AI 漫剧制片办公室固定样例流程。
- 研究办公室固定样例流程。
- 样例 Word 制片画布、handoff manifest、研究样例报告和截图目标说明。
- GitHub README、部署边界、安全说明和 release readiness 结果。
- `dist/public-showcase` 静态展示包。

不要宣称已经完成：

- 真正多租户 SaaS。
- 陌生用户在线真实调用模型。
- 飞瓜等第三方平台的一键全自动会员级截图采集。
- 新办公室批量上线。

## 当前方向

三个臭皮匠希望成为一个“办公室式”的 AI 协作平台：用户不需要面对一堆模型参数，而是进入某个办公室，提交目标，和一组有分工的 Agent 一起把事情做完。
