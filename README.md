# 三个臭皮匠

[![Release readiness](https://github.com/atticus-zhou/sangechoupijiang/actions/workflows/release-readiness.yml/badge.svg)](https://github.com/atticus-zhou/sangechoupijiang/actions/workflows/release-readiness.yml)

三个臭皮匠是一个本地优先的多 Agent 协作工作台。它把复杂任务拆成不同“办公室”，再由一组分工明确的 Agent 协同完成，让用户拿到可审查、可追溯、可下载的交付物，而不是只拿到一段聊天回复。

当前状态：早期产品原型，适合本地体验、作品集展示和继续二次开发；还不是可以直接开放给陌生用户使用的 SaaS。

## 现在能看什么

- **公开无 Key 演示**：适合面试官或访客查看固定样例、下载交付物、理解产品边界。它不读取真实 `config.yaml`，不调用真实模型，不暴露 API Key。
- **本地真实使用**：适合你或开发者在自己的机器上配置模型 Key 后运行真实任务。配置和产物默认留在本机。
- **开发者扩展**：适合继续新增办公室。新增办公室必须通过模型隔离、工作区隔离、schema、恢复动作、样例交付和安全扫描。

## 两个主要办公室

### AI 漫剧制片办公室

目标不是直接生成成片，而是生成可以交给视频生成、剪辑或下游制片流程继续使用的制片包：故事、视觉母版、人物/道具/场景资产、提示词包、图片证据、镜头执行说明、Word 制片画布和 `handoff_manifest.json`。

公开样例目前能证明“结构、流程、追溯链路、Word 画布和下载物”是存在的；真实画质、一致性和模型输出质量必须用你自己的模型重新跑，并通过真实生产声明检查后才能对外宣称。

### 研究办公室

目标是把产品/行业调研拆成需求理解、资料收集、证据整理、图表建议、截图计划和报告交付。公开样例目前只声明为 staged demo：它会展示证据缺口、补证清单和人工账号/截图边界，但不会假装已经完成飞瓜会员级全自动采集。

## 第一次运行

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

第一次从 GitHub 下载后，建议先跑这些不调用真实模型的检查：

```powershell
python scripts/doctor.py
python scripts/verify_first_run_readiness.py --format markdown
python scripts/verify_model_configuration_guidance.py --format markdown
python scripts/verify_release_readiness.py --format markdown
python scripts/check_no_secrets.py
```

## 公开展示与部署边界

如果只是放到个人网站或 Vercel 做作品集展示，不要开放真实生产入口，也不要让访客填写或使用你的 API Key。推荐导出静态展示包：

```powershell
python scripts/export_public_showcase.py
python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase
```

输出目录是 `dist/public-showcase/index.html`。如果复制到个人网站的 `public/three-stooges/`，还需要在个人网站仓库运行线上检查。线上 URL 只有在 `npm run check:online` 通过后，才能说已经部署成功。

当前核心文档：

- [docs/FIRST_RUN_DECISION_CARD.md](docs/FIRST_RUN_DECISION_CARD.md)：第一次使用时该选哪条路。
- [docs/MODEL_CONFIGURATION.md](docs/MODEL_CONFIGURATION.md)：每个部门需要什么类型的模型。
- [docs/DEPLOYMENT_MODES.md](docs/DEPLOYMENT_MODES.md)：公开演示、本地真实使用和未来 SaaS 的边界。
- [docs/PUBLIC_RELEASE_HANDOFF.md](docs/PUBLIC_RELEASE_HANDOFF.md)：公开交接和发布检查清单。
- [docs/PRODUCTIZATION_STATUS.md](docs/PRODUCTIZATION_STATUS.md)：当前产品化状态证据表。
- [docs/REAL_PRODUCTION_CLAIMS.md](docs/REAL_PRODUCTION_CLAIMS.md)：什么情况下可以宣称真实生产质量。
- [docs/COMIC_DOWNSTREAM_HANDOFF.md](docs/COMIC_DOWNSTREAM_HANDOFF.md)：AI 漫剧制片包如何交给下游。

## 模型配置原则

- `office_models` 会覆盖全局 `models`。
- 不同办公室的模型配置、工作区、历史和产物必须隔离。
- 文本模型、图片生成模型、视觉理解模型是不同能力，不要混填。
- AI 漫剧制片办公室的完整生产通常需要：文本模型、图片生成模型、视觉理解模型。
- 研究办公室的真实证据采集还需要人工账号、浏览器/截图能力或可追溯来源，不应该只靠文本模型假装完成。

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
      api_key: ${ARK_API_KEY}
    xingbu:
      provider: dashscope
      model: qwen-vl-max
      api_key: ${DASHSCOPE_API_KEY}
```

## 发布前检查

```powershell
python scripts/verify_productization_status.py --format markdown
python scripts/verify_public_docs_readability.py --format markdown
python scripts/verify_model_configuration_guidance.py --format markdown
python scripts/verify_release_readiness.py --format markdown
python scripts/check_no_secrets.py
```

只有这些检查通过，并且线上展示 URL 也通过个人网站的 `npm run check:online`，才能说公开展示链路已经准备好。

---

以下保留的是历史开发记录和旧门禁标记，后续会继续分批清理为正常中文文档。

# 三个臭皮匠

[![Release readiness](https://github.com/atticus-zhou/sangechoupijiang/actions/workflows/release-readiness.yml/badge.svg)](https://github.com/atticus-zhou/sangechoupijiang/actions/workflows/release-readiness.yml)

三个臭皮匠是一个本地优先的多 Agent 协作工作台。它把复杂任务拆成不同“办公室”，再由一组分工明确的 Agent 协同完成，让用户拿到可审核、可追溯、可下载的交付物，而不是只拿到一段聊天回复。

> 当前状态：早期产品原型。适合本地体验、作品展示和继续二次开发，还不是可以直接托管给陌生用户使用的 SaaS。

## 项目亮点

- 办公室式产品形态：不同业务进入不同办公室，避免一个入口里堆满所有功能。
- 多 Agent 分工：用“三省六部”的协作框架拆分规划、审核、生产、质检和交付。
- 办公室隔离：研究办公室、AI 漫剧制片办公室等场景拥有独立的模型配置、工作区、产物和历史记录。
- 可交付产物：目标不是生成聊天文本，而是生成报告、截图证据、提示词包、制片画布和 Word 文档。
- 本地优先：配置、历史和生成文件默认留在本机，避免把用户 API Key 或运行产物提交到仓库。
- 公开发布门禁：GitHub Actions 会运行无 Key release readiness 检查，证明公开展示、样例交付、办公室隔离和敏感信息扫描不依赖作者私有 Key；workflow 会上传 `no-key-release-evidence` artifact，保存 release readiness 和 secret scan 输出，方便访客复核。

## 现在能做什么

### 研究办公室

面向市场调研、竞品分析、数据证据、截图归档和报告交付。它适合把“我要调研某个产品或行业”拆成资料收集、证据整理、图表建议和老板可读报告。

当前公开展示边界是阶段性交付：研究办公室演示提供阶段调研报告、来源、数据、截图计划清单、可执行证据补齐卡和补证操作手册，但不伪装成全自动飞瓜会员级抓取。

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

V2 的目标交付不是一部成片，而是一份可生产的制片包：人物图、道具图、场景图、镜头提示词、视频提示词、资产引用链路和 Word 画布。生成 Word 时会同时生成 `*_handoff_manifest.json`，用于追踪故事版本、视觉母版、资产 ID、图片记录、镜头引用和 Word 文件之间的对应关系。其中 `asset_usage_map` 会进一步说明每个资产的身份基准图、图片角色、引用镜头和下游复用规则，避免下游操作者在一堆图片里猜哪张图该锁脸、哪张图该当首帧、哪个道具出现在哪个镜头。

历史页可以下载 Word 画布，也可以查看制片追溯：故事版本、风格版本、资产版本、提示词数量、视觉质检结果和交付审计。追溯 JSON 还会暴露 `image_production_evidence` 和 `image_quality_summary`，用来区分当前图片证据是固定样例、缺图、部分真实模型，还是已经通过真实模型视觉质检；同时记录可用图、废片/返工图、返工率、失败图片 ID 和 `rework_instructions`。每条返工指令都会说明责任部门、卡在哪个阶段、优先级、给用户看的原因、建议按钮和操作步骤，避免用户只看到一个内部 action 却不知道下一步该做什么。

## 三类读者怎么体验

- 面试官：先看首页的无 Key 演示入口和样例交付物。重点看 AI 漫剧制片办公室如何把故事、资产、提示词、图片记录和 Word 画布连成一份可追溯交付包；这条路径不需要 API Key，也不会调用真实模型。
- 开发者：先跑 `python scripts/verify_first_run_readiness.py --format markdown` 和 `python scripts/doctor.py`，再按 README 配置本地环境。需要扩展新办公室时，先看 `/api/offices/protocols`、上线门禁和隔离验证，不要复制一套临时代码。
- 普通用户：先通过固定样例确认产品能交付什么；真正创作或调研时，再进入本地真实模式，填写自己的 Key 并在本机运行。不要在公开页面、个人网站或 Vercel 展示页上传自己的 API Key、Cookie、登录态、用户数据或运行产物。

如果你是第一次从 GitHub 下载项目，先看 [docs/FIRST_RUN_DECISION_CARD.md](docs/FIRST_RUN_DECISION_CARD.md)。它会用一页把无 Key 展示、本地真实使用和开发者扩展分开，告诉你第一步该点哪里、跑什么命令、哪些文件绝对不能提交。

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
python scripts/verify_github_release_evidence.py --format markdown
```

这些命令会检查 Python、配置文件、数据库、输出目录，显示研究办公室和 AI 漫剧制片办公室的可用状态，并列出 AI 漫剧制片办公室的文本、生图、视觉质检等能力。

如果只想放到个人网站或 Vercel 展示，不需要启动真实 FastAPI 后端。可以导出一个不调用真实模型的静态展示包：

```powershell
python scripts/export_public_showcase.py
python scripts/verify_public_comic_trace_bundle.py --format markdown
python scripts/verify_static_public_showcase.py --format markdown
python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase
python scripts/verify_portfolio_showcase_sync.py --format markdown
```

静态展示包现在会明确展示三条首次使用路径，避免访客把无 Key demo、本地真实生产和开发者扩展混在一起：

- `public_demo`：不需要 API Key，适合个人作品集、面试或公开网页展示；它只使用固定样例交付物，并由 `python scripts/verify_public_demo_mode.py --format markdown` 验证。
- `local_real_use`：使用者填写自己的本地 API Key，配置 `config.yaml`，先在模型页测试每个办公室部门，再在本机运行真实调研或 AI 漫剧制片。
- `developer_extension`：首次审计不需要 API Key；新增办公室前，先看办公室协议、隔离检查和 `python scripts/verify_office_extension_governance.py --format markdown`，确认不会和现有办公室串线。

输出目录是 `dist/public-showcase/index.html`。部署细节见 [docs/STATIC_SHOWCASE_DEPLOYMENT.md](docs/STATIC_SHOWCASE_DEPLOYMENT.md)。
如果你把静态包复制到个人网站 `public/three-stooges/`，再运行 `python scripts/verify_portfolio_showcase_sync.py --format markdown`。它会逐个比对 `dist/public-showcase` 和个人网站拷贝的文件哈希：通过只能说明个人网站仓库里的静态拷贝和产品本体一致，不能说明线上 Vercel 已经刷新；线上仍必须由个人网站仓库的 `npm run check:online` 证明。其他开发者没有我的个人网站目录时，这条检查会显示 `skipped`；复制到自己的作品集目录后，可以用 `--target-dir` 指向自己的 `public/three-stooges`。
如果已经部署到任意公开静态域名，再用产品仓库里的线上检查器复核真实 URL：

```powershell
python scripts/verify_public_showcase_live.py --url https://www.atticus.asia/three-stooges/ --format markdown
```

这条命令会从线上地址读取首页、`showcase.json`、导出清单、访客验收指南、声明报告、样例 Word 和 handoff manifest。它通过时，才能说明这个 URL 本身可打开、可下载，并且仍保持无 Key demo 边界。
静态展示包会同时带上最快验收路线、七份下载物、八个可复核文件、交付物阅读顺序、3 分钟面试演示脚本和复现与验收清单。访客第一次打开时，先按“确认安全公开页 -> 下载 Word 制片画布 -> 核对 handoff manifest -> 核对追溯记录 -> 核对资产图片规格矩阵和资产使用地图 -> 查看声明边界和复现命令”的顺序判断产品价值。其中 `downloads/comic-production/files/trace.json` 会把故事、风格、资产、图片、镜头、证据等级、恢复建议和 `downstream_handoff_decision` 串成一份可复核链路；`data/comic_production_claim_report.json` 会暴露 `claim_upgrade_checklist`、`claim_upgrade_recovery` 和同一张下游接手决策卡：前者说明真实质量还缺什么证据，后者说明如何用 `regenerate_images` 从 demo 结构样例恢复到真实图片和视觉质检证据，决策卡则明确当前状态是 `structure_demo_only`、`ready_for_downstream` 还是 `blocked`，以及现在能不能交给下游。公开页面还会读取 `portfolio_embed.asset_usage_map`，把“每个资产怎么被下游复用”展示成访客可读卡片；同时读取 `portfolio_embed.public_recovery_drill`，把“访客质疑真实画质时如何处理”做成一张恢复演练卡：它必须说明当前证据是 `fixture_only`、恢复动作是 `regenerate_images`、保留故事/资产/提示词/旧 Word、清理图片证据和视觉质检、再由工部和刑部补跑真实模型证据。

`python scripts/verify_public_comic_trace_bundle.py --format markdown` 会单独检查公开追溯包：确认它不需要 API Key、不调用真实模型、不写工作区，且资产、图片、镜头、质量声明、图片证据等级、升级清单和下游接手决策都完整。它已经接入发布总门禁，后续如果 `trace.json` 缺失、泄漏本地路径、把 fixture 图片说成真实画质，或没有明确写出 demo 当前不能交给下游，`python scripts/verify_release_readiness.py --format markdown` 会失败。

静态展示包还会显示办公室公开状态矩阵，避免访客把旧入口和主力入口混在一起：

- `AI 漫剧制片办公室`：当前主推办公室，可以作为对外重点演示和后续真实使用入口。
- `研究办公室`：可公开展示固定样例，但当前不是主推入口。
- `AI 漫剧办公室`：旧版兼容入口，只用于迁移或历史兼容，不建议新用户从这里开始。

命令行也会显示同一结论：`python scripts/verify_public_demo_mode.py --format markdown` 和 `python scripts/verify_static_public_showcase.py --format markdown` 都会输出 `Office launch matrix: public_ready=2/3 / primary=1 / legacy=1`。

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
7. 如果历史追溯显示图片证据仍是 fixture、缺图或未完整质检，不要把它当成真实画质样例；先看 `image_quality_summary` 里的废片/返工数量和 `rework_instructions`。每张问题图都会被归类为“补跑视觉质检”“保留提示词重新生图”或“退回提示词重写”，再按历史页推荐的恢复动作补跑真实图片和视觉质检。

真实项目跑完后，再做三步验收：

```powershell
python scripts/audit_comic_v2_handoffs.py --format markdown
python scripts/verify_comic_real_production_claim.py --manifest output/your_project/xxx_handoff_manifest.json --format markdown
python scripts/verify_comic_v2_production_benchmark.py --manifest output/your_project/xxx_handoff_manifest.json --format markdown
```

只有交付物清点可追溯、真实生产声明显示 `can_claim_real_quality=True`，并且制片质量基准显示 `production_quality_verified` 或等价通过状态时，才把这次产物对外描述为真实生产质量。否则只能说它完成了结构、流程或部分模型验证。

常见首次运行问题可以直接看：

```powershell
python scripts/verify_first_run_readiness.py --format markdown
```

它会把依赖缺失、`config.yaml` 未创建、模型预检失败、8080 端口占用、公开部署误用真实模式等问题列成可执行恢复步骤。若 Codex Windows 桌面端反复弹出 `codex-windows-sandbox-setup.exe` 并提示“找不到指定的模块”，这通常是 Codex 应用沙箱组件或安装状态问题，不是本项目代码报错；先重启、更新或重装 Codex，本地项目仍可用 `python run.py --port 8080` 运行。

模型台阶可以这样理解：

| 阶段 | 需要什么 | 通过后能做什么 |
| --- | --- | --- |
| 公开无 Key 演示 | 不需要模型 | 查看固定样例、下载七份交付物、阅读 quick-start 和安全边界 |
| 最小可跑配置 | 文本部门通过测试 | 聊故事、锁定剧本方向、拆资产、生成镜头和提示词草案 |
| 完整制片配置 | 工部生图模型 + 刑部视觉理解模型通过测试 | 生成基础资产图、执行视觉质检、输出完整 Word 制片画布和 handoff manifest |

### 样例交付物怎么看

- AI 漫剧 Word 制片画布：给人看的主交付物。
- `handoff_manifest.json`：给系统看的引用清单，记录 story、asset、prompt、image、shot 和 Word 的版本关系。
- AI 漫剧真实生产声明报告：说明固定样例能公开证明什么、不能宣称什么，避免把 demo 说成真实画质验证。
- 研究办公室阶段报告：用于展示人机协作调研如何保留证据缺口，而不是假装全自动。
- 研究办公室阶段性交付声明：说明研究办公室可以公开展示 staged delivery，并提供人工登录、截图命名、来源说明、证据补齐卡和补证后重跑报告的操作手册，但不能宣称全自动飞瓜会员级采集。
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
| 工部 | 生图模型，也就是图片生成模型 | 基础资产图生成；Word 制片画布由已确认文本、提示词包和本地组装链路生成 |

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
      api_key: ${ARK_API_KEY}
    xingbu:
      provider: dashscope
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

不想先启动网页时，可以离线导出同一份启动包：

```powershell
python scripts/export_office_creation_template.py --format markdown
python scripts/export_office_creation_template.py --format json --output docs/new-office-template.local.json
```

这条命令不会调用模型、不会读取 API Key、不会写用户工作区；它只导出 `office_profile_skeleton`、`public_demo_contract_skeleton`、上线门禁、最小实现包、候选办公室阻塞原因和必跑验证命令。

同一个接口还会返回 `extension_blueprint`，把新办公室从注册到上线拆成可执行步骤：注册 `OfficeProfile`、隔离运行时状态、建立无 Key demo、接入 schema/recovery、补文档和验证命令。新增办公室时先按这份蓝图走，不要直接复制研究办公室或漫剧办公室的临时代码。完整执行协议见 `docs/OFFICE_EXTENSION_PROTOCOL.md`，启动检查清单见 `docs/NEW_OFFICE_STARTER_CHECKLIST.md`；扩展治理脚本会检查这些文档没有丢失关键边界。

`extension_blueprint` 还会列出未来办公室候选和暂不开放原因。当前候选包括：

- `short_video_ads` / 短视频投放办公室：还缺可复现投放样例、平台数据边界、素材审核规则和失败恢复动作。
- `ecommerce_selection` / 电商选品办公室：还缺真实数据来源边界、证据缺口标注、表格 schema 和可下载样例交付物。
- `story_ip` / 小说或短剧 IP 办公室：还缺版权/素材边界、故事评审 schema、人工确认节点和作品集级样例。
- `technical_project` / 技术项目办公室：还缺代码仓库权限边界、测试证据采集、变更审计和失败恢复协议。

这些候选办公室不能先做 UI 再补底层。进入公开展示前，必须先补 `future_schema_validators` 和 `future_recovery_events` 两类平台证据：每个办公室自己的 schema 校验器、运行状态、任务时间线、历史追溯、恢复接口，以及说明哪些产物会保留、哪些产物会清理的测试。

`python scripts/verify_future_office_backlog.py --format markdown` 会把候选办公室逐个列成阻塞清单，确认它们仍然不能被当作 public ready 或 primary office；只有补齐办公室专属 schema、恢复事件、样例交付、声明边界和发布门禁后，才允许从 backlog 迁入正式办公室矩阵。

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

总发布门禁也会自动运行轻量版开发检查：

```powershell
python scripts/verify_development_checklist.py --format json --skip-release
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

声明报告里的 `real_quality_promotion_gate` 是最终升级门。它会逐项检查制片包结构、manifest 内置质量基准、真实模型图片、视觉质检、图片返工数、导演式提示词、blocker 和 `production_quality_verified`。只要有一项缺失，就只能显示 `evidence_missing`，不能把这次交付说成真实生产质量。

历史页的追溯接口 `/api/tasks/{task_id}/comic-v2-trace.json` 会返回 `image_production_evidence`、`image_quality_summary` 和 `downstream_handoff_decision`。当图片证据显示 `fixture_only`、`missing_images`、`model_partial` 或 `mixed_or_unknown` 时，说明当前制片包只能证明结构或部分流程，不能证明真实画质；此时下游决策通常会保持 `structure_demo_only` 或 `blocked`，`handoff_allowed=false`，不能交给 Libtv、小云雀或其他视频平台当作最终生产素材。`image_quality_summary` 会列出 total/usable/waste-or-rework、返工率、失败图片 ID 和 `rework_instructions`；返工指令会说明某张图应该补跑视觉质检、保留提示词重新生图，还是退回提示词重写。此时可以对 `/api/workspaces/{workspace_id}/comic/v2/quality/recover` 提交 `{"action":"regenerate_images"}`：系统会保留已确认故事、资产拆解、提示词包和旧交付记录，把项目退回图片生成/质检阶段，用真实模型重新补齐图片证据。只有 `downstream_handoff_decision.status=ready_for_downstream` 且 `handoff_allowed=true` 时，才可以把这份制片包描述为可交给下游继续生产。

## 当前边界

可以公开展示：

- 办公室大厅和产品定位。
- 公开静态页的最快验收路线、七份下载物和八个可复核文件。
- AI 漫剧制片办公室固定样例流程。
- 研究办公室固定样例流程。
- 样例 Word 制片画布、handoff manifest、研究样例报告和截图目标说明。
- GitHub README、部署边界、安全说明和 release readiness 结果。
- `dist/public-showcase` 静态展示包。

GitHub 上的 `Release readiness` workflow 会自动运行 `python scripts/verify_release_readiness.py --format markdown` 和 `python scripts/check_no_secrets.py`，并上传 `no-key-release-evidence` artifact。你可以用 `python scripts/verify_github_release_evidence.py --format markdown` 通过 GitHub 公共 API 检查最新 workflow 是否成功、artifact 是否存在；如果公共 API 被限流，脚本会退回读取公开 Actions 页面并明确标注 `github_actions_html_fallback`。也可以补充 `--head-sha <commit>`，让脚本读取公开 commit checks 页面并标注 `github_commit_checks_html_fallback`，证明该提交的 release gate 是否成功；但 artifact 仍会保持未验证状态，不会假装发布证据已经通过。这条 CI 只证明公开 no-key 路径和仓库安全边界，不证明个人网站线上 Vercel 已经刷新；线上仍看个人网站的 `npm run check:online`。

不联网时可以先跑本地契约检查，确认 workflow、README 和公开交接文档仍然指向同一个无 Key 证据规则：

```powershell
python scripts/verify_github_release_evidence.py --format markdown --contract-only
```

不要宣称已经完成：

- 真正多租户 SaaS。
- 陌生用户在线真实调用模型。
- 飞瓜等第三方平台的一键全自动会员级截图采集。
- 新办公室批量上线。

## 当前方向

三个臭皮匠希望成为一个“办公室式”的 AI 协作平台：用户不需要面对一堆模型参数，而是进入某个办公室，提交目标，和一组有分工的 Agent 一起把事情做完。
## Public Showcase Handoff Notes

The public no-key showcase now includes an asset requirement matrix for the AI
comic-production office. Treat this matrix as part of the deliverable contract,
not as page decoration:

- character assets must expose `three_view` and `expression_sheet` requirements;
- prop assets must expose a `turnaround` requirement;
- scene assets must expose `wide` and `top_down` spatial reference requirements;
- character and prop base assets must keep `clean_background_required=true`;
- the same matrix must be visible through `/api/demo/comic-production`,
  `/api/demo/public-showcase`, `dist/public-showcase/showcase.json`, and the
  personal website copy at `public/three-stooges/`.

Before claiming the showcase is ready for a reviewer, run:

```powershell
python scripts/verify_comic_v2_downstream_handoff.py --format markdown
python scripts/verify_public_demo_mode.py --format markdown
python scripts/verify_public_comic_trace_bundle.py --format markdown
python scripts/verify_static_public_showcase.py --format markdown
python scripts/verify_public_showcase_live.py --url https://www.atticus.asia/three-stooges/ --format markdown
python scripts/verify_portfolio_showcase_sync.py --format markdown
python scripts/verify_release_readiness.py --format markdown
```

The production website route is a separate deployment fact. Do not describe
`https://www.atticus.asia/three-stooges/` as live until the personal website
repository passes:

```powershell
npm run check:showcase
npm run check:online
```

If local checks pass but `/three-stooges/` returns 404, the remaining action is
Vercel authorization or redeploy from the personal website repository, not a
change to the product code. Never publish API keys, cookies, `config.yaml`,
`.env`, `user_data/`, `output/`, browser profiles, or real user workspaces into
the static showcase.
