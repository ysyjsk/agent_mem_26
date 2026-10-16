# 执行计划：focused-maintenance-v4-20261015
执行修订：execution-ready-r1。成果见 GOAL.md，比较/准入/Manifest 见 docs/EXPERIMENT_PROTOCOL.md，实际状态以 execution/queue.json 与原始记录为准。

| ID | 依赖 | 交付和下一动作 |
|---|---|---|
| EVIDENCE | 无 | 已有版本化 v13 序列/重复/确认保留；是历史证据，不代表最终版本已测。 |
| ALIGN | EVIDENCE | 执行会话接收，检查当前作业，关闭不安全 Notes 规则并修正对应旧测试，登记实际代码与共同配置；预选确认数据。 |
| SOURCE_ONLY | ALIGN | 最小分支＋四项一致性检查，先真实单修订/查询，再完成两域各三轮 B3/Source-only/Ours 配对表。 |
| PUBLIC_BASELINES | SOURCE_ONLY | Raw RAG/Notes 薄更新适配，同负载四行开发对照；CPU 适配可在 ALIGN 后准备，GPU 首表仍先 Source-only。 |
| SELECT | SOURCE_ONLY、PUBLIC_BASELINES | 据成本/错误样例必要修复或简化，固定候选；代码正确性修复不必等待所有 baseline 完成。 |
| CONFIRM | SELECT | 预先选定未调参轨迹与多类型修订确认；必要正常问题回归和代表计时，输出扩量判断。 |
| SMALL_MAIN | CONFIRM 且扩量条件成立 | 完整 Small 历史库＋固定维护负载四行主实验；初始构建一次、复用合法快照；同核心修订子集完成 Source-only/Overlay/Delta Edit。 |
| WRITE | 无 | 现在写方法和设置，随实验更新结果；不阻塞首表。 |
| PACKAGE | SMALL_MAIN、WRITE | 最终主表、核心消融、连续更新图、确认、正文和复现核对；达标才结束。 |

## 第一项实际工作
先读当前作业与已完成阶段，不重做 P0。检查 tools/run_agentrunbook_updates.py 的 Notes 追加规则及 tests/test_agentrunbook_update_dependencies.py 中对应测试；按新协议修正后实现 Source-only。沿用现有 runner/adapter 和已有序列数据，不直接运行写死旧输出路径的序列脚本覆盖历史。
四项一致性检查通过，立即运行一个真实修订＋正常查询，随后补全已有六轮。首张表包含三个方法；旧 B3/Ours 只有输入、语义、配置和合法缓存一致时才复用，否则仅补缺失的匹配运行。

## 数据、冻结与扩量
- 起点：runs/dev-adapted-text-v1/data 和 runs/method-first-20261015/v13-sequential；已有八道正常问题按所需最终快照回归，不在无关中间版本全部重跑。
- ALIGN 阶段在查看确认分数之前选定确认轨迹/修订/问题，说明完整性、覆盖和既往暴露；已有 v13 confirmation 不能再次称新 held-out。
- 先固定数据选择，再固定最终代码/实际模型配置；修复产生新 Manifest，不覆盖旧清单。具体字段见协议。
- CONFIRM 不是一张 CSV 存在就放行。需要 Source-only 检查正确、相对 B3 可重复降本、没有未修复的系统性质量退化，并能解释对低成本对照的实际价值。准确率上涨不作为条件。
- 首轮/确认问题未解决时留在 SELECT 修复；队列记录继续任务，不把所有未过关工作永久 deferred。通过后自动进入 SMALL_MAIN，无需再次等待用户批准。
- SMALL_MAIN 使用现有 Small 数据固定历史库与修订/查询子集。先依据实测吞吐估算初始构建时间/资源，复用合法构建；不得静默缩库仍称完整 Small。
- 不要求正式每个案例三次。预选代表案例完成至少三次配对计时；相符的有效旧重复可计入。
- 同时一个 GPU 实验执行器；等待期间进行必要 CPU 适配、汇总和写作。成功阶段保留，失败单元修复后续跑，实际重试成本保留。

## 输出位置
- 新运行：runs/focused-maintenance-v4/<stage>/<run-id>/
- 冻结清单：manifests/focused-maintenance-v4/，由执行会话实际核对/生成；本次没有代写已冻结清单。
- 开发汇总：results/tables/focused-maintenance-v4/dev/{source_only_compare,public_main}.csv
- 确认：results/tables/focused-maintenance-v4/confirmation.csv
- 正式：results/tables/focused-maintenance-v4/{public_main,source_only_compare,ablation}.csv，标记 full_small_history 与实际 revision/query 子集。
- 图：results/figures/focused-maintenance-v4/；正文：paper/manuscript.md；复现：paper/reproduction.md。
旧 runs、tools、third_party、结果不搬迁。尤其 runs/agentrunbook-r-native-small-20261014/local-text-only/ 是正在被导入的 adapter 代码，不能当作可删除的旧运行缓存。
