# 从这里接续
执行修订：execution-recovery-20261016；协议仍为 focused-maintenance-v4-20261015。

1. 读 [执行更新](EXECUTION_UPDATE.md) 与 [实际队列](execution/queue.json)，短核对活动作业。
2. 按 [恢复与自主诊断](docs/EXECUTION_RECOVERY.md) 执行 [当前 Prompt](execution/prompts/CONTINUE_RESEARCH.md)。
3. 目标看 [GOAL](GOAL.md)，科学比较看 [协议](docs/EXPERIMENT_PROTOCOL.md)，实际运行配置看 [contract](execution/experiment_contract.json)。

先修评测再补缺，复用已有有效快照。不要重开方法探索，也不要依据旧 complete 标记结束。
长实验沿用 execution/launch_detached.sh；历史 runs/.../local-text-only 含实际代码，保留路径。
