# 三个臭皮匠

三个臭皮匠是一个本地优先的多 Agent 协作工作台。它把复杂任务拆成不同“办公室”，再由多个分工明确的 Agent 协同完成，从需求确认、资料拆解、生成、审核到交付，尽量让用户得到一份可以继续使用的成品材料，而不是只得到一段聊天回复。

> 当前状态：早期产品原型。适合本地体验、作品展示和继续二次开发，还不是可直接托管给陌生用户使用的 SaaS。

## 现在能做什么

- **办公室大厅**：把不同业务能力拆成独立办公室，避免一个入口里堆满所有功能。
- **研究办公室**：面向市场调研、竞品分析、数据证据、截图归档和报告交付。
- **AI 漫剧制片办公室**：从灵感或剧本出发，经过故事共创、资产拆解、提示词预审、人物/道具/场景/分镜生成，最后导出制片画布。
- **模型配置测试**：每个办公室、每个部门可以独立配置模型，并在页面中测试连通性。
- **本地运行数据隔离**：用户配置、历史记录、生成文件默认保存在本地目录，不提交到仓库。

## 产品思路

这个项目不是把一个大模型包装成聊天框，而是把真实工作流程拆给不同角色协作：

1. 用户提出任务或创意。
2. 办公室先确认目标、边界和交付标准。
3. 上游 Agent 负责规划、拆解、审核。
4. 下游 Agent 负责检索、生成、制图、截图或整理材料。
5. 人类在关键节点确认，避免系统一路跑偏。
6. 最终导出报告、制片画布或其他可交付文件。

核心原则是：**办公室之间代码隔离，模型配置隔离，产物隔离，历史隔离。**

## 技术结构

- 后端：FastAPI
- 前端：原生 HTML/CSS/JavaScript 单页应用
- 模型调用：LiteLLM 兼容接口
- 本地存储：SQLite 与本地文件目录
- 文档交付：Word `.docx`
- 运行入口：`run.py`

主要目录：

```text
src/
  web/                 # Web API 与静态页面
  offices.py           # 办公室注册与元数据
  comic_office/        # AI 漫剧制片办公室核心流程
  comic_artifacts.py   # 漫剧制片画布与交付物
tests/                 # 单元测试与接口测试
config.example.yaml    # 配置示例，不包含真实密钥
```

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

如果你已经有指定 Python 路径，也可以直接运行：

```powershell
python run.py --port 8080
```

## 模型配置

复制 `config.example.yaml` 为 `config.yaml` 后，再填写自己的模型服务。

建议使用环境变量保存密钥，例如：

```powershell
$env:DEEPSEEK_API_KEY="your-key"
$env:DASHSCOPE_API_KEY="your-key"
$env:ARK_API_KEY="your-key"
```

也可以直接在本地 `config.yaml` 中配置。注意：`config.yaml` 已经被 `.gitignore` 忽略，不应该提交到 GitHub。

模型配置按办公室隔离，例如：

```yaml
office_models:
  comic_production:
    zhongshu:
      model: deepseek/deepseek-chat
    gongbu:
      model: doubao-seedream-5
    xingbu:
      model: qwen/qwen-vl-plus
```

推荐方向：

- 文本规划、剧本、报告：DeepSeek、Qwen、GPT 等文本模型。
- 图片生成：Seedream、MiniMax Image、Qwen Image 等图像模型。
- 截图理解、画面审核：Qwen VL、GPT 多模态、Gemini 多模态等视觉模型。

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

如果你要公开部署，请不要把自己的 API Key 暴露给访问者。更安全的方式是让使用者填写自己的 Key，或者只提供演示模式。

## 测试

```powershell
python -m unittest discover -s tests -v
```

部分测试会启动本地服务或生成文档，运行时间可能较长。

## 当前限制

- 这是本地优先原型，长期任务、队列、权限、计费和多人账户体系还没有完整 SaaS 化。
- 自动截图和第三方平台操作依赖本地浏览器状态、账号权限和页面变化。
- AI 漫剧制片包已经能导出结构化画布，但生成图片的一致性、镜头质量和提示词审核仍需要继续打磨。
- 所有 AI 产物都建议经过人工复核后再交付。

## 适合谁

- 想研究多 Agent 产品形态的人。
- 想把市场调研、内容生产、AI 漫剧制片拆成可执行流程的人。
- 想基于本地模型配置继续开发私有工作台的人。

## 项目愿景

三个臭皮匠希望成为一个“办公室式”的 AI 协作平台：不是让用户面对一堆模型参数，而是进入某个办公室，提交目标，和一组有分工的 Agent 一起把事情做完。
