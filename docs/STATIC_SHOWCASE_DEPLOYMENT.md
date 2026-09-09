# 无 Key 静态展示部署

这条路径用于把“三个臭皮匠”放进个人网站、作品集或面试展示页。它输出的是一个自包含的静态站点，不需要 Python 后端，不读取 `config.yaml`，不调用真实模型，也不会消耗作者 API Key。

它不是在线 SaaS。访客可以看固定样例、理解两个办公室的工作链、按最快验收路线检查五个关键证据、下载八份样例下载物，并查看 AI 漫剧下游生产 quick-start，但不能提交真实创作任务。

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
- `data/comic_production_claim_report.json` 必须保留 `claim_upgrade_checklist` 和 `claim_upgrade_recovery`：前者说明真实质量还缺哪些证据，后者说明失败后如何保留 story/asset/prompt、用 `regenerate_images` 重建图片证据和视觉质检，再重建 Word、handoff manifest 和 claim report。
- `showcase.json` 和 `data.js` 必须保留 `portfolio_embed.public_recovery_drill`：公开页会把它渲染成失败恢复演练卡，说明 `fixture_only` 样例如何通过 `regenerate_images` 回到真实图片生成、刑部质检和重新交付，而不是让访客误以为 demo 图片已经代表真实画质。
- 禁止把 `config.yaml`、`.env`、API Key、Cookie、`user_data/`、`output/`、浏览器 Profile 或真实用户工作区复制进公开站点。

`python scripts/verify_public_demo_mode.py --format markdown` 和 `python scripts/verify_static_public_showcase.py --format markdown` 都会检查这份接入协议。如果后续修改了个人网站接入方式，必须同时更新接口、静态页和验证器。

注意：不带 `--existing-dir` 时，验证器会临时导出一份新包再检查；带 `--existing-dir dist/public-showcase` 时，它检查的是你即将复制到个人网站或部署到 Vercel 的现有目录。部署前建议两条都跑，前者证明导出链路可复现，后者证明当前目录不是旧包。

部署完成后，用真实线上 URL 做最终检查：

```powershell
python scripts/verify_public_showcase_live.py --url https://www.atticus.asia/three-stooges/ --format markdown
```

这条命令不需要 Vercel 登录，也不会读取本地 Key。它只从公开 URL 下载首页、`showcase.json`、`export-manifest.json`、访客验收指南、真实生产声明报告、样例 Word 画布和 handoff manifest。它通过时，才能把这个 URL 当作可发给面试官或访客的线上证据。

静态包包含：

- 一个无需后端即可打开的公开展示页。
- 首次打开时的最快验收路线：确认安全公开页、下载 Word 制片画布、核对 handoff manifest、核对资产图片规格矩阵和资产使用地图、查看声明边界和复现命令。
- A seven-step visitor route for quickly checking the public page, Word canvas, handoff manifest, trace bundle, production acceptance card, asset matrix, asset usage map, claim boundary, and reproducibility commands.
- 三条首次使用路径：
  - `public_demo`：不需要 API Key，只看固定样例、下载物、阅读指南和公开安全边界，适合面试官或作品集访客。
  - `local_real_use`：使用者在本机填写自己的 API Key，测试各办公室部门模型后，再运行真实调研或 AI 漫剧制片。
  - `developer_extension`：开发者先跑办公室协议、隔离和扩展治理检查，再新增办公室，避免模型配置、工作区、历史和产物串线。
- AI 漫剧制片办公室与研究办公室的固定样例说明。
- 样例 Word 制片画布、handoff manifest、阶段调研报告、证据清单和研究补证操作手册。
- 八份下载物和十二个可复核文件目录，包含 AI 漫剧追溯记录、AI 漫剧生产验收卡、研究办公室阶段性交付声明、`evidence_capture_playbook`、AI 漫剧真实生产声明报告、AI 漫剧真实运行证据收口单、办公室扩展决策简报和面试官评审包。
- AI 漫剧真实生产声明报告里的 `claim_upgrade_recovery` 卡片，明确公开样例只证明结构；如果要升级为真实质量证据，需要本地配置模型、重新生成图片、执行视觉质检，并重新写入质量基准。
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

Netlify 的发布目录选择 `dist/public-showcase`。GitHub Pages 只发布导出后的静态包，不能直接把 FastAPI 项目根目录当成静态站点。

