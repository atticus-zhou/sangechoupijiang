# AI 漫剧真实运行证据收口单

这份文件解决一个很具体的问题：当 AI 漫剧制片办公室真的调用了图片生成、视觉理解和文本模型以后，项目负责人应该凭什么判断“这份制片包可以给下游视频平台继续做”，而不是只凭页面看起来热闹。

公开无 Key 样例只能证明结构、引用链和交付格式。真实生产质量必须等一次真实模型运行结束后，再用这份收口单验收。没有通过之前，任何页面、README、演示稿和历史记录都只能说 `demo_structure_only`、`model_reviewed` 或 `evidence_missing`，不能说 `real_quality_verified`。

## 使用时机

1. 用户确认完整故事。
2. 中书省和门下省完成资产拆解，用户审核人物、道具、场景是否来自故事本身。
3. 工部开始生成基础资产图和镜头参考图。
4. 刑部逐张做视觉质检，判断是否保持故事风格、人物身份和干净背景。
5. 兵部生成导演式提示词，绑定参考图、人物动作、台词、镜头语言和负面提示词。
6. 礼部组装 Word 制片画布、handoff manifest、trace bundle 和 production acceptance card。
7. 用户或开发者运行本收口单对应的检查，再决定是否允许对外宣称真实生产质量。

真实产物检查命令：

```bash
python scripts/verify_comic_real_run_evidence_intake.py --manifest output/你的项目/xxx_handoff_manifest.json --format markdown
```

这条命令不调用模型，只读取已经生成的 `handoff_manifest.json`、它引用的 Word 画布和清单里的图片/质检记录。它会同时跑生产质量基准、公开声明边界和下游交接验收，并输出：当前是 `real_quality_verified`、`demo_structure_only` 还是 `needs_review`；缺的是模型证据、图片证据、七维视觉质检、提示词谱系，还是 Word/manifest/trace 对不上。

## 必须提交的证据

真实运行后，`handoff_manifest.json`、`trace.json`、`production-acceptance.json` 和 `word_canvas.docx` 必须能互相对上。最低证据包括：

- `workspace_id`、`task_id`、`office_id=comic_production`，证明没有串到研究办公室或旧 AI 漫剧办公室。
- `model_evidence`，列出工部、刑部、兵部实际使用的 provider、model、request_id 或等价 trace id。
- `image_production_evidence`，每张图都要有 `image_id`、`asset_id` 或 `shot_id`、文件路径、生成模型、生成时间和非 fixture 标记。
- `image_quality_summary`，列出 total、usable、waste_or_rework_images、failed_image_ids、rework_instructions。
- `asset_identity_cards`，人物、道具、场景都有稳定身份卡，后续所有图片和提示词只引用这些身份卡。
- `reference_asset_chain`，每个镜头说明用了哪些人物图、道具图、场景图或首帧参考图。
- `prompt_strategy_lineage`，证明基础资产提示词、镜头提示词和 Word 画布来自同一版提示词策略。
- `downstream_handoff_decision`，明确 `handoff_allowed` 是否为 true，以及不能交付时下一步该做什么。

## 图片资产验收

人物资产和道具资产默认应该是干净白底或极简背景，不讲故事、不加剧情动作。它们的任务是当作“身份证”和一致性参考，而不是当作成片画面。

- 人物：至少包含人物三视图、人物表情表、可复用半身或全身参考图。脸型、发型、年龄感、服装主色、材质和标志性细节必须稳定。
- 道具：至少包含白底产品图或设定图、必要的细节图。不能把古风道具生成成现代物件，也不能凭空添加故事里不存在的道具。
- 场景：至少包含广角图和俯视图或空间关系图。场景可以有氛围，但必须服务后续分镜定位，不能只是一张漂亮背景图。
- 镜头参考图：可以带人物动作和情绪，但必须引用已经通过审核的人物、道具、场景身份卡。
- 废片：任何脸型漂移、服装漂移、风格不符、时代错置、多余肢体、背景破碎、文字水印、资产缺失都必须进入 `waste_or_rework_images`。

## 提示词验收

提示词不能只是固定模板堆词。每个镜头提示词都应该像导演交代现场一样，包含这一镜为什么存在、谁在做什么、镜头怎么看、观众应该感到什么。

