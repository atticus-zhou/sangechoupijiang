# 三个臭皮匠产品进化任务清单

> 本文档是后续修改的第一优先级约束。任何新功能、重构、UI 调整、模型接入和办公室扩展，都必须先对照本文档确认是否符合路线、边界和验收标准。

## 长期目标

长期目标：把“三个臭皮匠”做成一个本地优先、可公开演示、可扩展的多 Agent 协作工作台。它不是聊天机器人，也不是单次生成器，而是让用户把一个复杂项目交给“办公室”，由内阁对齐目标，由三省六部拆解、生产、质检、交付，并留下可追溯的过程和文件。

### 后续长目标：从能跑到能交付

后续开发的核心目标不是继续堆办公室、堆按钮或堆模型选项，而是把一个办公室做到真实生产可用，再把这套能力沉淀成平台协议。判断标准只有一个：陌生用户拿到产品后，能不能知道自己要做什么、系统正在做什么、失败后怎么继续，并最终拿到可下载、可复核、可继续生产的交付物。

第一阶段继续以 AI 漫剧制片办公室为主样板。它必须稳定完成从故事对齐、资产拆解、资产审核、提示词生成、图片资产、质检、Word 制片画布到历史追溯的完整链路。所有关键产物都必须有来源、版本、责任 Agent 和引用关系；所有人工退回都必须真实影响下一版结果；所有长任务都必须在工作台给出当前阶段、缺失产物和恢复动作。

第二阶段把 AI 漫剧制片办公室里验证有效的能力抽象成平台底座，包括办公室协议、模型预检、schema gate、artifact contract、runtime status、recovery plan、history trace 和 no-key demo。后续任何新办公室都必须先对齐这些协议，再进入公开展示或真实使用链路。

第三阶段再扩展研究办公室和新办公室。研究办公室的重点不是承诺一键爬取所有第三方平台，而是做到计划、证据、截图、来源、报告和人工协作闭环；新办公室只有在满足“可展示、可试用、可交付、可追溯”四项标准后，才允许成为主力办公室。

阶段性禁令：在 AI 漫剧制片办公室没有稳定达到产品级交付前，不新增大规模办公室；不把无人工确认的模型输出伪装成最终结果；不让不同办公室共享底层模型配置或工作区；不把本地 API Key、Cookie、登录态、运行历史和生成文件带入 Git 或公开部署。

### 后续长目标：从办公室样板到产品网络

长期北极星：三个臭皮匠最终要成为一个“复杂项目生产系统”，不是把每个 Agent 做成聊天框，也不是把多个模型按钮摆在一起。用户进入产品后，应该像进入一个真实办公室一样：先说清目标，再确认方案，然后看到不同部门拆解、生产、质检、归档，最后拿到能继续交给下游工具、同事或客户使用的交付物。

第一里程碑：一个办公室真实可交付。AI 漫剧制片办公室必须先成为标杆样板：用户可以从灵感或完整剧本进入，内阁负责把故事聊清楚，三省六部负责把故事拆成资产、视觉规则、镜头执行卡、提示词包、图片资产和 Word 制片画布。这个阶段不追求“自动生成一部短剧”，而是交付一份足够清楚、可追溯、可复用的制片包。

第二里程碑：办公室协议成为底座。AI 漫剧制片办公室里跑通的能力要沉淀成通用协议，包括模型配置隔离、工作区隔离、schema gate、artifact contract、人工审核节点、失败恢复、历史追溯、无 Key 演示和公开安全边界。后续办公室必须先满足这套协议，才允许进入真实使用链路。

第三里程碑：多办公室组合协作。当单个办公室和底层协议都稳定后，再让不同办公室互相接力。例如研究办公室可以先产出市场证据和用户洞察，AI 漫剧制片办公室再把这些洞察转成内容资产，未来投放办公室再把内容资产转成投放素材和复盘报告。平台最终要做到：先让一个复杂项目被稳定完成，再让多个办公室协同完成更大的项目。

后续长目标的验收标准：任何新功能都必须回答四个问题：它是否让用户更容易开始；它是否让 Agent 分工更清楚；它是否让交付物更接近真实生产；它是否让失败、历史和安全边界更可控。回答不清楚的功能，暂时不做。