产品仓库已经提供备用 GitHub Pages 工作流：

```text
.github/workflows/pages-showcase.yml
```

它会在 `main` 更新或手动触发时执行三步：导出 `dist/public-showcase`、验证静态包、运行敏感信息扫描，然后上传 GitHub Pages artifact。这个通道不需要 Vercel 授权，也不需要任何 API Key。第一次使用前，需要在 GitHub 仓库 Settings -> Pages 中把 Source 设为 GitHub Actions；如果组织或仓库禁用了 Pages，工作流会留下 `GitHub Pages not enabled` 提示，静态 artifact 仍然会完成构建和验证，但公开 URL 不应宣称已发布。

## 发布前检查

每次更新样例、展示文案或下载物后，重新运行：

```powershell
python scripts/export_public_showcase.py
python scripts/verify_static_public_showcase.py --format markdown
python scripts/verify_static_public_showcase.py --format markdown --existing-dir dist/public-showcase
python scripts/verify_public_showcase_live.py --url https://www.atticus.asia/three-stooges/ --format markdown
python scripts/verify_comic_real_production_claim.py --format markdown
python scripts/verify_release_readiness.py --format markdown
python scripts/check_no_secrets.py
```

只有这些命令全部通过，才发布新的静态包。

## GitHub 邮件失败怎么判断

如果邮箱提示 `Three Cobblers showcase workflow run failed`，先不要把它当成真实产品崩溃。这个邮件通常只说明某一次 GitHub Actions 没有通过，需要先定位它属于哪条链路：

- 产品本体仓库失败：运行 `python scripts/verify_release_readiness.py --format markdown` 和 `python scripts/check_no_secrets.py`。如果这两条通过，公开 no-key release gate 和安全扫描在本机是成立的。
- 个人网站仓库失败：进入个人网站仓库运行 `npm run check:showcase-ci`。这条会按 GitHub Actions 的顺序检查本地静态展示、交接文档、备用审阅包、构建和 build-info。
- 本地 `check:showcase-ci` 通过但线上还是 404：问题通常在 Vercel 授权、Vercel 没有重新部署、或者线上仍在服务旧 bundle。继续运行个人网站仓库的 `npm run doctor:deploy` 和 `npm run check:online`，不要为了消掉 404 去改产品展示数据。

这三种结果的边界要分清：GitHub Actions 证明仓库构建和 no-key 展示包；`check:showcase-ci` 证明个人网站仓库里的静态拷贝能构建；`check:online` 才证明生产域名真的已经更新。

## 安全边界

不要把下面内容复制进静态展示目录：

- `config.yaml`、`.env` 或任何 API Key。
- `user_data/`、`output/`、数据库、日志或浏览器配置。
- Cookie、第三方平台登录态、真实客户资料和本地创作历史。

`dist/` 已被 Git 忽略。静态包是部署产物，不应混入源码提交；源码仓库只提交导出器、模板、固定样例和验证器。

## Personal Website Vercel Handoff

The main product repository owns the no-key static export at `dist/public-showcase`. The personal website repository owns the public route `/three-stooges/`.

Current handoff contract:

- Copy `dist/public-showcase/*` into the personal website repository at `public/three-stooges/`.
- The personal website must expose a link to `/three-stooges/` and keep the copied static files backend-free.
- The personal website has its own deployment helpers: `npm run doctor:deploy`, `npm run check:showcase`, `npm run prepare:vercel-prebuilt`, `npm run ship:vercel`, and `npm run check:online`.
- Run `npm run doctor:deploy` first when you are unsure whether the current blocker is local package readiness, Vercel authorization, prebuilt output, or the live production route.
- `npm run check:online` is the authority for the live site. If it reports `/three-stooges/` as 404, the static package is prepared but Vercel is still serving an older deployment.
- The product repository can also verify any deployed static URL with `python scripts/verify_public_showcase_live.py --url <public-url> --format markdown`; this is useful for Vercel, Netlify, GitHub Pages, or an independent static host.
- When Vercel CLI asks for device authorization, complete `npx vercel login`, then rerun `npm run ship:vercel`.

