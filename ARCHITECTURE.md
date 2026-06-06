# 三省六部 · 多 Agent 协作平台 — 架构文档

> 版本: v2.0 | 日期: 2026-05-08 | 形态: Web 应用平台

---

## 目录

1. [产品定位](#1-产品定位)
2. [系统架构总览](#2-系统架构总览)
3. [三省六部流程引擎](#3-三省六部流程引擎)
4. [多模型适配层 (LiteLLM)](#4-多模型适配层-litellm)
5. [用户配置系统](#5-用户配置系统)
6. [Web 界面](#6-web-界面)
7. [快速开始](#7-快速开始)
8. [项目结构](#8-项目结构)

---

## 1. 产品定位

**三省六部**是一个**可分发、可配置、开箱即用**的多 Agent 协作平台。

```
用户下载 → 配置自己的模型 API → 放入自己的提示词/模板 → 直接使用
                                          ↓
                          三省六部提供: 流程引擎 + 工具机制 + Web UI
                          用户提供: 提示词 + 案例模板 + 模型选择
```

### 核心特性

| 特性 | 说明 |
|------|------|
| 多模型支持 | LiteLLM 适配, Claude / GPT / Ollama / Gemini / DeepSeek 等 |
| 多模态支持 | 支持图片/视频输入的模型可处理视觉任务 |
| Web 界面 | FastAPI 后端 + 单页前端, 浏览器打开即用 |
| 提示词可配 | 每个部门的 System Prompt 都可在 Web UI 中编辑 |
| 模板系统 | 用户可创建/管理任务模板, 一键复用 |
| 三省六部流程 | 中书省(起草) → 门下省(审议) → 尚书省(LLM调度) → 六部执行 |
| 朝堂报告 | 人类可随时打断, 查看完整进度和最新文件 |
| 零框架依赖 | 流程引擎手写状态机, 不绑定 LangChain 等框架 |

---

## 2. 系统架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                      浏览器 (Web UI)                          │
│   📜 奏事  │  🏛️ 朝堂  │  📋 历史  │  ⚙️ 配置  │  💬 提示词  │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP + WebSocket
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI 后端 (src/web/)                    │
│  /api/tasks (CRUD)  /api/config (模型/提示词/模板)  /ws/*    │
└──────────────────────────┬───────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌────────────┐ ┌────────────┐ ┌──────────────┐
     │ 配置管理器  │ │ 三省六部   │ │ LLM 适配层   │
     │ConfigManager│ │ 流程引擎    │ │ (LiteLLM)    │
     │            │ │            │ │              │
     │ YAML+SQLite│ │ StateMachine│ │ Claude/GPT/  │
     │ 提示词/模板 │ │ MessageBus │ │ Ollama/Gemini│
     └────────────┘ └─────┬──────┘ └──────────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │  中书省    │ │  门下省    │ │  尚书省    │
     │  Planner   │ │  Reviewer  │ │Orchestrator│
     │  起草方案  │ │  审议方案  │ │  LLM调度   │
     └────────────┘ └────────────┘ └──┬──┬──┬──┘
                                      │  │  │
                              ┌───────┘  │  └───────┐
                              ▼          ▼          ▼
                         ┌────────┐ ┌────────┐ ┌────────┐
                         │  吏部  │ │  兵部  │ │  刑部  │
                         │Context │ │ Exec   │ │ Test   │
                         └───┬────┘ └────────┘ └────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   共享向量库     │
                    │   (ChromaDB)    │
                    └─────────────────┘
```

---

## 3. 三省六部流程引擎

### 3.1 三省 (核心决策链)

| 部门 | Agent 角色 | 职责 | 输出 |
|------|-----------|------|------|
| 中书省 | Planner | 理解需求、拆解任务、起草方案 | TaskPlan |
| 门下省 | Reviewer | 审查可行性/完备性/风险, 批准或驳回 | ReviewResult |
| 尚书省 | Orchestrator | LLM 动态调度, 每步决定下一步做什么 | OrchestratorDecision |

### 3.2 流程控制

- **中书-门下循环**: 最多 5 轮, 超限自动升堂请人类裁决
- **尚书省否决权**: 执行中发现不可行, 可打回中书省或升堂
- **兵部-刑部串行**: 兵部执行步骤N → 刑部验证步骤N → 通过才进入N+1
- **人类任意打断**: 输出朝堂报告 (上一流程/当前阶段/最新文件全文/待决议题)

### 3.3 状态机 (15 状态)

```
RECEIVED → PLANNING ⇄ REVIEWING → APPROVED → DISPATCHING ⇄ EXECUTING/TESTING
                                                  ↓
                                            FINALIZING → DELIVERING → COMPLETED
                                                  ↓
                                     SHANGSHU_VETO / HUMAN_CALLED / ERROR_HANDLING
```

---

## 4. 多模型适配层 (LiteLLM)

### 4.1 设计

每个部门独立配置 LLM, 通过 LiteLLM 统一调用:

```yaml
# config.yaml
models:
  zhongshu:
    provider: anthropic     # 起草需要最强推理
    model: claude-sonnet-4-6
    api_key: ${ANTHROPIC_API_KEY}
  bingbu:
    provider: openai        # 执行可用 GPT-4o
    model: gpt-4o
    api_key: ${OPENAI_API_KEY}
  xingbu:
    provider: ollama        # 测试可用本地模型省钱
    model: llama3.1
    api_base: http://localhost:11434
  libu:
    provider: deepseek      # 上下文检索可用便宜的
    model: deepseek-chat
```

### 4.2 支持的 Provider

| Provider | 模型示例 | 多模态 |
|----------|---------|--------|
| anthropic | Claude Opus/Sonnet/Haiku | ✅ 图片 |
| openai | GPT-4o, GPT-4.1 | ✅ 图片/视频 |
| ollama | Llama 3.1, Qwen 等 | 取决于模型 |
| gemini | Gemini 2.0/2.5 | ✅ 图片/视频 |
| deepseek | DeepSeek V3/R1 | ❌ |

### 4.3 多模态调用

```python
# 支持图片/视频输入的模型可自动处理视觉任务
agent.call_llm_with_vision(
    text="分析这张报错截图",
    images=["base64_encoded_image..."],
)
```

---

## 5. 用户配置系统

### 5.1 配置层级

```
config.yaml              ← 默认配置 (模型、模板、系统参数)
user_data/
  prompts/               ← 用户自定义 System Prompt (按部门, .txt)
    zhongshu.txt          # 中书省的提示词
    bingbu.txt            # 兵部的提示词
    ...
  templates/             ← 用户自定义任务模板 (.yaml)
    bug_fix.yaml
    code_review.yaml
  tools/                 ← 自定义工具定义 (.yaml)
    custom_tools.yaml
  config.db              ← SQLite (Web UI 编辑持久化 + 任务历史)
```

### 5.2 提示词变量

用户可在 System Prompt 中使用变量:
- `{task_id}` — 当前任务 ID
- `{user_request}` — 用户原始需求
- `{context}` — 吏部检索的上下文

---

## 6. Web 界面

### 6.1 页面功能

| 页面 | 路径 | 功能 |
|------|------|------|
| 奏事 | `/#task` | 输入需求 + 选择模板, 提交任务 |
| 朝堂 | `/#court` | 实时监控三省六部协作过程, 查看朝堂报告 |
| 奏折 | `/#history` | 查看历史任务记录 |
| 模型配置 | `/#config-models` | 每个部门独立配置 LLM provider/model/api_key |
| 提示词配置 | `/#config-prompts` | 在线编辑每个部门的 System Prompt |
| 模板管理 | `/#config-templates` | 创建/管理任务模板 |

### 6.2 WebSocket 实时推送

- `/ws/tasks/{task_id}` — 订阅任务实时进度
- `/ws/court` — 朝堂事件全局广播

### 6.3 REST API

- `POST /api/tasks` — 创建并启动任务
- `GET /api/tasks/{id}/report` — 获取朝堂报告
- `GET/PUT /api/config/models` — 模型配置 CRUD
- `GET/PUT /api/prompts/{agent}` — 提示词 CRUD
- `GET/POST /api/templates` — 模板 CRUD

---

## 7. 快速开始

### 7.1 安装

```bash
cd E:\trae\cc
pip install -r requirements.txt
```

### 7.2 配置 API Key

方式一: 通过 Web UI 的「模型配置」页面设置

方式二: 编辑 `config.yaml` 或设置环境变量:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

### 7.3 启动

```bash
# Web 服务模式 (推荐)
python run.py

# 指定端口
python run.py --port 3000

# CLI 交互模式
python run.py --cli
```

启动后浏览器打开 `http://localhost:8080`

### 7.4 自定义提示词

1. 打开 Web UI → 「提示词配置」
2. 选择要修改的部门 (如 中书省)
3. 编辑 System Prompt
4. 保存

### 7.5 创建任务模板

1. 打开 Web UI → 「模板管理」
2. 填写模板 ID、名称、描述和默认 Prompt
3. 在「奏事」页面选择模板使用

---

## 8. 项目结构

```
E:\trae\cc\
├─ ARCHITECTURE.md              # 本文档
├─ requirements.txt             # Python 依赖
├─ run.py                       # 一键启动脚本
├─ config.yaml                  # 默认配置 (自动生成)
│
├─ user_data/                   # 用户数据 (自定义提示词/模板/工具)
│  ├─ prompts/                  # 自定义 System Prompt (.txt)
│  │  └─ .gitkeep
│  ├─ templates/                # 自定义任务模板 (.yaml)
│  │  └─ example_bug_fix.yaml
│  ├─ tools/                    # 自定义工具定义 (.yaml)
│  │  └─ custom_tools.yaml
│  └─ config.db                 # SQLite (Web UI 持久化, 自动生成)
│
├─ src/
│  ├─ main.py                   # 三省六部流程主控制器
│  ├─ config_manager.py         # 统一配置管理 (YAML+SQLite)
│  │
│  ├─ agents/                   # Agent 实现
│  │  ├─ base.py                # Agent 基类 (多模型适配)
│  │  ├─ zhongshu.py            # 中书省 — Planner
│  │  ├─ menxia.py              # 门下省 — Reviewer
│  │  ├─ shangshu.py            # 尚书省 — Orchestrator
│  │  ├─ libu.py                # 吏部 — Context Manager
│  │  ├─ bingbu.py              # 兵部 — Executor
│  │  └─ xingbu.py              # 刑部 — Tester
│  │
│  ├─ core/                     # 核心引擎
│  │  ├─ state_machine.py       # 状态机引擎 (15状态)
│  │  ├─ message_bus.py         # 消息总线
│  │  ├─ court_event_log.py     # 朝堂事件日志
│  │  ├─ court_report.py        # 朝堂报告生成器
│  │  └─ human_interface.py     # 人类介入管理
│  │
│  ├─ llm/                      # LLM 抽象层
│  │  └─ providers.py           # LiteLLM 多模型适配 (Claude/GPT/Ollama/...)
│  │
│  ├─ data/
│  │  ├─ schemas.py             # 全部数据结构定义
│  │  └─ prompts.py             # 默认 System Prompt 模板
│  │
│  ├─ storage/
│  │  └─ vector_store.py        # ChromaDB 向量库封装
│  │
│  └─ web/                      # Web 应用
│     ├─ app.py                 # FastAPI 后端 (REST + WebSocket)
│     └─ static/
│         ├─ index.html         # 单页应用
│         ├─ css/style.css      # 样式 (中国风配色)
│         └─ js/app.js          # 前端逻辑
│
└─ tests/                       # 测试 (待补充)
```

---

> **设计哲学**: 三省六部提供流程引擎和工具机制, 用户提供提示词和模板。  
> 平台不绑定任何特定模型或提示词 —— 用户拥有完全的控制权。