### 阶段 A：可信展示

目标：陌生人不配置 API Key，也能在 3 分钟内明白产品价值。

- [x] 个人网站展示产品定位、办公室大厅、主流程截图、样例交付物和 GitHub 链接。
- [x] 在线公开版只开放无 Key 演示模式，不消耗作者额度。
- [x] GitHub README 能让面试官、开发者和普通用户分别看懂怎么体验、怎么运行、怎么扩展。
- [x] 所有公开展示都不暴露 API Key、Cookie、登录态、用户数据和运行产物。

### 阶段 B：单办公室产品级

目标：先把 AI 漫剧制片办公室做到“可以真实交付制片包”，再考虑新办公室。

- [x] 用户可从灵感、完整剧本、已有角色设定、参考风格进入工作流。
- [x] 内阁只负责和人对齐故事，不替三省六部做生产拆解。
- [x] 三省六部必须产出可审核的故事合同、视觉母版、资产清单、镜头执行卡、提示词包和 Word 制片画布。
- [x] 用户能在关键节点确认、修改、退回，退回意见必须真实影响下一版结果。
- [x] 最终 Word 画布能被下游图片/视频工具理解，而不是只适合展示给人看。

说明：阶段 B 产品闭环已纳入 `python scripts/verify_product_readiness.py --format markdown --run-e2e`，运行时会显式审计入口模式、内阁边界、三省六部产物、退回链路和下游交付五项承诺。

### 阶段 C：平台协议化

目标：把 AI 漫剧制片办公室里跑通的能力沉淀成所有办公室都能复用的底座。

- [x] 每个办公室必须有独立的配置、模型、工作区、历史、产物和测试。
- [x] 每个办公室必须声明输入类型、输出类型、Agent 分工、人工审核节点和验收标准。
- [x] 新办公室创建模板必须声明必需协议字段和上线门槛，避免后续办公室复制临时代码入口。
- [x] 每个办公室必须能通过 `/api/offices/{office_id}/launch-gates` 返回上线门禁审计，明确哪些门槛已通过、证据是什么、下一步该补什么。
- [x] 办公室大厅必须展示上线门禁审计摘要，让用户和开发者能直接看出哪些办公室可公开展示、哪些仍需补齐。
- [x] 所有 Agent 关键输出必须有结构化 schema 校验。
- [x] 所有产物必须有 artifact ID、来源、版本、责任 Agent 和引用链路。
- [x] 工作空间运行时状态接口和工作台面板必须能展示当前阶段、产物完成度、缺失产物、人工审核节点和恢复动作。
- [x] 所有长任务必须可观测、可重试、可恢复，并记录失败原因和下一步建议。

说明：办公室协议已集中到 `src/offices.py`，并通过 `/api/offices/protocols` 暴露；协议 API 同时返回 `creation_template`，要求新办公室补齐 `input_types`、`output_types`、`model_requirements`、`human_checkpoints`、`artifact_contract`、`schema_gates`、`recovery_actions` 和验收标准，并通过无 Key 演示、模型预检、端到端测试、样例交付、失败恢复、历史追溯、schema gate、README 文档和 secret scan。`/api/offices/{office_id}/launch-gates` 已返回单个办公室的上线门禁审计，后续办公室如果没有证据、状态和下一步动作，就不能进入公开展示或真实使用链路。工作空间运行时状态通过 `/api/workspaces/{workspace_id}/runtime-status` 暴露，并已接入 AI 漫剧制片办公室工作台，用于统一说明当前阶段、最近任务、产物完成度、缺失产物和恢复动作。长任务事件已覆盖任务开始、任务完成、AI 漫剧图片生产、单张图片进度、Word 画布生成、失败恢复和前端时间线展示，并纳入 `long_task_observability` readiness 条件。artifact 写入 SQLite 前会在 `ConfigManager.create_artifact` 中补齐并校验 `artifact_id`、来源、版本、责任 Agent 和引用链路。AI 漫剧制片办公室已把 `comic_contract`、`asset_manifest`、`asset_prompt_set`、`shot_cards` 和 `image_review_result` 等关键模型输出声明进办公室协议；研究办公室已把 `research_standard_report`、`research_source_list`、`research_data_table` 和 `research_competitor_table` 声明进办公室协议，后续办公室必须沿用同一套 schema gate 方式。

