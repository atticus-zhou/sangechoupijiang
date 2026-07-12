# 公开发布交接说明

这份文档用于把“三个臭皮匠”交给面试官、访客或新开发者时说明清楚：现在能公开展示什么，不能承诺什么，怎样验证公开仓库没有把本地真实生产能力和个人密钥暴露出去。

当前推荐公开形态是：个人网站或作品集展示产品定位、办公室大厅、无 Key 固定样例、样例交付物下载和 GitHub 源码；真实生产继续由使用者在本地填写自己的模型 Key 后运行。

## 可以公开展示什么

- 首页公开展示页和 `/api/demo/public-showcase` 清单。
- 由 `python scripts/export_public_showcase.py` 生成的 `dist/public-showcase` 静态站点；它可以在没有 FastAPI 后端的情况下托管到个人网站或 Vercel。
- AI 漫剧制片办公室固定样例：故事、资产引用链路、样例 Word 制片画布、handoff manifest、下游交接门禁。
- 研究办公室固定样例：阶段报告、来源清单、数据表、截图计划和证据缺口说明。
- 第一次运行清单、模型配置说明、办公室协议、办公室上线门禁和隔离验证。
- GitHub README、部署边界、安全说明和 release readiness 结果。

这些内容都应该能在不配置真实 API Key 的情况下查看或验证。它们证明的是产品能力样例和工程边界，不等同于把本地真实生产系统开放成 SaaS。

## 不应该公开承诺什么

- 不宣称全自动飞瓜会员级调研，也不宣称可以绕过第三方平台账号、权限、登录和截图限制。
- 不宣称当前版本已经是多用户 SaaS；账号体系、权限、计费、队列、文件授权和成本控制仍属于未来阶段。
- 不要公开 API Key、Cookie、登录态、浏览器 Profile、`config.yaml`、`.env`、`user_data/`、`output/`、数据库、日志或真实生成产物。
- 不要把作者自己的模型 Key 放进 Vercel 前端环境变量、静态 JSON、HTML 或浏览器端 JavaScript。
- 不宣称 AI 漫剧制片办公室会直接生成成片；当前交付目标是下游可接手的制片包、提示词、图片记录、Word 画布和引用链路。

## 面试官或访客建议路径

1. 打开个人网站上的静态展示页，或从本地首页进入公开展示页。
2. 查看 `/api/demo/public-showcase` 对应的产品定位、访客路径、3 分钟演示脚本、推荐 demo 和安全边界。
3. 先看 AI 漫剧制片办公室固定样例，下载 Word 制片画布和 handoff manifest。
4. 再看研究办公室固定样例，确认报告、来源、截图计划和证据缺口是分开呈现的。
5. 最后查看 README 和这份交接说明，确认公开演示不消耗作者 API Key，也没有承诺未完成的 SaaS 能力。

## 样例交付物阅读检查

公开演示交付物应该按文件检查，而不是只看页面截图：

- AI 漫剧 Word 制片画布：确认故事、视觉母版、人物/道具/场景资产、镜头提示词和下游执行清单处在同一套制片包里。
- AI 漫剧 handoff manifest：确认 `story_version`、`style_version`、`asset_id`、`image_id`、`shot_id`、首帧参考和 `production_lineage` 能追踪每个素材和镜头的来源。
- 研究办公室阶段报告：确认结论、来源、数据表、截图计划和证据缺口分开呈现。
- 研究办公室证据清单：确认来源、数据、截图计划、缺口和人工确认项没有被伪装成已完成采集。

这份检查也会由 `python scripts/verify_first_run_readiness.py --format markdown` 输出，作为第一次从 GitHub 下载项目后的交付物阅读指南。

## 新开发者本地复现路径

第一次下载仓库后，先不要填模型 Key，先运行：

```powershell
python scripts/verify_first_run_readiness.py --format markdown
python scripts/verify_public_demo_mode.py --format markdown
python scripts/export_public_showcase.py
python scripts/verify_static_public_showcase.py --format markdown
python scripts/verify_comic_v2_downstream_handoff.py --format markdown
python scripts/verify_research_office_readiness.py --format markdown
python scripts/verify_release_readiness.py --format markdown
python scripts/check_no_secrets.py
```

这些命令会检查公开演示、静态部署包、样例交付、下游制片交接、研究办公室边界、总发布门禁和敏感信息扫描。通过后，再复制 `config.example.yaml` 为 `config.yaml`，进入本地真实模式，用自己的模型 Key 测试各部门。

## 维护者发布前检查

公开仓库、作品集页面或演示包更新前，至少确认：

- `python scripts/verify_productization_status.py --format markdown` 能把产品化目标映射到证据。
- `python scripts/verify_first_run_readiness.py --format markdown` 能说明公开演示、本地真实使用和开发者扩展三条路径。
- `python scripts/verify_public_demo_mode.py --format markdown` 能证明公开展示清单、demo 端点和样例下载可用。
- `python scripts/verify_static_public_showcase.py --format markdown` 能证明静态作品集不依赖后端，四份下载物、阅读指南和真实产品截图都可用。
- `python scripts/verify_comic_v2_delivery.py --format markdown` 能证明 AI 漫剧 Word 画布结构、资产 ID、镜头 ID、图片记录和交付审计可用。
- `python scripts/verify_comic_v2_downstream_handoff.py --format markdown` 能证明人物三视图、表情、道具、场景广角/俯视图、镜头视频包、首帧参考图和失败重试策略可交接。
- `python scripts/verify_research_office_readiness.py --format markdown` 能证明研究办公室只公开阶段性样例和证据边界，不伪装成全自动平台采集。
- `python scripts/verify_release_readiness.py --format markdown` 能串联全部 no-key 发布门禁。
- `python scripts/check_no_secrets.py` 能证明仓库没有误提交敏感信息或运行产物。

如果其中任一项失败，不要把当前版本描述为公开发布就绪。

## 相关证据

- [README](../README.md)
- [部署模式说明](DEPLOYMENT_MODES.md)
- [无 Key 静态展示部署](STATIC_SHOWCASE_DEPLOYMENT.md)
- [产品化状态表](PRODUCTIZATION_STATUS.md)
- [模型配置说明](MODEL_CONFIGURATION.md)
- [AI 漫剧下游交接说明](COMIC_DOWNSTREAM_HANDOFF.md)