每条镜头提示词必须包含：

- 镜头目的：这一镜推动了哪个剧情节点或情绪变化。
- 参考链路：首帧参考图、人物图、道具图、场景图分别引用哪个 `image_id`。
- 摄影计划：景别、视角、机位、运动方式、镜头时长或节奏。
- 人物表演：动作、眼神、表情、语气、台词或沉默。
- 美术与光线：画风、时代、材质、色彩、光源和空间气氛。
- 连续性要求：人物身份、服装、道具位置、场景方向、上一镜到下一镜的承接。
- 负面提示词：放在最后，用“禁止...”表达，不夹在正文里，不写读不出来的碎词。

## Word 画布验收

`word_canvas.docx` 不是普通报告，而是给 Libtv、小云雀或其他视频平台继续生产的制片画布。它必须让人一眼看出“哪张图服务哪个镜头，哪个镜头使用哪些资产，哪段提示词对应哪个画面”。

必须包含：

- 故事合同：已确认故事、不可改动的主角、冲突、结尾方向。
- 资产身份证：人物、道具、场景的身份卡和图片索引。
- 图片联系表：每张图的 `image_id`、用途、状态、是否通过刑部质检。
- 镜头卡：镜头编号、剧情功能、参考图、画面说明、视频提示词。
- 提示词包：基础资产提示词和镜头视频提示词分开呈现。
- 质检记录：刑部逐图意见、废片数量、返工指令。
- 追溯附录：`handoff_manifest.json`、`trace.json`、production acceptance card 的关键字段摘要。

## 失败恢复

真实运行失败时，不能让用户重新开盲盒。恢复动作必须保留已经确认的人类意图，清掉坏证据，再从正确阶段继续。

- 如果图片质量失败：使用 `regenerate_images`，保留故事、资产拆解、提示词策略和旧 Word 归档，清掉 fixture 或失败图片证据，回到工部重新生成，再交给刑部复审。
- 如果资产拆解失败：退回中书省和门下省，只重做人物、道具、场景拆解，不改已确认故事。
- 如果提示词失败：退回兵部，保留已通过的基础资产图和刑部质检结果，重写导演式镜头提示词。
- 如果 Word 画布缺失：退回礼部，只重建 Word、manifest 和 trace，不重新生成图片。

如果真实运行结束后不确定卡在哪里，先运行：

```bash
python scripts/verify_comic_v2_downstream_handoff.py --manifest output/你的项目/xxx_handoff_manifest.json --format markdown
python scripts/verify_comic_real_production_claim.py --manifest output/你的项目/xxx_handoff_manifest.json --format markdown
python scripts/verify_comic_real_run_evidence_intake.py --manifest output/你的项目/xxx_handoff_manifest.json --format markdown
```

第一条看下游能不能接手，第二条看对外能怎么说，第三条把真实运行证据做总收口。三条都不读取 API Key、不调用真实模型，只审计已经落盘的交付物。

## 对外声明规则

只有同时满足以下条件，才允许把这次产物标成 `production_quality_verified=true`：

- 图片证据不是 fixture，且每张图绑定真实 provider/model/image_id。
- `image_quality_summary.waste_or_rework_images=0`。
- 刑部视觉质检显示所有基础资产和镜头参考图通过。
- 兵部提示词质量为 ready，且没有固定模板式重复问题。
- Word 画布、handoff manifest、trace bundle 和 production acceptance card 字段互相一致。
- `downstream_handoff_decision.status=ready_for_downstream` 且 `handoff_allowed=true`。
- `python scripts/verify_comic_real_run_evidence_intake.py --format markdown`、`python scripts/verify_comic_real_production_claim.py --format markdown`、`python scripts/verify_comic_v2_production_benchmark.py --format markdown`、`python scripts/verify_comic_v2_downstream_handoff.py --format markdown` 和 `python scripts/verify_release_readiness.py --format markdown` 全部通过。

对于真实项目，必须把 `--manifest output/你的项目/xxx_handoff_manifest.json` 加到前三条制片包检查命令上；不带 `--manifest` 时检查的是公开无 Key 固定样例，只能证明结构演示没有坏。