办公室隔离已补充离线验收：`python scripts/verify_office_isolation.py --format markdown` 会在临时目录里验证研究办公室和 AI 漫剧制片办公室的模型配置、工作区、历史、产物和输出目录不会串线，并且历史追踪必须按 `payload.workspace_id` 精确归属。

### 阶段 D：真实使用闭环

目标：用户拿到本地版后，能用自己的模型和自己的资料完成真实项目。

- [x] 模型页明确说明每个部门需要文本模型、视觉理解模型、图片生成模型还是视频/镜头模型。
- [x] 启动预检能告诉用户缺哪个模型、能跑哪些模式、哪些功能暂时不可用。
- [x] 历史页能完整下载 Word、图片、清单、提示词包和追溯记录。
- [x] 项目切换不会串数据，新项目默认清空旧状态。
- [x] 本地真实模式优先稳定，不把尚未可靠的第三方平台自动化包装成“一键全自动”。

### 阶段 E：多办公室扩展

目标：当平台底座稳定后，再扩展新的办公室，而不是堆半成品入口。

- [ ] 研究办公室成为可靠的人机协作调研工具，重点解决报告、数据、截图证据和来源追溯。
- [x] 新办公室必须复用平台协议，而不是复制一套临时代码。
- [x] 每新增一个办公室，都必须同时提供无 Key 演示、模型预检、端到端测试、失败处理和样例交付物。
- [x] `/api/offices/protocols` 已暴露新办公室创建模板，后续办公室扩展必须先对齐这份模板。
- [x] 新办公室扩展治理已补充离线验收：`python scripts/verify_office_extension_governance.py --format markdown` 会检查所有办公室是否复用 `OfficeProfile` 协议，并确认主力办公室必须满足可展示、可试用、可交付、可追溯四项标准。
- [x] 只有当一个办公室达到“可展示、可试用、可交付、可追溯”四项标准后，才允许标记为主力办公室。

## 0. 总原则

- [x] 不再盲目横向增加办公室；先把一个主力办公室打磨到能展示、能试用、能交付。
- [x] 默认主力办公室为 `AI漫剧制片办公室`，研究办公室保持可用但不作为当前主打。
- [x] 所有办公室必须保持代码、模型配置、工作区、历史、产物隔离。
- [x] 用户每次点击关键按钮后，都必须知道系统正在做什么、由哪个 Agent 做、下一步是什么。
- [x] 所有真实模型调用失败都必须可见，不允许静默生成伪正式结果。
- [x] 所有 API Key、Cookie、登录态、运行产物、生成文档和用户数据不得进入 Git。
- [ ] 每次修改都要有最小验证；涉及核心链路时必须跑端到端验证。

## 1. 当前版本固化

目标：把现有可运行状态固定下来，避免后续迭代反复破坏已跑通链路。

- [x] 给当前稳定分支打版本标签，例如 `v0.1-alpha`。
- [x] 保留一套 AI 漫剧制片办公室样例项目。
- [x] 保留一套研究办公室样例项目。
- [x] 确认 README 能说明：项目定位、启动方式、模型配置、演示模式、安全边界。
- [x] 建立“修改前检查”习惯：`git status --short --branch`、确认当前分支、确认无无关脏改。

验收标准：

- [x] 陌生开发者能按 README 在本地启动。
- [x] 没有真实 API Key 的情况下，也能运行确定性验证脚本。
- [x] 当前主分支或开发分支可回退到稳定标签。

## 2. 无 Key 演示模式

目标：面试官、朋友或陌生用户不配置模型也能看懂产品价值。

状态：已形成公开展示包。AI 漫剧制片办公室与研究办公室已接入固定样例无 Key 演示入口；`/api/demo/public-showcase` 已提供 `portfolio_embed` 和 `public_deployment`，供个人网站或 Vercel 页面复用产品定位、办公室大厅说明、主流程截图目标、样例交付物、GitHub 链接和 demo-only 部署边界。

