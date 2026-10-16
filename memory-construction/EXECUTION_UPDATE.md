# 执行纠正：修复评测并继续正式实验
update_id: focused-maintenance-v4-20261015
update_revision: execution-recovery-20261016

先读本文件、execution/queue.json、docs/EXECUTION_RECOVERY.md，再执行 execution/prompts/CONTINUE_RESEARCH.md。研究方法、baseline 范围和 GOAL.md 总目标未改变；这不是新一轮方法探索。

已核实的问题：正式/消融 20 个实际 Reader 请求中 19 个带截图，重复 12/12 带截图；开发连续序列 36 个请求均无图。正式入口未继承原 text-only 和检索 flags。正式库每域 10 条且引用开发 Manifest，官方 Small 为每域 100 条；缺 Raw RAG/Notes 同负载维护；汇总漏 controller；Coalesced 检查把未改事实也限制在 CURRENT 块。
旧“全部完成”声明已撤回为待修复/补缺。已完成构建、更新及开发序列保留，不重新从 P0 开始。

本次已新增共享运行配置 tools/focused_runtime.py，并让正式 Reader 先加载配置再导入 harness，记录 effective_runtime.json；这仅完成代码修复和离线验证，尚未产生纠正后的 Reader 数字。execution/verify_evidence.py 可离线查实际请求、历史范围、成本分项和任务依赖；发现错误后按报告修复，不能直接停工。
第一项实际工作：短核对活动作业，运行 python3 execution/verify_evidence.py --current，确认当前待修项后，复用现有快照做两域 B3/Ours 最小配对查询（原 4 题，共 8 个回答）。先检查实际请求无图、有效配置一致，再补其他策略和正常问题覆盖。不要先重跑重复实验。

由服务器执行会话写 execution/ack-execution-recovery-20261016.json，包含 update_id、update_revision、received_at、当前作业、下一实际任务、真实查询的 native_goal_status，并确认“配置错自行修、阶段复用、不能缩库/删必需方法、负结果不等于交付完成”。
旧回执保留。当前部署不代写接收，不操作原生 Goal，不启动第二执行器。
