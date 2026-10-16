# 当前执行入口
协议 focused-maintenance-v4-20261015；执行修订 execution-recovery-20261016。用户最新指令优先。

最新收尾指导为 paper-delivery-20261016，见 docs/PAPER_EVIDENCE_PLAN.md：A矩阵继续；B使用maintenance-confirmation-v2的受控text字段修订，旧v1 thoughts负载不作为核心确认。仅补固定的一批维护确认与正常QA。旧“先8个回答”等恢复动作仅在对应阶段实际缺失时执行。

每次输出先用一段话讲清本次动作。从 EXECUTION_UPDATE.md 接续，不按旧报告中的完成声明停止。
- GOAL.md 定义交付，docs/EXPERIMENT_PROTOCOL.md 定义实验比较；execution/experiment_contract.json 保存可检查的运行参数与范围；execution/queue.json 是唯一任务状态。WORKPLAN/STATUS/README 只导航，不各自维护状态副本。
- 沿用 v13 局部维护和四行公开主表；Raw RAG、RAG+Notes 不可自行降为仅冷构建参考。Source-only/Overlay 是机制对照，B3 与 AgentRunbook-R 是同一公开行。完整 Small 历史范围从官方映射验证，不用开发库替代。
- 发现问题按 docs/EXECUTION_RECOVERY.md 自主定位、修复、核验、补受影响单元并继续。恢复冻结配置是修复，不是禁止的性能调参；真实负结果须在配置和指标正确后判断。
- 保留合法构建、更新快照和历史结果；仅补查询、重评分或重聚合就能解决的问题不重建记忆。文件存在、进程退出 0、检查器通过都不单独代表研究完成。
- 模型服务与实验 runner 分开；一次一个 GPU 实验执行器。不得改活动实验正在使用的代码/配置，不杀不明作业。使用已有 detached launcher，不再开发监督平台。
- 新增代码放 tools/ 或 execution/；不搬动已有 runs 内被导入的 adapter。新结果写新 run，旧结果保留并标适用范围。
- 每阶段报告新增数字/已修问题/最小重跑范围/下一已启动任务。检查失败是修复定位信息，不是立即终止任务的条件。
- 本次技能/文档部署不代表服务器会话已接收或原生 Goal 已激活。实际执行会话写新版回执并查询 Goal；负结果允许结束的前提是固定范围交付齐全。