- [x] 首页增加清晰的“演示模式”入口。
- [x] 演示入口包含 `体验AI漫剧制片办公室`。
- [x] 演示入口包含 `体验研究办公室`。
- [x] 演示模式加载固定项目、固定流程状态、固定产物和固定下载文件。
- [x] 演示模式明确提示“不消耗 API Key，不调用真实模型”。
- [x] 演示模式禁止误触真实生产接口。
- [x] AI 漫剧制片办公室演示入口可直接下载样例 Word 制片画布和资产引用清单。
- [x] 研究办公室演示入口可直接下载阶段调研报告和证据清单。
- [x] 演示入口展示交付质量门禁，说明样例为何可公开、可下载、可追溯。
- [x] 演示入口提供“建议你这样看”的参观路径和 proof points，让面试官或陌生用户不用阅读代码也能理解产品价值。
- [x] 提供 `python scripts/verify_public_demo_mode.py --format markdown`，一条命令验证 AI 漫剧制片办公室和研究办公室的无 Key 演示入口、样例下载和门禁证据链接。
- [x] 提供 `/api/demo/public-showcase` 公开展示清单，供个人网站或作品集页复用产品定位、访客参观路径、推荐 demo、下载物和安全边界。

验收标准：

- [x] 用户打开网页后 1 分钟内能看到产品价值。
- [x] 不填写任何 API Key 也能查看 AI 漫剧制片办公室固定样例流程和交付物。
- [x] 不填写任何 API Key 也能查看研究办公室固定样例报告、来源、数据点、竞品和截图计划。
- [x] 演示项目能展示 Agent 分工、人工审核节点和最终交付文件。
- [x] 演示项目能展示无 Key 只读、可下载交付、来源/引用链路等质量门禁。

## 3. 新手启动检查

目标：用户知道自己现在能做什么、不能做什么、为什么不能做。

- [x] 启动后显示系统检查状态。
- [x] 检查 Python 环境、配置文件、数据库、输出目录、模型配置是否可用。
- [x] 模型页面为每个部门展示：部门职责、需要的模型类型、推荐供应商、缺失影响。
- [x] 工作台开始前执行能力预检。
- [x] 缺少文本模型时，提示无法完成故事/规划。
- [x] 缺少生图模型时，提示可以生成提示词但不能生成图片。
- [x] 缺少视觉模型时，提示可以生成图片但不能自动质检。
- [x] 模型测试按钮必须返回明确、可操作的错误说明。

验收标准：

- [x] 用户不会在“点了没反应”的状态里等待。
- [x] 每个阻塞都能定位到办公室、部门、模型或配置项。
- [x] 用户知道下一步该填什么、改什么或跳过什么。

## 4. AI 漫剧制片办公室主力化

目标：把 AI 漫剧制片办公室打磨成产品主样板。

### 4.1 输入入口

- [x] 用户可以选择 `只有灵感`。
- [x] 用户可以选择 `已有完整剧本`。
- [x] 用户可以选择 `已有角色设定`。
- [x] 用户可以选择 `已有参考风格`。
- [x] 完整剧本模式不得随意改写用户故事，只能整理、校验和补充生产信息。
- [x] 灵感模式允许主创对话补全故事，但必须让用户确认故事稿。

### 4.2 主创对话

- [x] 主创对话必须像真实创作助理，不得机械列问题。
- [x] 每轮追问最多聚焦 1-2 个关键问题。
- [x] 主创需要解释为什么问这个问题。
- [x] 主创可以给出 2-3 个方向让用户选择。
- [x] 确认前必须展示完整故事稿，而不是只展示故事承诺或梗概。
- [x] 用户确认后才能进入生产链。

### 4.3 三省六部边界

- [x] 内阁只负责和人对齐故事、方向和创作取舍。
- [x] 中书省负责把确认故事变成生产合同和视觉母版。
- [x] 门下省负责审查故事、资产、镜头和交付是否遗漏或跑偏。
- [x] 尚书省负责调度阶段、记录状态、决定下一步。
- [x] 吏部负责连续性、版本、人物道具场景身份稳定。
- [x] 户部负责结构化资产台账和资源引用。
- [x] 礼部负责交付说明、下游提示、对人可读的整理。
- [x] 兵部负责镜头、动作链、视频提示词和执行计划，不负责生图。
- [x] 刑部负责文本/视觉质检、风险说明和是否需要人工放行。
- [x] 工部负责基础资产图生成和 Word 制片画布组装。

