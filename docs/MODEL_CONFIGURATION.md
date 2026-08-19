# 模型配置指南

这份指南回答新用户最容易卡住的几个问题：

- 我到底需要填哪些 API Key？
- 每个部门需要文本模型、视觉模型还是生图模型？
- 只有 DeepSeek、千问、豆包这三类模型时够不够跑？
- 为什么研究办公室和 AI 漫剧制片办公室的模型配置不能混用？

结论先说：公开演示不需要 Key；本地真实使用才需要填自己的 Key。先跑最小可用配置，再补完整制片配置。

> 机器可读版本见 [`docs/MODEL_CAPABILITY_MATRIX.json`](MODEL_CAPABILITY_MATRIX.json)。以后新增办公室或调整部门模型要求时，先改这份矩阵，再同步前端提示、`config.example.yaml` 和验证脚本，避免说明、页面和运行门禁互相打架。

## 三种使用状态

| 状态 | 需要模型吗 | 能做什么 | 适合谁 |
| --- | --- | --- | --- |
| 公开无 Key 演示 | 不需要 | 查看固定样例、下载样例 Word、查看引用清单和安全边界 | 面试官、访客、第一次打开项目的人 |
| 最小可跑配置 | 需要文本模型 | 聊故事、拆结构、规划资产、生成提示词和材料包草案 | 想先验证工作流的人 |
| 完整制片配置 | 需要文本模型、视觉理解模型、生图模型 | 生成基础资产图、做视觉质检、组装 Word 制片画布 | 真正要交付 AI 漫剧制片包的人 |

## 推荐配置顺序

不要一开始就把所有部门填满。按这个顺序来：

1. 先打开首页无 Key 演示，确认样例交付物长什么样。
2. 复制 `config.example.yaml` 为 `config.yaml`。
3. 先给全局 `models` 里的文本部门填一个可用文本模型。
4. 进入模型页面，逐个点击“测试此部门”。
5. 如果要做 AI 漫剧制片，确认 `office_models.comic_production.bingbu` 是文本模型。
6. 再补 `office_models.comic_production.gongbu` 的生图模型。
7. 再补 `office_models.comic_production.xingbu` 的视觉理解模型。
8. 全部通过后再进入工作台跑真实项目。

## 部门能力表

| 部门 | AI 漫剧制片办公室需要什么 | 缺失影响 |
| --- | --- | --- |
| 内阁 | 文本模型 | 无法自然追问、完善故事和锁定创作方向 |
| 中书省 | 文本模型 | 无法生成故事合同、视觉母版和生产任务书 |
| 门下省 | 文本模型 | 无法审核故事、人物、道具、场景是否缺漏 |
| 尚书省 | 文本模型 | 无法协调生产阶段和交接状态 |
| 户部 | 文本模型 | 无法维护资产登记表、资源台账和引用关系 |
| 兵部 | 文本模型 | 无法生成镜头执行卡、动作链和视频提示词 |
| 礼部 | 文本模型 | 无法整理给下游工具的交接说明 |
| 刑部 | 视觉理解模型 | 可以继续生成图片，但无法自动检查人物一致性、画风漂移和交付风险 |
| 工部 | 生图模型 | 可以先完成故事和提示词，但无法生成基础资产图；Word 制片画布会使用已确认文本、提示词包和本地组装链路生成，不需要在工部同一槽位再填一个文本模型 |

研究办公室当前更偏文本和证据整理：中书省、门下省、尚书省、吏部、户部、礼部和兵部先用文本模型跑阶段报告；刑部如果要理解截图，建议使用视觉理解模型；工部不是普通 API Key 槽位，它负责截图证据、平台页面和第三方后台材料的归档入口，真实取证仍依赖登录后的浏览器、人工上传截图或平台导出，不能用文本模型伪装完成。

## 常见模型组合

如果你现在只有 DeepSeek、千问和豆包，可以这样配：

| 位置 | 推荐 |
| --- | --- |
| 全局文本部门 | DeepSeek Chat 或 Qwen 文本模型 |
| AI 漫剧制片办公室兵部 | DeepSeek Chat 或 Qwen 文本模型 |
| AI 漫剧制片办公室刑部 | Qwen VL，例如 `qwen-vl-plus` 或 `qwen-vl-max` |
| AI 漫剧制片办公室工部 | 豆包 Seedream，例如 `doubao-seedream-5` |

如果只有文本模型，也可以先跑到故事、资产拆解和提示词规划阶段；系统会在生图和视觉质检前提醒你补模型。

## Provider 怎么填

页面里的 provider 和模型厂商不是一回事，而是系统底层识别的调用通道。按下面填最稳：

| 你手里的模型/Key | provider 填什么 | 常见模型名 | 适合放在哪 |
| --- | --- | --- | --- |
| DeepSeek API Key | `deepseek` | `deepseek-chat`、`deepseek-reasoner` | 文本部门：中书省、门下省、尚书省、吏部、户部、礼部、兵部 |
| 阿里云百炼/通义千问 API Key | `dashscope` | 文本：`qwen-plus`、`qwen-max`；视觉：`qwen-vl-plus`、`qwen-vl-max` | 文本部门或刑部视觉理解 |
| 火山方舟/豆包 Seedream API Key | `doubao` | `doubao-seedream-5`、`doubao-seedream-4-5` | AI 漫剧制片办公室工部生图 |
| OpenAI API Key | `openai` | `gpt-4.1`、`gpt-5` | 文本部门或刑部视觉理解 |

