# 执行导航
收尾指导 paper-evidence-20261016；不复制 done/todo，实时状态只看 [queue](execution/queue.json)。

| 顺序 | 接续工作 | 复用与边界 |
|---|---|---|
| A：当前正式矩阵 | 完成已登记全历史构建、四方法维护、核心消融、连续与重复 | 不重做有效修复/开发实验，不修改活动冻结输入 |
| B：独立确认与质量 | 按 [PAPER_EVIDENCE_PLAN](docs/PAPER_EVIDENCE_PLAN.md) 预选一批新修订，补正常 QA 与生成记忆核对 | 离线准备可与 A 并行；模型调用按既有单执行器顺序接续；复用完整初始快照 |
| C：论文收尾 | 正式受控结果、独立确认、机制图、质量分项和复现 | 写作同步；新旧版本及暴露状态分开，保留负结果 |

[GOAL](GOAL.md) 定义完成条件，[协议](docs/EXPERIMENT_PROTOCOL.md) 定义公平比较，[恢复规则](docs/EXECUTION_RECOVERY.md) 指导故障处理。新收尾说明不是从头重跑指令，不扩建监督平台。