验收标准：

- [x] 用户能理解每一步是谁在做。
- [x] Agent 职责不重叠、不互相抢活。
- [x] 失败信息能体现对应部门。

## 5. 资产拆解与审核

目标：资产必须来自故事，不得凭空 invent。

- [x] 资产拆解只展示人物、道具、场景三类。
- [x] 每个资产必须包含原文证据。
- [x] 每个资产必须说明故事用途。
- [x] 每个资产必须说明出现在哪些场景或镜头。
- [x] 用户可以确认、删除、修改或退回重拆。
- [x] 退回意见必须真实影响下一版拆解，不允许生成和上一版完全相同的包。
- [x] 拆解包默认只展示清单，不把大量提示词堆给用户。
- [x] 提示词生成放在资产确认之后。

验收标准：

- [x] 不出现故事中不存在的人物、道具、场景。
- [x] 不把普通名词误判成人物。
- [x] 用户退回“缺少道具”后，下一版必须补充道具或解释为什么不补。

## 6. 图片资产规范

目标：基础资产为后续一致性服务，而不是每张图都讲故事。

- [x] 人物资产默认白色或近白色干净背景。
- [x] 道具资产默认白色或近白色干净背景。
- [x] 场景资产不得强制白底。
- [x] 人物资产至少规划三视图和表情表。
- [x] 道具资产至少规划多角度图和状态变化图。
- [x] 场景资产至少规划广角图、俯视图、关键机位图。
- [x] 基础资产图不得加入剧情动作、剧情冲突、无关人物或现代元素。
- [x] 资产图必须继承故事风格，例如古风故事不能生成现代风道具。

验收标准：

- [x] 人物、道具资产干净，适合作为参考图。
- [x] 场景资产能辅助空间理解。
- [x] 资产图和故事时代、风格、题材一致。

## 7. 提示词生成规范

目标：提示词由 Agent 根据故事、资产和镜头灵活生成，不能像固定模板。

- [x] 正向提示词必须包含故事风格、资产身份、镜头目的、光影、构图、动作和情绪。
- [x] 负面提示词必须单独放在最后。
- [x] 负面提示词使用 `禁止`，不得使用“不要”。
- [x] 每个资产和镜头都必须有专属提示词。
- [x] 不允许所有提示词只有少量变量替换。
- [x] 提示词必须引用资产 ID 或资产身份，保证下游可追踪。
- [x] 视频提示词需要包含动作链、镜头语言、表演意图、光线和声音提示。

验收标准：

- [x] 提示词读起来像为当前故事定制。
- [x] 提示词可直接交给生图或视频平台继续使用。
- [x] 负面提示词清楚、统一、可读。

## 8. Word 制片画布专业化

目标：最终交付物像可给下游生产团队使用的制片包。

- [x] Word 结构包含封面、项目概览、完整故事、视觉母版、人物资产、道具资产、场景资产、镜头执行卡、下游生产清单。
- [x] 每个资产一页或一组连续页，不使用难读的大表格。
- [x] 每个镜头执行卡必须引用真实资产 ID。
- [x] Word 中必须嵌入已批准图片。
- [x] Word 中必须包含失败重试策略。
- [x] Word 必须通过结构审计。
- [x] 条件允许时，Word 必须渲染成页面图片进行视觉 QA。

验收标准：

- [x] 下游用户能看懂哪个画面对应哪个资产、哪个提示词。
- [x] 没有孤立空页、严重挤压、断裂表格或缺图。
- [x] 交付物能作为作品集展示材料。

## 9. 产品级状态反馈

目标：用户永远知道产品在干什么。

- [x] 工作台显示当前阶段。
- [x] 工作台显示当前 Agent。
- [x] 工作台显示当前对象。
- [x] 工作台显示下一步动作。
- [x] V2 关键动作失败时，前端可以展示后端返回的部门、原因、影响和下一步建议。
- [x] 最近一次 V2 操作失败会固定显示在阶段看板里，不只依赖短暂 toast。
- [x] 提示词、图片、Word 画布关键生产节点失败时，会返回对应部门、影响和下一步建议。
- [x] 视觉母版、资产审核、视觉质检人工放行等审核节点失败时，会返回对应部门、影响和下一步建议。
- [x] 长任务必须有进度或事件记录。
- [x] 图片生成和 Word 画布组装会创建可见任务记录，并写入开始、完成或失败事件。
- [x] 每个失败必须包含原因、影响和可操作建议。
- [x] 切换项目时必须立即清空旧项目状态，避免串项目。
- [x] 历史记录必须能下载完整交付文件。
- [x] 历史详情展示 V2 制片追溯摘要：故事版本、风格版本、资产版本、提示词数量、视觉质检和交付审计。

