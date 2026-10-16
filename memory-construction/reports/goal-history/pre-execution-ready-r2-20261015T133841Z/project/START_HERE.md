# 当前入口：focused-maintenance-v4-20261015
执行修订：execution-ready-r1。
项目：/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction

1. 读 [执行更新](EXECUTION_UPDATE.md)，确认本修订和活动作业。
2. [Goal](GOAL.md) 是唯一成果定义；[Workplan](WORKPLAN.md) 和 [队列](execution/queue.json) 规定顺序/状态；[协议](docs/EXPERIMENT_PROTOCOL.md) 规定比较、准入与冻结。
3. 直接执行 [完整 Prompt](execution/prompts/CONTINUE_RESEARCH.md)，采用 [当前技能](execution/skill/memory-research-loop/SKILL.md)。
4. 第一张新增表：B3/Source-only/Ours 两域三轮；后续公开四行、独立确认、完整 Small 历史维护负载与核心消融。
5. [论文入口](paper/README.md) 可立即开始写作；方法/配置仍未正式冻结，待执行会话实际核实。

旧报告和 reports/goal-history/ 只作证据。不要回到 B0/kernel、P0、原生 Small 下载或新框架适配。已有代码/数据不搬迁，尤其保留 runs/.../local-text-only 的实际 adapter。
