# 新办公室扩展协议

这份协议用于把“三个臭皮匠”的新办公室从想法推进到可公开展示、可本地复现、可真实交付的状态。后续新增任何办公室，都不能只复制一个页面或接口；必须先证明它不会污染已有办公室的模型配置、工作区、历史、产物和输出目录。

## 1. 先注册 OfficeProfile

新办公室必须先在 `src/offices.py` 注册独立的 `OfficeProfile`，并使用全新的 `office_id`。不要复用 `research`、`comic` 或 `comic_production` 的底层 id。

每个办公室至少声明：

- 输入类型和输出类型。
- Agent 分工和人工审核节点。
- 模型能力要求。
- artifact contract。
- schema gates。
- recovery_actions。
- 验收标准。
- 默认任务模板。

如果这些字段缺失，办公室只能作为草稿，不能进入公开展示或真实使用链路。

## 2. 隔离运行时状态

每个办公室必须按 `office_id` 隔离以下内容：

- 模型配置和 API Key 引用。
- workspace id。
- 历史记录。
- artifact 记录。
- 输出目录。
- 恢复动作和失败状态。

新增办公室时必须运行：

```text
python scripts/verify_office_isolation.py --format markdown
```

这条检查通过之前，不能把新办公室标记为主力办公室。

## 3. 建立无 Key 演示

公开展示必须先有 no-key demo。no-key demo 不能读取用户 API Key，不能调用真实模型，不能写用户工作区，也不能依赖本地浏览器登录态。

演示契约必须包含：

- `viewer_path`：访客先看什么、后看什么。
- `proof_points`：这个演示证明了什么能力。
- `downloadable_deliverables`：可下载、可复核的样例交付物。
- `deliverable_reading_guide`：说明每个交付物怎么看。
- `interview_demo_script`：面试官或作品集访客的 3 分钟演示路线。
- `public_safety_boundaries`：公开模式的安全边界。

只有能下载交付物的演示，才算可展示。只有 UI 截图或空页面不算。

## 4. 接入 schema gate 和恢复动作

每个长任务阶段都必须有结构化验收或产物验收。失败时，用户要知道：

- 哪一步失败了。
- 哪些内容已经保留。
- 哪些内容需要重新生成。
- 点击哪个恢复动作可以继续。

`schema_gates` 用来保护 Agent 输出不要变成散文式文本；`recovery_actions` 用来避免用户在失败后只能重新开始。

## 5. 准备公开上线门禁

新办公室成为公开演示或主力办公室前，必须满足以下门禁：

- `no_key_demo`
- `model_preflight`
- `end_to_end_test`
- `sample_delivery`
- `failure_recovery`
- `history_trace`
- `schema_gate`
- `readme_documentation`
- `secret_scan`

运行：

```text
python scripts/verify_office_extension_governance.py --format markdown
python scripts/verify_public_demo_mode.py --format markdown
python scripts/verify_release_readiness.py --format markdown
python scripts/check_no_secrets.py
```

## 6. 禁止事项

新办公室扩展时禁止：

- 复用其他办公室的 `office_id` 写运行时代码。
- 把 API Key、cookie、`config.yaml`、`user_data`、`output` 或浏览器 profile 放进公开演示资产。
- 在没有样例交付物、历史追踪、schema gate 和失败恢复的情况下标记为主力办公室。
- 只做 UI，不提供可下载、可复核的交付物。

## 7. 最小交付定义

一个新办公室至少要做到：

- 用户知道它解决什么问题。
- 用户能在无 Key 模式看懂一个完整样例。
- 用户能下载样例交付物。
- 开发者能运行验证命令复现结果。
- 失败时用户能看到原因和下一步。
- 公开仓库不包含敏感信息。

达到以上条件后，才可以进入真实模型接入和更复杂的工作流优化。
