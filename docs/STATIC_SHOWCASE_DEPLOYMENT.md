# 无 Key 静态展示部署

这条路径用于把“三个臭皮匠”放进个人网站、作品集或面试展示页。它输出的是一个自包含的静态站点，不需要 Python 后端，不读取 `config.yaml`，不调用真实模型，也不会消耗作者 API Key。

它不是在线 SaaS。访客可以看固定样例、理解两个办公室的工作链、下载四份样例交付物，但不能提交真实创作任务。

## 一键生成

先在项目根目录安装依赖，然后运行：

```powershell
python scripts/export_public_showcase.py
python scripts/verify_static_public_showcase.py --format markdown
```

生成入口：

```text
dist/public-showcase/index.html
```

静态包包含：

- 一个无需后端即可打开的公开展示页。
- AI 漫剧制片办公室与研究办公室的固定样例说明。
- 样例 Word 制片画布、handoff manifest、阶段调研报告和证据清单。
- 实际产品界面截图、交付物阅读顺序和 3 分钟面试演示脚本。
- `export-manifest.json`，用于核对文件大小、哈希和安全标志。

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
python scripts/verify_release_readiness.py --format markdown
python scripts/check_no_secrets.py
```

只有四条命令全部通过，才发布新的静态包。

## 安全边界

不要把下面内容复制进静态展示目录：

- `config.yaml`、`.env` 或任何 API Key。
- `user_data/`、`output/`、数据库、日志或浏览器配置。
- Cookie、第三方平台登录态、真实客户资料和本地创作历史。

`dist/` 已被 Git 忽略。静态包是部署产物，不应混入源码提交；源码仓库只提交导出器、模板、固定样例和验证器。
