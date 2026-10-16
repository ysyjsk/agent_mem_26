---
name: memory-research-loop
description: 推进 Agent Memory 项目的局部维护实验、必要修复和论文交付；按当前项目协议接续，优先真实配对成本与质量结果。
---

# 按当前协议持续推进
本技能服务项目 /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction。当前协议 focused-maintenance-v4-20261015，执行修订 execution-ready-r1。用户最新范围和项目协议优先；早期 memory-fast-results-v4、B0/kernel、native Small 先行路线已退休。

## 接续
先读项目 EXECUTION_UPDATE.md、GOAL.md、WORKPLAN.md、docs/EXPERIMENT_PROTOCOL.md 和 execution/queue.json，再做一次短作业/产物检查，避免重复服务或执行器。技能不另存完整任务表；当前最早缺失单元由真实结果与队列决定。具体入口和已知陷阱见 [project-context.md](references/project-context.md)，需要时读。

本轮首项是共同 Notes 规则与 Source-only 一致性，随后两域三轮三方开发表、同负载公开表、独立确认、完整 Small 历史维护实验和论文。完整 Small 是后续正式阶段，不是首表前置。现有架构可局部修复，不增加 baseline 或重设计方法。

## 以数字继续
假设一个主要原因 → 最小必要改动 → 配对实测 → 原始记录/表 → 决定保留或淘汰 → 执行下一项。每次一至两个因素；主要目标是更新及更新＋查询成本，质量是约束，不要求单题涨分、全零调用或预定胜出。Source-only 正常检索新 Raw State，公共优化与缓存条件同等提供。
任务验收看真实产物和协议条件，不看文件是否存在。有效旧结果仅在输入/语义/配置匹配时复用；首表是开发表，不代替正式主表。Manifest 数据选择先于确认分数，运行配置在执行前冻结；修复保留版本和暴露记录。

## 修复与资源
保留成功单元，失败留档、定位并修复后续跑；不机械重试相同错误、不重建环境、不扩建监督/恢复框架。非必要准备约二十分钟仍无进展时回到下一张表的必要动作，此检查点不是实验超时。
一次一个 GPU 实验执行器；模型服务不等于实验 runner，不杀不明作业、不改活动实验配置。等待期间做相关 CPU 适配、聚合和写作。缺 Judge 保留 pending 并继续可靠可评分项目与成本实验，不能宣称质量已通过。
连续两轮同类候选无效，改查另一有证据瓶颈或简化无效部分；不得按结果改确认样本、削弱对照或隐藏失败。一次错误/负结果不自动结束仍可执行的工作。

## 交接与 Goal
每次输出先简述动作，然后报告新增数字、原因、决定与下一实际动作。Skill/Goal 文件不会唤醒会话，也不等于原生 Goal 已激活。由实际执行会话写当前 update_id＋update_revision 的接收记录并查询原生 Goal；无目标且支持时按 GOAL.md 创建，相符则延续，受宿主限制时如实记录，不把未完成目标伪标 complete 或启动第二执行器。
预算/暂停/blocked 按宿主规则；仍有可执行授权工作就继续，结束前保存真实进度和精确下一动作，不把“计划已写完”当研究完成。
