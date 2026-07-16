# AI 漫剧真实生产声明边界

这份文档说明一件很具体的事：AI 漫剧制片办公室产出一个 Word 画布和 `handoff_manifest.json` 之后，什么时候可以公开展示，什么时候只能当内部草稿，什么时候才可以说“真实模型质量已验证”。

## 一键检查

```powershell
python scripts/verify_comic_real_production_claim.py --format markdown
```

默认不传 `--manifest` 时，脚本会使用仓库里的无 Key 固定样例。这个结果应该是 `demo_structure_only`，表示它只能证明流程、引用链和交付结构可复现。

真实创作完成后，指向真实生成的 manifest：

```powershell
python scripts/verify_comic_real_production_claim.py --manifest output/你的项目/xxx_handoff_manifest.json --format markdown
```

这个脚本不调用模型，不读取密钥，只审计已经生成的交付物。

在机器可读结果里，`claim_level` 是对外声明等级，`production_quality_verified` 是能否宣称真实模型画质和生产质量已经通过验证的布尔证据。无 Key 固定样例必须保持 `production_quality_verified=False`；只有真实模型产物通过完整质量基准、视觉质检和下游交付审计后，才能变成 `production_quality_verified=True`。

报告还会输出 `claim_upgrade_checklist`。它不是宣传文案，而是补证据清单：固定样例会列出还缺真实模型图片、视觉质检和重新写入质量基准；真实质量已验证的 manifest 会提示保留证据包，并在故事、资产、模型或提示词有重大改动后重新验证。

## 图片证据恢复路径

历史追溯会输出 `image_production_evidence`，用来说明图片证据到底强到什么程度。`demo_structure_only` 通常会对应 `fixture_only`：它可以证明结构和引用链，但不能证明真实模型画质。`missing_images` 表示 manifest 或 Word 画布存在，但图片文件或图片记录不完整；`model_partial` 表示有真实模型图片，但还没有形成完整视觉质检证据；`mixed_or_unknown` 表示图片来源混杂或缺少 provider/model/review 信息。

历史追溯还会输出 `image_quality_summary`。它不是宣传分数，而是返工账本：总图片数、可用图片数、废片/返工图片数、返工率、失败图片 ID 和 `rework_instructions`。`rework_instructions` 会把每张失败图指向具体恢复方式，例如补跑视觉质检、保留提示词重新生图，或退回提示词重写。

这些状态都不能公开宣称“真实模型画质已验证”。工作台或历史页应提示使用 `regenerate_images` 恢复动作：系统保留已确认故事、资产 manifest、提示词包和旧交付记录，只清理需要重建的图片生产证据，并把项目退回图片生成和视觉质检阶段。如果当前包连提示词包都缺失，则先回到提示词规划，而不是直接生图。恢复完成后，再重新运行：

```powershell
python scripts/verify_comic_real_production_claim.py --manifest output/你的项目/xxx_handoff_manifest.json --format markdown
```

## 三种声明等级

| 等级 | 能说什么 | 不能说什么 |
| --- | --- | --- |
| `demo_structure_only` | 无 Key 样例证明流程、Word 画布、manifest、资产引用链和下游交接方式可复现。 | 不能说真实模型画质已验证，不能说人物一致性和画风一致性已经通过真实生产检验。 |
| `real_quality_verified` | 这份真实模型产物通过了制片包质量基准，可以展示为真实交付证据，并交给下游图生视频或剪辑流程继续使用。 | 不能说系统已经自动生成完整成片，不能承诺第三方视频平台一次成功。 |
| `needs_review` | 只能作为内部草稿或问题复盘材料，可以展示阻塞原因、责任部门和恢复动作。 | 不能公开宣称已可交付，不能交给下游平台当最终制片材料。 |

## 为什么要单独做声明报告

质量基准回答“结构和证据是否合格”，交付盘点回答“本地有哪些历史产物”，声明报告回答“我现在对外能怎么说”。这三者分开以后，公开展示会更诚实：

- 面试官看到的是安全的固定样例，不会误以为作者把密钥开放给了访客。
- 使用者跑真实模型后，有明确命令判断产物能不能展示。
- 后续接入真实图像模型时，不会把占位图、旧版包或未质检图片包装成生产级成果。
