# 当前执行：分支取舍＋外部开发首表

2026-10-15；GOAL.md为总目标。旧完整计划见 reports/goal-history/external-method-selection-20261015/。

| 任务 | 状态 | 下一实际动作与决策 |
|---|---|---|
| METHOD01可信起点 | 完成，复用 | matched两域快照及合法缓存，不重做 |
| METHOD02分支比较 | 执行中 | 先跑已有v12 reply/count三方正常检索→Reader，再补Title/sort及预选新修订；依据事件/notes和Reader决定overlay/edit取舍 |
| EXTERNAL01开发首表 | 执行中 | MemForest共享每域5完整轨迹/4题，现有HTTP服务，保留原算法；统一Reader预算与评分，纳入Raw RAG、RAG+Notes、AgentRunbook-R及当前方法 |
| METHOD03新样本/累计维护 | 待首表 | 预选未调参问题；同库多轮更新/查询，核算初始+维护+查询，不以独立快照冒充流 |
| FREEZE | 未满足 | 外部强对照、正常质量、关键三次配对、新样本、累计成本、关键消融均支持后冻结 |
| PAPER | 待冻结自动接续 | 正式主表/消融/扩量/质量稳定性、论文表图章节和复现；出现实质退化回方法改进 |

当前主要成本指标：更新总LLM tokens；发布墙钟、Embedding、失败与查询增量全部并列。候选最多两个，不扫查询参数。冷构建复用历史必须标注，不把旧Ours当当前版本。
当前低成本主候选v12 source_overlay仅通过两例固定题正常回归；更新0LLM，三方均7/8且完整。delta_guarded转为失效结论上的语义修复对照。四例修订值完整检索、连续更新、外部确认仍缺，不冻结。

运行入口：tools/run_agentrunbook_updates.py、tools/run_method_v12_normal_readers.sh、tools/run_memforest_local_smoke.py及最小共享库适配；原始产物沿用runs，决策追加reports/optimization_log.md。无新框架或执行器，GPU串行。原生Goal实际blocked，接口无resume；文档不假称active。
