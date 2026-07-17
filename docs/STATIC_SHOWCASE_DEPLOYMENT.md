# 无 Key 静态展示部署

这条路径用于把“三个臭皮匠”放进个人网站、作品集或面试展示页。它输出的是一个自包含的静态站点，不需要 Python 后端，不读取 `config.yaml`，不调用真实模型，也不会消耗作者 API Key。

它不是在线 SaaS。访客可以看固定样例、理解两个办公室的工作链、按最快验收路线检查四个关键证据、下载六份样例交付物，并查看 AI 漫剧下游生产 quick-start，但不能提交真实创作任务。

## 一键生成

先在项目根目录安装依赖，然后运行：

```powershell
python scripts/export_public_showcase.py
python scripts/verify_static_public_showcase.py --format markdown
python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase
```

生成入口：

```text
dist/public-showcase/index.html
```

## 个人网站接入协议

`/api/demo/public-showcase` 的 `portfolio_embed.portfolio_integration` 是给个人网站或作品集页使用的机器可读接入协议。它和这份文档保持同一套边界：

- 推荐路径是 `static_export`，源目录固定为 `dist/public-showcase`。
- 独立部署时，把 `dist/public-showcase` 当作一个纯静态站点发布。
- 嵌入已有个人网站时，把 `dist/public-showcase/*` 复制到个人网站仓库的 `public/three-stooges/`，再链接到 `/three-stooges/`。
- 必须保留 `index.html`、`data.js`、`app.js`、`style.css`、`assets/public-showcase-desktop.png`、`downloads/`、`data/comic_production_claim_report.json`、`export-manifest.json` 和 `portfolio-deploy-manifest.json`。
- 禁止把 `config.yaml`、`.env`、API Key、Cookie、`user_data/`、`output/`、浏览器 Profile 或真实用户工作区复制进公开站点。

`python scripts/verify_public_demo_mode.py --format markdown` 和 `python scripts/verify_static_public_showcase.py --format markdown` 都会检查这份接入协议。如果后续修改了个人网站接入方式，必须同时更新接口、静态页和验证器。

注意：不带 `--existing-dir` 时，验证器会临时导出一份新包再检查；带 `--existing-dir dist/public-showcase` 时，它检查的是你即将复制到个人网站或部署到 Vercel 的现有目录。部署前建议两条都跑，前者证明导出链路可复现，后者证明当前目录不是旧包。

静态包包含：

- 一个无需后端即可打开的公开展示页。
- 首次打开时的最快验收路线：确认安全公开页、下载 Word 制片画布、核对 handoff manifest、查看声明边界和复现命令。
- 三条首次使用路径：
  - `public_demo`：不需要 API Key，只看固定样例、下载物、阅读指南和公开安全边界，适合面试官或作品集访客。
  - `local_real_use`：使用者在本机填写自己的 API Key，测试各办公室部门模型后，再运行真实调研或 AI 漫剧制片。
  - `developer_extension`：开发者先跑办公室协议、隔离和扩展治理检查，再新增办公室，避免模型配置、工作区、历史和产物串线。
- AI 漫剧制片办公室与研究办公室的固定样例说明。
- 样例 Word 制片画布、handoff manifest、阶段调研报告和证据清单。
- 六份下载物和七个可复核文件目录，包含研究办公室阶段性交付声明和 AI 漫剧真实生产声明报告。
- AI 漫剧下游生产 quick-start，说明 Word 画布之后如何确认资产、逐镜头生成、复核和归档。
- 实际产品界面截图、交付物阅读顺序和 3 分钟面试演示脚本。
- 复现与验收清单，列出公开 demo、静态导出、真实生产声明和 release readiness 的 no-key 检查命令，以及每条命令通过或失败时该怎么判断。
- `export-manifest.json`，用于核对文件大小、哈希和安全标志。
- `portfolio-deploy-manifest.json`，用于核对个人网站复制目标、入口路径、必需文件、禁止带入内容和发布前验证命令。

## 本机预览

直接打开 `dist/public-showcase/index.html` 即可。为了模拟真实静态托管，也可以运行：

```powershell
python -m http.server 4173 --directory dist/public-showcase
```

然后访问：

```text
http://127.0.0.1:4173/
```

## 部署到 Vercel

最轻量的方式是先在本机生成并验证静态包，再把这个目录作为纯静态站点部署：

```powershell
npx vercel --cwd dist/public-showcase
npx vercel --prod --cwd dist/public-showcase
```

第一次运行时 Vercel 会让你选择账号和项目。这个目录没有服务端函数，也不需要添加任何 API Key 环境变量。

如果个人网站已经在 Vercel 上，有两种接法：

1. 把静态展示部署成独立项目，再在个人网站的“三个臭皮匠”项目卡片中链接到它。这种方式最稳，也不会影响个人网站现有构建。
2. 把 `dist/public-showcase` 的内容复制到个人网站仓库的静态资源目录，例如 `public/three-stooges/`，再从个人网站链接到 `/three-stooges/`。复制后要确认站点框架会原样保留子目录中的 `index.html`、JS、CSS 和下载文件。

## 部署到 Netlify 或 GitHub Pages

Netlify 的发布目录选择 `dist/public-showcase`。GitHub Pages 需要把该目录发布到 Pages 分支或由 Actions 上传为 Pages artifact。两者都只能托管导出后的静态包，不能直接把 FastAPI 项目根目录当成静态站点。

## 发布前检查

每次更新样例、展示文案或下载物后，重新运行：

```powershell
python scripts/export_public_showcase.py
python scripts/verify_static_public_showcase.py --format markdown
python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase
python scripts/verify_release_readiness.py --format markdown
python scripts/check_no_secrets.py
```

只有这些命令全部通过，才发布新的静态包。

## 安全边界

不要把下面内容复制进静态展示目录：

- `config.yaml`、`.env` 或任何 API Key。
- `user_data/`、`output/`、数据库、日志或浏览器配置。
- Cookie、第三方平台登录态、真实客户资料和本地创作历史。

`dist/` 已被 Git 忽略。静态包是部署产物，不应混入源码提交；源码仓库只提交导出器、模板、固定样例和验证器。
