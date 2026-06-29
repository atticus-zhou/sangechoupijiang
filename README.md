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

V2 的目标交付不是一部成片，而是一份可生产的制片包：人物图、道具图、场景图、镜头提示词、视频提示词、资产引用链路和 Word 画布。

生成完成后，历史页可以下载 Word 画布，也可以查看制片追溯：故事版本、风格版本、资产版本、提示词数量、视觉质检结果和交付审计。这样后续修改时能知道这份画布来自哪一版故事、哪一版资产拆解和哪一次图片质检。

## 快速开始

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
| 兵部 | 生图模型 | Seedream、MiniMax Image、Qwen Image |
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
      provider: doubao
      model: doubao-seedream-5
      api_key: ${ARK_API_KEY}
    xingbu:
      provider: dashscope
      model: qwen-vl-plus
      api_key: ${DASHSCOPE_API_KEY}
```

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

仓库保留两套稳定样例：

- `tests/fixtures/comic_v2_sample.json`：AI 漫剧制片办公室样例，可用于验证资产、图片、镜头提示词和 Word 画布。
- `tests/fixtures/research_sample.json`：研究办公室阶段性报告样例，可用于验证报告、来源、截图清单、数据表和竞品表。

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

如果要公开部署，不要把自己的 API Key 暴露给访问者。更安全的方式是让使用者填写自己的 Key，或者只提供演示模式。真实产品模式下，使用者填写自己的 Key 后才能调用对应供应商模型。

## 当前限制

- 这是本地优先原型，长期任务队列、权限、计费、多用户账号体系还没有完整 SaaS 化。
- 自动截图和第三方平台操作依赖本地浏览器状态、账号权限和页面变化。
- AI 漫剧制片包已经能导出结构化 Word 画布，但图片一致性、镜头质量和平台适配仍需要继续打磨。
- 所有 AI 产物都建议人工复核后再交付。

## 项目愿景

三个臭皮匠希望成为一个“办公室式”的 AI 协作平台：用户不需要面对一堆模型参数，而是进入某个办公室，提交目标，和一组有分工的 Agent 一起把事情做完。
