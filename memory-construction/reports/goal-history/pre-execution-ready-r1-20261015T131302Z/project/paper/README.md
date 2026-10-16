# 论文工作区
执行版本：focused-maintenance-v4-20261015。

暂定主题：Efficient Agent Memory Maintenance through Source-Grounded Incremental Updates。
范围固定为局部源证据修订，最终标题与贡献随真实对照结果收敛，不宣称冷构建或自然增长提速。

## 写作顺序与交付
1. manuscript.md：现在写问题定义、方法、实验设置；结果段随真实主表更新。Source-only 若持平，则据此简化贡献表述。
2. 方法节明确三部分：影响定位/合法复用、绑定状态角色的当前证据维护、必要再生成与回退；不要把全部收益归给合并。
3. 实验节引用公开四行主表、B3/Source-only/Ours 机制表、合并/编辑消融、序列成本与证据大小、未调参确认。成本与质量分列。
4. reproduction.md：最终实际命令、环境/配置、输入清单、版本、原始路径、汇总方法。未测内容留为待完成项，不能填预计数字。
5. 结果图至少包括实际累计更新＋查询成本与证据大小；已有配对重复可作为误差/范围数据，独立样本与重复分开。
这些文件由执行会话实际写作时创建，本次没有用占位正文冒充稿件完成。

## 现在可用的材料
| 现有路径 | 可用范围 |
|---|---|
| ../results/tables/method_v13_sequence.csv | 已测两域三轮序列；原代码版本 |
| ../results/tables/method_v13_repeats.csv | 同一 v13 核心成本重复；不是新增问题 |
| ../results/tables/method_v13_confirmation.csv | 两条确认轨迹的窄 QA/成本 |
| ../results/tables/method_v12_branches.csv | 早期 overlay/edit 比较，不冒充最终 v13 |
| ../results/tables/method_v11_repeats.csv | 局部编辑对照重复 |
| ../reports/method_v12_quality_review.md | 已有事件/笔记质量检查 |
| ../reports/construction_cost_paper_draft.md | 历史写作素材；不直接当最终稿 |
| ../results/tables/method_external_dev.csv | 历史公开方法结果；不能代替本轮同负载主表 |

## 最终图表接口
来自 ../results/tables/focused-maintenance-v4/ 的 public_main.csv、source_only_compare.csv、ablation.csv、confirmation.csv；图在 ../results/figures/focused-maintenance-v4/。
每张最终表保留来源与版本字段，显示零 LLM 之外的实际 Embedding/查询开销。不能拼接不同版本形成一套从未执行的最终方法。
