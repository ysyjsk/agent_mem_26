# 执行计划：focused-maintenance-v4-20261015
执行修订：execution-ready-r2-freeze。成果见 GOAL.md，比较/准入/Manifest 见 docs/EXPERIMENT_PROTOCOL.md，实际状态以 execution/queue.json 与原始记录为准。

| ID | 依赖 | 交付和下一动作 |
|---|---|---|
| EVIDENCE | 无 | 已有版本化 v13 序列/重复/确认保留；是历史证据，不代表最终版本已测。 |
| ALIGN | EVIDENCE | 完成：已写接收回执、原生 Goal 查询为 null、复用清单已核对。 |
| SOURCE_ONLY | ALIGN | 完成：Source-only 实际保存/重载/查询准入通过，首轮 0 更新 LLM、2.206s、2/2 Reader。 |
| PUBLIC_BASELINES | SOURCE_ONLY | 暂缓：不阻塞当前正式 Small；历史 Raw RAG/Notes 结果保留，维护接口仍记录缺口。 |
| SELECT | SOURCE_ONLY、PUBLIC_BASELINES | 完成：关闭不安全 Notes 行缺席复用，冻结 B3/Source-only/Coalesced、Reader/检索/预算与正式 Manifest。 |
| CONFIRM | SELECT | 完成：固定开发序列 18 单元已跑通；Source-only 质量波动保留，不以胜过它为扩量门槛。 |
| SMALL_MAIN | CONFIRM 且必要一致性/公平性通过 | 进行中：两域完整 10 轨迹历史库；web 全库构建进行中，随后跑正式 B3/Source-only/Coalesced 维护查询。 |
| WRITE | 无 | 现在写方法和设置，随实验更新结果；不阻塞首表。 |
| PACKAGE | SMALL_MAIN、WRITE | 最终主表、核心消融、连续更新图、确认、正文和复现核对；达标才结束。 |

## 第一项实际工作
先读当前作业与已完成阶段，不重做 P0。短核对并更新 execution/reuse_inventory.csv，先输出已有/缺失/新增计算，不等全历史审完才补明确缺项。检查 tools/run_agentrunbook_updates.py 的 Notes 追加规则及 tests/test_agentrunbook_update_dependencies.py 中对应测试；按新协议修正后实现 Source-only。沿用现有 runner/adapter 和已有序列数据，不直接运行写死旧输出路径的序列脚本覆盖历史。
四项一致性检查通过，运行一个真实修订＋正常查询，该单元可计入缺失六轮，再补剩余单元。首张表包含三个方法；旧 B3/Ours 只有输入、语义、配置和合法缓存一致时才复用，否则仅补缺失的匹配运行。

## 数据、冻结与扩量
- 起点：runs/dev-adapted-text-v1/data 和 runs/method-first-20261015/v13-sequential；已有八道正常问题按所需最终快照回归，不在无关中间版本全部重跑。
- 已有 v13 confirmation 按原版本/当时暴露状态先核对复用，不称本轮新 held-out。仅必要新增确认在看分数前冻结；未变化且已有证据充分的部分不重复确认。
- 先固定数据选择，再固定最终代码/实际模型配置；修复产生新 Manifest，不覆盖旧清单。具体字段见协议。
- 扩量只要求必要一致性/公平性、有效模型请求与真实更新查询链路通过，并冻结正式清单。成本高低、答错或 Source-only 持平是待报告结果，不是停止或继续调参的理由。
- 明确实现错误修复后自动进入 SMALL_MAIN，无需再次批准。确认中的方法局限如实记录，不自动回 SELECT；若根据其结果改方法，该样本标已暴露，必要的新确认另选未暴露数据。
- SMALL_MAIN 使用现有 Small 数据固定历史库与修订/查询子集。先依据实测吞吐估算初始构建时间/资源，复用合法构建；不得静默缩库仍称完整 Small。
- 不要求正式每个案例三次。预选代表案例完成至少三次配对计时；相符的有效旧重复可计入。
- 同时一个 GPU 实验执行器；等待期间进行必要 CPU 适配、汇总和写作。成功阶段保留，失败单元修复后续跑，实际重试成本保留。

## 复用与自主优化
执行 [复用与自主优化](docs/REUSE_AND_OPTIMIZATION.md)。十八个维护单元是初始缺口估计，不是调用数；每次重跑填具体原因，按阶段依赖补最小范围。评分变更优先重评保存答案，历史构建/查询不拼成不兼容生命周期。
Ours 的可选候选默认不执行，全程最多两个且只在正式冻结前，能立即验证且不延误主线才做；无效则保留可靠 v13，禁止换对象重新计数。冻结 Reader/检索/评分，不把通用查询调参作为 Ours 收益。正式结果正负都进入完整交付。

## 输出位置
- 新运行：runs/focused-maintenance-v4/<stage>/<run-id>/
- 冻结清单：manifests/focused-maintenance-v4/，由执行会话实际核对/生成；本次没有代写已冻结清单。
- 开发汇总：results/tables/focused-maintenance-v4/dev/{source_only_compare,public_main}.csv
- 确认：results/tables/focused-maintenance-v4/confirmation.csv
- 正式：results/tables/focused-maintenance-v4/{public_main,source_only_compare,ablation}.csv，标记 full_small_history 与实际 revision/query 子集。
- 图：results/figures/focused-maintenance-v4/；正文：paper/manuscript.md；复现：paper/reproduction.md。
旧 runs、tools、third_party、结果不搬迁。尤其 runs/agentrunbook-r-native-small-20261014/local-text-only/ 是正在被导入的 adapter 代码，不能当作可删除的旧运行缓存。
