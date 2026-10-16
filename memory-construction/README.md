# Agent Memory Maintenance
协议 focused-maintenance-v4-20261015；执行修订 execution-recovery-20261016。

从 [START_HERE](START_HERE.md) 进入，研究对象是局部记忆维护的成本与质量，不扩大 baseline 或重开冷构建方法探索。

| 位置 | 唯一职责 |
|---|---|
| GOAL.md | 成果和完成条件 |
| docs/EXPERIMENT_PROTOCOL.md | 比较、质量、数据划分与公平性 |
| execution/experiment_contract.json | 已约定的运行参数、范围及审计目标 |
| execution/queue.json | 任务状态、证据、下一动作 |
| tools/focused_runtime.py | 正式入口共享配置，导入 harness 前应用 |
| execution/verify_evidence.py | 无模型调用的结构核验，不代替语义/科学审查 |
| docs/EXECUTION_RECOVERY.md | 自主诊断和最小补跑规则 |
| tools/、tests/ | 执行和必要回归检查 |
| runs/、results/、reports/、paper/ | 原始数据、派生产物、分析、稿件 |

正式主表：Raw RAG、RAG+Notes、AgentRunbook-R/B3、Ours。Source-only、Overlay 为核心机制对照；Delta Edit 优先复用。实际完整 Small 历史来自官方映射，修订与问题子集另行冻结，仍是 text-only/adapted 维护实验。

已有代码/快照不搬迁；runs/agentrunbook-r-native-small-20261014/local-text-only/ 含实际 adapter。新增共享逻辑放 tools/，不继续在 runs 内放新运行器。
长任务沿用 execution/launch_detached.sh 和 execution/background_status.sh，进程完成后还须验收产物。
