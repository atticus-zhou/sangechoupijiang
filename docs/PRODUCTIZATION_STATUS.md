# 产品化状态审计

这份文档用来回答一个问题：当前“三个臭皮匠”距离可公开展示、可复现、可扩展的产品化阶段，到底哪些已经有证据，哪些仍然只是后续路线。

它不是路线图，也不是宣传稿。它是给开发者、面试官和未来维护者看的状态表：每一条产品承诺都必须能落到一个可运行命令、一个公开接口、一个样例交付物或一份安全边界文档上。

## 一键总门禁

公开展示或提交代码前，先运行：

```powershell
python scripts/verify_productization_status.py --format markdown
python scripts/verify_model_configuration_guidance.py --format markdown
python scripts/verify_public_docs_readability.py --format markdown
python scripts/verify_release_readiness.py --format markdown
python scripts/check_no_secrets.py
python scripts/verify_comic_real_production_claim.py --format markdown
docs/REAL_PRODUCTION_CLAIMS.md
```

`verify_productization_status.py` 负责检查这份产品化状态表是否覆盖关键目标；`verify_model_configuration_guidance.py` 负责检查模型配置说明、示例配置、前端模型页和 preflight 是否一致；`verify_public_docs_readability.py` 负责检查 README、部署说明、公开交接、真实生产声明和下游交付文档是否保持 UTF-8 可读、命令齐全、边界清楚；`verify_release_readiness.py` 负责串联 no-key 运行门禁，并自动纳入办公室模型配置、工作区、历史和产物隔离检查；`check_no_secrets.py` 负责确认仓库没有误提交密钥、日志、数据库和运行产物。

## 目标覆盖表

| ID | 产品化承诺 | 当前状态 | 权威证据 |
| --- | --- | --- | --- |
| P1 | 个人网站和公开作品集可以展示产品，但不暴露真实 API Key | 已具备 demo-only 展示边界、发布状态铭牌和后端无关的静态部署包 | `python scripts/verify_public_demo_mode.py --format markdown`、`python scripts/verify_static_public_showcase.py --format markdown`、`/api/demo/public-showcase` 的 `release_badge`、`docs/STATIC_SHOWCASE_DEPLOYMENT.md` |
| P2 | 面试官可以无 Key 看到固定样例、流程说明、样例交付物和下载物 | 已具备公开演示包，并提供复现与验收清单说明每条 no-key 检查命令证明什么 | `/api/demo/public-showcase` 的 `portfolio_embed`、样例 Word 画布、handoff manifest、`python scripts/verify_public_demo_mode.py --format markdown` |
| P3 | 从 GitHub 下载项目后，开发者能复现本地运行路径 | 已具备第一次运行清单 | `python scripts/verify_first_run_readiness.py --format markdown`、`python scripts/doctor.py`、`README.md` |
| P4 | AI 漫剧制片办公室输出不止聊天文本，而是可追溯制片包 | 已具备 deterministic 样例交付验证 | `python scripts/verify_comic_v2_delivery.py --format markdown`、`python scripts/verify_comic_v2_user_flow.py`、Word 制片画布、`*_handoff_manifest.json` |
| P5 | 漫剧生产链路保留资产身份、引用链路、提示词包、图片记录、历史追溯和失败恢复 | 已具备跨产物质量基准、部门级恢复路由和旧版不可审计标记，仍需用真实模型产物持续积累质量证据 | `python scripts/verify_product_readiness.py --format markdown --run-e2e`、`python scripts/verify_comic_v2_production_benchmark.py --format markdown`、历史下载和 lineage 字段 |
| P6 | 研究办公室可以公开展示阶段性能力，但不伪装成全自动飞瓜会员级交付 | 已具备 staged demo、证据缺口说明和待补证据交接表 | `python scripts/verify_research_office_readiness.py --format markdown`、研究样例报告、证据 manifest |
| P7 | 新办公室可以继续扩展，同时不会污染已有办公室的模型配置、历史和产物 | 已具备办公室隔离、扩展治理、可读演示契约门禁和 `extension_blueprint` 扩展蓝图 | `python scripts/verify_office_isolation.py --format markdown`、`python scripts/verify_office_extension_governance.py --format markdown`、`/api/offices/protocols`、`required_demo_contract`（参观路径、证明点、下载物、阅读指南、面试脚本和公开安全边界） |
| P8 | 公开仓库不应包含用户密钥、Cookie、数据库、输出目录或运行日志 | 已具备安全扫描和部署边界文档 | `python scripts/check_no_secrets.py`、`.gitignore`、`docs/DEPLOYMENT_MODES.md` |
| P9 | 新用户能看懂每个部门需要什么模型，以及最小可跑和完整制片配置的区别 | 已具备模型配置指南和离线一致性验证 | `docs/MODEL_CONFIGURATION.md`、`python scripts/verify_model_configuration_guidance.py --format markdown`、模型页面测试按钮 |
| P10 | AI 漫剧制片包能被下游视频平台或剪辑流程接手，而不是只生成一个 Word 文件 | 已具备人物三视图、镜头视频包、下游交接门禁、机器可读导演合同和诚实的质量声明 | `docs/COMIC_DOWNSTREAM_HANDOFF.md`、`python scripts/verify_comic_v2_downstream_handoff.py --format markdown`、`python scripts/verify_comic_v2_production_benchmark.py --format markdown`、handoff manifest v3 |

