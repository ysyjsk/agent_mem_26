# 仓库执行入口：focused-maintenance-v4-20261015

本仓库当前研究任务的唯一有效执行协议位于 memory-construction/。请先读该目录的 EXECUTION_UPDATE.md，再读 AGENTS.md、GOAL.md、WORKPLAN.md、docs/EXPERIMENT_PROTOCOL.md 和 execution/queue.json。旧 native Small 先行、流式 Freshness 优先等冲突条款已归档，不再控制本轮任务。

本轮固定局部记忆维护方法与 baseline，不新增外部框架。Source-only 一致性验证和首批配对实验先行；正式扩量在必要正确性/公平性检查通过后，以冻结的 Manifest 执行；不以胜过 Source-only 为门槛。完整 Small 历史库不等于恢复旧的原生多模态 Small 前置任务。

Git 根目录为本目录，继续使用本仓库，不使用 github-exports 作为发布工作目录。数据、模型、缓存和备份由 .gitignore 排除。结果 JSON/JSONL 的 Git clean filter 只过滤提交内容，不能据此修改或截断服务器原始结果文件。

每次向用户输出前，先用一段话简述本次动作。保留活动作业和原始结果；具体执行及原生 Goal 状态由当前服务器 VS Code 会话维护。文档同步不代表会话已接收或 Goal 已激活。