验收标准：

- [x] 用户不会误以为系统没动静。
- [x] 用户不会看到上一个项目的内容污染新项目。
- [x] 历史里的产物完整可追溯。

## 10. 研究办公室后续方向

目标：研究办公室先成为可靠的人机协作调研工具，不承诺不稳定的一键全自动。

- [x] 明确弱化“一键全自动调研飞瓜”的承诺。
- [x] 支持调研计划生成。
- [x] 支持截图清单生成。
- [x] 支持用户登录第三方平台后辅助截图。
- [x] 支持截图归档、识别和证据表整理。
- [x] 支持报告模板标准化。
- [x] 报告输出包含行业概览、竞品表、价格带、用户痛点、机会判断、风险和建议。

验收标准：

- [x] 即使第三方平台权限不足，也能交付有价值的阶段性结果。
- [x] 截图和证据来源可追溯。
- [x] 报告不是纯 AI 文本，而是包含证据、表格和可复核结论。

## 11. 公开展示与部署

目标：让别人能看懂、能体验，但不暴露作者 API Key。

- [x] 个人网站增加“三个臭皮匠”产品入口。
- [x] 网站展示产品定位、办公室大厅、主流程截图、样例 Word、GitHub 链接。
- [x] 个人网站已提供 AI 漫剧制片办公室样例 Word 画布和资产引用清单下载。
- [x] 个人网站已提供研究办公室样例阶段报告和证据清单下载。
- [x] 在线版优先只开放演示模式。
- [x] 真实使用优先走本地版，让用户填写自己的 API Key。
- [x] 部署文档明确区分演示模式、本地真实模式、未来 SaaS 模式。
- [x] 不在前端、GitHub、Vercel 环境中暴露个人 API Key。

验收标准：

- [x] 面试官可以直接看懂产品。
- [x] 公开页面不会消耗作者模型额度。
- [x] GitHub 仓库不包含敏感信息。

## 12. 后续办公室扩展条件

目标：防止产品再次变成一堆半成品入口。

只有当 AI 漫剧制片办公室满足以下条件后，才允许扩展新办公室：

- [x] 有无 Key 演示模式。
- [x] 有完整工作流状态。
- [x] 有可下载交付物。
- [x] 有模型预检。
- [x] 有端到端测试。
- [x] 有清晰 README。
- [x] 有失败处理策略。

说明：AI 漫剧制片办公室无 Key 演示模式已纳入 `src/product_readiness.py` 审计，并由 `tests/test_comic_production_readiness.py` 与前后端 focused tests 验证。

可考虑的新办公室：

- [ ] 短视频投放办公室。
- [ ] 电商选品办公室。
- [ ] 小说或短剧 IP 办公室。
- [ ] 技术项目办公室。

## 13. 每次开发必须遵循的验证清单

小改动：

- [ ] 查看 `git status --short --branch`。
- [ ] 明确本次改动影响哪个办公室。
- [ ] 跑对应单元测试。
- [ ] 检查是否误改其他办公室模型配置。

核心链路改动：

- [ ] 先写失败测试或补充验证脚本。
- [ ] 跑相关 focused tests。
- [ ] 跑端到端验证脚本。
- [ ] 必要时用浏览器真实点击验证。
- [ ] 检查生成产物。
- [ ] 扫描敏感信息。

交付物改动：

- [ ] 检查 DOCX 结构。
- [ ] 检查图片嵌入数量。
- [ ] 条件允许时渲染页面检查。
- [x] 下载链接必须可用。
  说明：无 Key 演示下载链接已纳入 `/api/offices/{office_id}/launch-gates` 的 `evidence_links`，并在办公室大厅展示；AI 漫剧制片办公室样例 Word 指向 `/api/demo/comic-production/files/word_canvas.docx`，研究办公室阶段报告指向 `/api/demo/research/files/report.md`。

