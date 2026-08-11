# 首次运行决策卡

这份卡片给第一次从 GitHub 下载“三个臭皮匠”的人看。先判断自己是哪一种使用场景，再进入对应路径，避免把无 Key 展示、本地真实生产和后续开发混在一起。

## 先选一条路

| 你是谁 | 先做什么 | 需要 API Key 吗 | 看到什么才算成功 |
| --- | --- | --- | --- |
| 面试官或访客 | 看无 Key 静态演示和样例交付物 | 不需要 | 能打开首页演示，下载样例 Word、handoff manifest、研究样例和公开安全说明 |
| 本地真实用户 | 在自己电脑上配置模型并启动产品 | 需要自己的 Key | 模型页每个必需部门测试通过，工作台能生成本地 Word、图片、提示词包和历史追溯 |
| 开发者 | 先读办公室协议和隔离规则 | 首次审计不需要 | 新办公室有独立 `office_id`、模型配置、工作区、历史和发布门禁 |

## 如果只是公开展示

公开展示只能使用固定样例，不应该让访客输入真实 API Key。

```powershell
python scripts/export_public_showcase.py
python scripts/verify_static_public_showcase.py --format markdown
python scripts/verify_release_readiness.py --format markdown
python scripts/check_no_secrets.py
```

这一条路径适合个人网站、作品集和面试演示。它证明的是产品结构、样例交付、下载物和安全边界，不证明线上访客可以真实调用你的模型。

## 如果要本地真实使用

本地真实使用让用户填写自己的 Key，并把生成记录留在自己的机器上。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.yaml config.yaml
python scripts/doctor.py --format markdown
python run.py --port 8080
```

打开 `http://127.0.0.1:8080/` 后，先去模型页测试。不要一上来就跑完整制片，先让文本部门通过，再补生图和视觉理解。

## 模型怎么填

| 阶段 | 必需模型 | 能完成什么 |
| --- | --- | --- |
| 无 Key 演示 | 不需要 | 看固定样例、下载交付物、理解产品 |
| 最小可跑 | 文本模型 | 聊故事、确认剧本、拆人物/道具/场景、生成提示词草案 |
| 完整制片 | 文本模型 + 工部生图模型 + 刑部视觉理解模型 | 生成干净资产图、做视觉质检、输出完整 Word 制片画布和 handoff manifest |

AI 漫剧制片办公室里，`工部` 是生图槽位，`刑部` 是视觉理解槽位，`兵部` 是文本镜头和视频提示词槽位。研究办公室与 AI 漫剧制片办公室的底层配置必须按 `office_id` 隔离，不能共用一套运行目录或模型覆盖。

常见 provider 对照：

| Key 来源 | provider | 常见模型 | 放到哪里 |
| --- | --- | --- | --- |
| DeepSeek | `deepseek` | `deepseek-chat` | 文本部门 |
| 阿里云百炼/通义千问 | `dashscope` | `qwen-plus`、`qwen-vl-max` | 文本部门或刑部视觉理解 |
| 火山方舟/豆包 Seedream | `doubao` | `doubao-seedream-5` | 工部生图 |

如果你不确定自己填的是文本、视觉还是生图模型，先在模型页点“测试此部门”。通过测试后再跑真实项目。

## 如果要新增办公室

先不要复制现有办公室硬改。新增办公室前至少跑：

```powershell
python scripts/verify_office_isolation.py --format markdown
python scripts/verify_office_extension_governance.py --format markdown
python scripts/verify_product_readiness.py --format markdown
```

新增办公室必须有自己的 `office_id`、模型能力矩阵、工作区、产物清单、历史记录、公开演示边界和失败恢复说明。

## 不要提交到公开仓库

- 真实 API Key、Cookie、登录态和浏览器 Profile。
- `config.yaml`、`.env`、数据库、日志、`runtime_logs/`。
- 用户真实 `user_data/`、`output/` 和真实运行生成的 Word、图片、截图。
- 任何能让访客直接消耗作者模型额度的前端配置。

公开仓库提交前至少跑：

```powershell
python scripts/check_no_secrets.py
python scripts/verify_first_run_readiness.py --format markdown
python scripts/verify_public_docs_readability.py --format markdown
python scripts/verify_release_readiness.py --format markdown
```
