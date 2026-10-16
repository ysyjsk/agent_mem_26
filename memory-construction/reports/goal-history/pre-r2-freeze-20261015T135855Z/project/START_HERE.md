# 当前入口：focused-maintenance-v4-20261015
执行修订：execution-ready-r2。
项目：/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction

1. 读 [执行更新](EXECUTION_UPDATE.md)，确认本修订和活动作业。
2. [Goal](GOAL.md) 是唯一成果定义；[Workplan](WORKPLAN.md) 和 [队列](execution/queue.json) 规定顺序/状态；[协议](docs/EXPERIMENT_PROTOCOL.md) 规定比较、准入与冻结。
3. 直接执行 [完整 Prompt](execution/prompts/CONTINUE_RESEARCH.md)，采用 [当前技能](execution/skill/memory-research-loop/SKILL.md)。
4. 先读 [复用与自主优化](docs/REUSE_AND_OPTIMIZATION.md)，核对 execution/reuse_inventory.csv 并只补 Source-only/Raw RAG/Notes 缺失维护。首表由合法旧结果＋新增结果组装。
5. [论文入口](paper/README.md) 可立即开始写作；最终匹配配置由执行会话核实，已有合法阶段不重新运行。

旧报告和 reports/goal-history/ 只作证据。不要回到 B0/kernel、P0、原生 Small 下载或新框架适配。已有代码/数据不搬迁，尤其保留 runs/.../local-text-only 的实际 adapter。