发布前：

- [ ] `python -m unittest discover -s tests -q`
- [ ] `git diff --check`
- [ ] 敏感信息扫描。
- [ ] README 与实际功能一致。
- [ ] 本地分支和远端状态明确。

## 14. 当前最高优先级

按顺序执行：

1. [x] 固定当前稳定版本。
2. [x] 增加启动和模型配置预检。
3. [x] 优化 AI 漫剧主创对话，让它像真实创作助理。
4. [x] 优化资产审核体验，允许删除、修改、退回且退回真实生效。
5. [x] 强化图片资产规范，人物和道具保持干净白底，场景提供空间视图。
6. [x] 继续提升 Word 制片画布审美与下游可用性。
7. [x] 建立 AI 漫剧制片办公室无 Key 演示模式。
8. [x] 将个人网站改成产品展示入口，并接入演示模式。

## Schema Gate Progress

- [x] AI comic-production V2 `comic_contract` output is declared and validated by
  `src/comic_office/v2/output_schemas.py` before production can enter visual
  bible review.
- [x] AI comic-production V2 `visual_revision` output is declared and validated
  through the same schema gate before a new visual bible version can be used.
- [x] AI comic-production V2 `asset_manifest` output is declared and validated
  through the same schema gate before the user can review character, prop, and
  scene inventories.
- [x] AI comic-production V2 `asset_manifest_revision` output is declared and
  validated through the same schema gate before a returned asset list can become
  a new manifest version.
- [x] AI comic-production V2 `asset_prompt_set` output is declared and validated
  through the same schema gate before asset image prompts can enter the prompt
  package.
- [x] AI comic-production V2 `shot_cards` output is declared and validated
  through the same schema gate before shot/video prompts can enter the Word
  canvas and downstream handoff.
- [x] AI comic-production V2 `image_review_result` output is declared and
  validated through the same schema gate before generated images can be promoted
  into approved asset records.
- [x] Office protocols now expose `schema_gates`, and the new-office creation
  template requires future offices to declare their model-output gates before
  public demo or real use.
- [x] Research-office validators now cover the standard report, source list,
  data table, and competitor table gates.
- [x] Research-office artifact packaging now runs those gates, records
  `schema_gate` audit metadata on each governed artifact, and adds a
  `quality_report` when a report package is not delivery-ready.
- [x] Workspace artifact details now render schema-gate status in the UI, so
  users can see whether a delivery artifact passed or needs review.
- [ ] Continue extending concrete schema validators to future office-specific
  outputs.

## Runtime Recovery Progress

- [x] Failed or interrupted task runs expose a structured `recovery_plan` from
  `ConfigManager.get_task_run()`, including failed phase, department, impact,
  next action, and optional retry action.
- [x] `/api/tasks/{task_id}` returns the recovery plan so the frontend and
  history views can explain how a user should continue after a failed run.
- [x] Research and comic task timelines render the recovery plan with failed
  phase, department, next action, and a direct continue button when available.
- [x] AI comic-production V2 image-generation failures include a concrete retry
  action for regenerating and visually reviewing base asset images.
- [x] AI comic-production V2 recovery plans can infer retry actions for visual
  bible planning, asset planning, prompt planning, image generation, visual
  review, and Word canvas generation stages.
- [x] AI comic-production V2 Word canvas failures include a concrete retry
  action for rebuilding the delivery package.
- [x] History delivery summaries expose concrete recovery actions for incomplete
  comic-production V2 handoffs, including Word canvas rebuilds and base-asset
  image regeneration.
- [x] Research-office recovery plans can infer retry actions for Feigua evidence
  capture, screenshot extraction, agent workflow failures, and artifact
  packaging failures.
- [x] Research-office background failures include a concrete recovery action for
  organizing already available research outputs.
- [x] History records expose downloadable archived artifact content and comic V2
  trace JSON, so prompt packages and lineage evidence can be reproduced from
  the history page instead of only from the live workspace.
- [x] Office protocols now declare reusable recovery actions, so future offices
  can expose retry buttons without hard-coding stage maps in task storage.
- [ ] Extend explicit recovery events to future offices as they are added.
