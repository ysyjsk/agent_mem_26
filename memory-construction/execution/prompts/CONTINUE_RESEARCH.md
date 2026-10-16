# 接续执行：先纠正实际配置，再完成既定实验
协议 focused-maintenance-v4-20261015；执行修订 execution-recovery-20261016。
项目 /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction。

读取 EXECUTION_UPDATE.md、execution/queue.json、docs/EXECUTION_RECOVERY.md 与当前 memory-research-loop 技能。延续已有成果，不重新规划 Methodology，不重跑全部冷构建。GOAL.md 的正式交付仍有效。

先短查作业并运行 python3 execution/verify_evidence.py --current；报告非零表示待修证据，不是停止指令。根据原始请求/源数据自行区分配置错误、计量/检查器错误、实现错误和真实负结果；定位后最小修复、验证并接着执行，不仅汇报问题。常规修复和阶段级补跑已授权。

正式 Reader 已改为通过 tools/focused_runtime.py 读取 execution/experiment_contract.json，在导入 harness 前启用 text-only/共同检索配置并记录生效环境。尚未运行真实修复验证。第一项交付是复用已有两域 B3/Ours 更新快照，对原四题产生共 8 个回答；核对实际 messages 无图及有效参数一致后，再补其他方法的受影响查询/正常问题。输出新路径，保留旧记录。

同时离线修复成本漏计和质量检查。总 LLM 必须含更新、retrieval controller、Reader；失败/重试未知 usage 不填零。将改后事实、未改事实、旧值被误当当前值分别核验；不得通过放松检查直接宣布质量保持。仅修改计量或评分时重聚合/重评，查询错误只补查询，真实维护错误才补受影响更新链。

随后补 Raw RAG/RAG+Notes 同负载维护对照，完成真实完整 Small 历史上的固定修订和问题集合、核心消融、连续累计曲线、必要重复及论文。每域 10 条是开发库；完整历史按官方映射和实际加载快照核对。独立修订数、问题数、重复数分别报告。四行主表不能被三种内部策略或冷构建参考替代。

继续冻结 v13 主方法；不以 Ours 胜过 Source-only 为扩量条件。恢复冻结配置属于必要修复；配置正确后仍差则保留负结果并完成其余交付，不无限调参。正式数据参与方法修复时记录版本/暴露，不能仍称独立确认。

更新 queue/reuse inventory 和论文的实际证据；每轮给新增数字、修复原因、保留阶段及下一项已启动任务。成功退出或文件存在不等于研究完成，必需任务不得擅自 deferred。等待 GPU 时处理相关离线聚合/写作，不新建监督平台或第二执行器。

在 execution/ack-execution-recovery-20261016.json 写真实接收回执并查询本会话原生 Goal。若旧 Goal 已完成，按用户本次纠正请求创建“修复评测并补齐 GOAL.md 剩余证据”的后续 Goal；有未完成目标则按宿主能力延续，不伪标完成以换名。工具不可用时如实记录并继续授权工作。不要只回复计划，立即接续上述首项。