## 当前可公开展示的形态

可以公开展示的是“产品能力样例”，不是把本地真实生产系统直接开放给陌生用户。

推荐公开页面展示：

- 办公室大厅和产品定位。
- 发布状态铭牌，集中说明无 Key、demo-only、静态托管、真实模型不调用和真实画质未验证。
- AI 漫剧制片办公室的固定样例流程。
- 研究办公室的固定样例流程。
- 样例 Word 制片画布、handoff manifest、研究样例报告和截图目标说明。
- GitHub README、部署边界、安全说明和 release readiness 结果。
- 可直接托管到个人网站或静态平台的 `dist/public-showcase` 导出包。

公开页面必须保持 demo-only：

- 不读取 `config.yaml`。
- 不调用真实模型。
- 不写入用户本地工作区。
- 不暴露个人 API Key。
- 不让访客提交真实生产任务。

## 本地真实使用的形态

真实创作和真实调研仍然走本地模式：用户下载仓库，在自己的机器上填写自己的模型配置，并通过 `python run.py --port 8080` 运行。

这个模式可以：

- 调用用户自己的文本模型、视觉理解模型和图片生成模型。
- 生成本地 Word 画布、图片、manifest 和历史记录。
- 在模型页面测试各部门配置是否连通。
- 在历史里追溯 story、asset、prompt、image 和 Word 交付版本。

这个模式不应该：

- 把用户的 Key 提交到 GitHub。
- 把用户的输出目录、数据库或日志提交到 GitHub。
- 被误包装成多用户 SaaS。

## 仍未宣称完成的事项

这些事项不应在 README 或个人网站里说成已经完成：

- 真正多租户 SaaS：还没有账号、权限、配额、计费、队列、租户隔离和云端文件存储。
- 陌生用户在线真实调用模型：公开部署版本当前只适合固定样例演示。
- 飞瓜等第三方平台的全自动会员级截图采集：研究办公室可以表达证据缺口和半自动边界，但不能伪装成已完全自动。
- 新办公室批量上线：必须先通过办公室隔离、扩展治理、样例交付和安全门禁。

## 发布判断

当下面命令全部通过时，可以说当前仓库“适合公开作品集展示和本地复现”：

```powershell
python scripts/verify_productization_status.py --format markdown
python scripts/verify_model_configuration_guidance.py --format markdown
python scripts/verify_release_readiness.py --format markdown
python -m unittest discover -s tests -q
python scripts/check_no_secrets.py
```

当这些命令没有通过时，不要把当前状态说成产品化完成。