Do not describe the personal website as live until `npm run check:online` passes against the production domain. If you deploy the static package outside the personal website, do not share that URL until `verify_public_showcase_live.py` passes against the same URL.

## Vercel 线上仍是 404 时怎么处理

如果本地 `npm run check:showcase`、`npm run prepare:vercel-prebuilt` 都通过，但 `npm run check:online` 仍然报告 `/three-stooges/` 是 404，先不要继续改三个臭皮匠产品代码。这通常只说明 Vercel 还在服务旧构建，或者 Vercel 项目没有从当前 GitHub 分支重新部署。

推荐先走 Dashboard 路线：

1. 打开 Vercel Dashboard。
2. 进入 `personal-website-v2` 项目。
3. 打开 Deployments。
4. 找到最新的 `main` 分支提交。
5. 点击 Redeploy。
6. 等部署完成后，在个人网站仓库重新运行 `npm run check:online`。

如果你想走命令行路线：

1. 在个人网站仓库运行 `npm run check:vercel-auth`。
2. 如果提示没有 Vercel 授权，运行 `npx vercel login`，在浏览器里完成登录。
3. 回到终端运行 `npm run ship:vercel`。
4. 最后运行 `npm run check:online`。

两个判断要分清：

- `npm run check:showcase` 通过：说明个人网站仓库里的静态展示包是好的。
- `npm run check:online` 通过：说明 `https://www.atticus.asia/three-stooges/` 这个线上地址真的已经更新。

只有第二条通过，才适合把线上链接发给面试官。任何时候都不要为了让线上检查通过，把 API Key、Cookie、`config.yaml`、`.env`、`user_data/`、`output/` 或真实运行产物放进 `public/three-stooges/`。

## Visitor Acceptance Guide

The static package must also keep `data/visitor_acceptance_guide.json`.
This file is the reviewer-facing route for the public demo: it records the
seven-step visitor route, the nine reviewable files, the demo-only claim
boundaries, and the live-site rule that `/three-stooges/` is not public evidence
until `npm run check:online` passes.

After copying `dist/public-showcase/*` into the personal website repository,
both local and online checks must include this file:

```powershell
npm run check:showcase
npm run check:online
```

`check:showcase` proves the copied local package contains the visitor acceptance
guide. `check:online` proves the production Vercel domain is serving the same
guide instead of an older build.

## Asset Requirement Matrix In The Static Package

The static package must carry the same `asset_requirement_matrix` that the API
demo exposes. This matrix is part of the public handoff story, not decoration:

- it proves that characters, props, and scenes have different image
  requirements;
- it makes clean white-background requirements visible for character and prop
  base assets;
- it makes scene `wide` and `top_down` spatial references visible before any
  downstream video generation;
- it lets a reviewer compare the page, `showcase.json`,
  `data/comic_production.json`, and the downloadable handoff manifest.

After copying `dist/public-showcase/*` into `public/three-stooges/`, verify the
matrix in the personal website repository:

```powershell
npm run check:showcase
Select-String -Path public\three-stooges\index.html -Pattern "资产图片规格矩阵|ASSET REQUIREMENTS"
Select-String -Path public\three-stooges\showcase.json -Pattern "asset_requirement_matrix|three_view|top_down"
```

## Asset Usage Map In The Static Package

The static package must also carry `asset_usage_map`. This is the reviewer-facing
bridge between the asset files and the downstream video workflow:

- it tells which image is the identity baseline for each character, prop, or
  scene;
- it explains every image role, such as three-view identity, expression sheet,
  prop turnaround, scene wide shot, or top-down layout;
- it lists which shots reference each asset and whether the asset is used as a
  primary first-frame reference;
- it gives downstream operators a short reuse instruction so they do not guess
  how to bind images into Libtv, Xiaoyunque, or another video tool.

After copying the static package, verify the usage map in the personal website
repository:

```powershell
npm run check:showcase
Select-String -Path public\three-stooges\index.html -Pattern "asset-usage-map"
Select-String -Path public\three-stooges\showcase.json -Pattern "asset_usage_map|identity_baseline_image_id|referenced_by_shots"
```

If the local static package is ready but `https://www.atticus.asia/three-stooges/`
returns 404, do not edit the product code to hide the failure. Finish Vercel
authorization or redeploy the personal website, then use `npm run check:online`
as the live evidence.
