# 执行顺序
协议 focused-maintenance-v4-20261015；修订 execution-recovery-20261016。
任务状态只读取 [execution/queue.json](execution/queue.json)；本文件不保存另一份 done/todo。

| 阶段 | 实际动作 | 复用边界 |
|---|---|---|
| REPAIR_EVAL | 核验入口修复；离线修成本/事实检查；先 8 个 B3/Ours 回答，再补受影响策略和正常问题 | 复用现有更新快照；不重建记忆 |
| PUBLIC_BASELINES | 补 Raw RAG、RAG+Notes 更新薄接口及同负载维护查询 | 不重跑已合法的冷构建/正常 QA |
| SELECT / CONFIRM | 冻结修复后的配置与数据，补必要一致性/确认 | 已观察的两例只是修复诊断，不改称独立确认 |
| SMALL_MAIN | 实际官方 Small 历史库上的固定修订/问题；四行主表、核心消融和连续成本 | 三类初始记忆一次构建，兼容部分补缺；AR 各策略独立分支 |
| WRITE / PACKAGE | 纠正草稿结论，完成可追溯表图/复现；逐条核验 GOAL 完成条件 | 历史有效证据分版本引用 |

开发表、旧正式错误查询与纠正后的结果分开。沿用 runs/focused-maintenance-v4/；本次修复建议 runs/focused-maintenance-v4/repair-20261016/；最终扩量输出单独命名，清单放 manifests/focused-maintenance-v4/。
旧结果不覆盖。完整历史库与独立修订/问题数分别报告；正常/工作流问题不能被内部状态定位题全部替代。连续曲线按真实修订轮累计。
长任务沿用 execution/launch_detached.sh 与 background_status.sh；退出码只表示命令执行结果，不表示实验验收。