`千问 VL` 指的是“能看图的千问模型”，不是普通文本千问。它应该放在刑部，用来检查人物一致性、画风漂移、道具错误和场景是否符合故事；如果把 `qwen-plus` 这类文本模型填到刑部，故事和提示词仍可能生成，但图片质检会缺少可靠视觉证据。

`豆包 Seedream` 是生图模型。它应该放在 AI 漫剧制片办公室的工部，用来生成干净人物资产、道具资产、场景广角图和俯视图；它不适合放到兵部，因为兵部要写镜头卡、动作链和视频提示词。

如果你使用的是阿里云百炼控制台，Key 对应这里的 `DASHSCOPE_API_KEY`；如果你使用的是火山方舟控制台，Key 对应这里的 `ARK_API_KEY`。公开展示页、GitHub README 和静态样例都不需要这些 Key。

## 推荐环境变量

推荐把 Key 放进本机环境变量，不要写进 GitHub：

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-key"
$env:DASHSCOPE_API_KEY="your-qwen-key"
$env:ARK_API_KEY="your-doubao-or-volcengine-key"
$env:OPENAI_API_KEY="your-openai-key"
```

`config.example.yaml` 默认使用这些变量：

```yaml
models:
  zhongshu:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}

office_models:
  comic_production:
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

`config.yaml` 已被 `.gitignore` 忽略。不要提交真实 Key、Cookie、浏览器登录态、数据库、日志或输出目录。

## 办公室隔离规则

全局 `models` 是默认配置；`office_models` 是办公室专属覆盖。

例如：

- `models.gongbu` 影响没有单独覆盖的办公室。
- `office_models.comic_production.gongbu` 只影响 AI 漫剧制片办公室的工部。
- 如果以后新增电商选品办公室，它应该使用自己的 `office_models.ecommerce_selection.*`，不能复用 `comic_production.*`。

这条隔离规则很重要：前端可以继续显示“工部、刑部、兵部”，但底层配置必须按办公室 ID 隔离，避免你修改 AI 漫剧制片办公室的生图模型时影响研究办公室或未来办公室。

## 如何知道配置是否正确

优先使用页面上的模型测试按钮：

- 单个部门：点击“测试此部门”。
- 当前办公室：点击“测试当前办公室全部部门”。

也可以使用离线门禁确认文档和配置结构没有漂移：

```powershell
python scripts/verify_model_configuration_guidance.py --format markdown
python scripts/verify_office_isolation.py --format markdown
python scripts/verify_release_readiness.py --format markdown
```

注意：`verify_model_configuration_guidance.py` 不会调用真实模型，不会读取或打印 API Key。它只检查文档、示例配置、前端提示和 preflight 规则是否一致。

## 常见误填

| 误填方式 | 为什么会出问题 | 正确做法 |
| --- | --- | --- |
| 把豆包 Seedream 填到兵部 | 兵部负责镜头、动作链和视频提示词，需要能写文本的模型；Seedream 是生图模型，不能稳定产出镜头卡文本。 | 兵部填 DeepSeek Chat、Qwen 文本模型或 GPT 文本模型。 |
| 把 DeepSeek 填到 AI 漫剧制片办公室工部后期待它生图 | DeepSeek 文本模型可以写提示词，但不能生成基础资产图片；`office_models.comic_production.gongbu` 当前优先作为生图槽位使用。 | 工部填豆包 Seedream、MiniMax Image、Qwen Image 等生图模型；文本规划交给中书省、兵部等文本部门。 |
| 把普通文本模型填到刑部后期待它看图 | 普通文本模型无法读取人物图、道具图和场景图，不能做视觉一致性质检。 | 刑部填 Qwen VL、GPT 多模态、Gemini 多模态等视觉理解模型。 |
| 在研究办公室工部填文本 Key 后期待自动截图 | 工部在研究办公室代表浏览器/人工证据能力，不是普通模型能力；平台截图还受账号、权限和页面状态影响。 | 到工作台上传截图、打开登录窗口或导入平台导出文件；文本模型只辅助整理证据说明。 |
| 把真实 Key 写进 README 或 GitHub | 公开仓库会泄露账号额度和调用权限。 | 使用本机环境变量或被 `.gitignore` 忽略的 `config.yaml`。 |

## 最小可跑与完整制片的区别

最小可跑：

- 文本部门可用。
- 可以聊故事、确认剧本、拆资产、规划提示词。
- 适合验证产品逻辑和人工审核节点。

完整制片：

- 文本部门可用。
- 工部生图模型可用。
- 刑部视觉理解模型可用。
- 可以生成基础资产图、做一致性质检、输出更完整的 Word 制片画布和 handoff manifest。

如果目标是给下游图片/视频平台继续生产，应该追求完整制片配置。
