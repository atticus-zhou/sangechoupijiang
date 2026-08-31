# 先看这里：三个臭皮匠第一次打开怎么走

这份文件给刚从 GitHub 下载项目的人看。先别急着填 API Key，也别直接部署成线上 SaaS。先判断你属于哪一种情况。

## 我只是想看看产品

不需要 API Key。

```powershell
python scripts/verify_public_demo_mode.py --format markdown
python scripts/export_public_showcase.py
python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase
```

看 `dist/public-showcase/index.html`，重点检查三件事：

- AI 漫剧制片办公室是不是能展示故事、资产、提示词、图片记录、Word 制片画布和 handoff manifest。
- 研究办公室是不是能展示阶段报告、来源、数据、截图计划和证据缺口。
- 页面是否明确写着无 Key、只读、不调用真实模型、不证明真实画质。

## 我想在自己电脑上真实使用

需要你自己的模型 Key。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.yaml config.yaml
python scripts/doctor.py --format markdown
python run.py --port 8080
```

打开：

```text
http://127.0.0.1:8080/
```

进入模型页面后，先按办公室测试部门。不要一开始就跑完整生产。

### AI 漫剧制片办公室最小配置

- 文本部门：内阁、中书省、门下省、尚书省、吏部、户部、礼部、兵部。
- 工部：生图模型，例如豆包 Seedream、Qwen Image、MiniMax Image。
- 刑部：视觉理解模型，例如 Qwen VL、GPT 多模态、Gemini 多模态。

只有文本模型时，可以聊故事、确认剧本、拆人物/道具/场景、生成提示词草案。  
工部和刑部也通过后，才适合生成基础资产图、视觉质检和完整 Word 制片画布。

### 研究办公室最小配置

- 大部分部门使用文本模型。
- 刑部需要视觉理解模型时，才适合分析截图。
- 工部不是普通文本 Key 槽位，它代表浏览器、人工截图或平台导出证据能力。

## 我想部署给别人看

只部署无 Key 静态展示包。

```powershell
python scripts/export_public_showcase.py
python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase
python scripts/check_no_secrets.py
```

如果复制到个人网站，继续跑：

```powershell
python scripts/verify_portfolio_showcase_sync.py --format markdown
```

线上地址是否真的可用，必须用实际 URL 检查。对于作者当前个人网站，权威检查是：

```powershell
npm run check:online
```

这条命令通过前，不要说 `https://www.atticus.asia/three-stooges/` 已经上线。

## 我想继续开发新办公室

先看办公室隔离和扩展协议，不要复制一套旧页面就开新办公室。

```powershell
python scripts/verify_office_isolation.py --format markdown
python scripts/verify_office_extension_governance.py --format markdown
python scripts/verify_office_expansion_decision_brief.py --format markdown
python scripts/export_office_creation_template.py --format markdown
```

扩展顺序和暂缓原因先看 `docs/OFFICE_EXPANSION_DECISION_BRIEF.md`。当前建议是先稳定 AI 漫剧制片办公室和研究办公室，再把 `ecommerce_selection` 作为第一间候选新办公室。

新办公室必须有自己的 `office_id`、模型配置、工作区、历史记录、产物清单、schema gate、recovery actions 和公开演示边界。

## 绝对不要提交

- 真实 API Key、Cookie、浏览器登录态。
- `config.yaml`、`.env`、数据库、日志。
- `user_data/`、`output/`、真实运行生成的 Word、图片、截图。
- 会让访客消耗作者模型额度的前端配置。

提交或公开前至少跑：

```powershell
python scripts/check_no_secrets.py
python scripts/verify_release_readiness.py --format markdown
```
