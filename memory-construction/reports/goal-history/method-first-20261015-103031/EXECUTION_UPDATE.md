# 接续指令：先补完整 Small 本地运行（2026-10-15）

已经核对最新成果：更新、Reader、冷构建候选和真实流式探针均已产生数据，继续保留。
总 Goal 尚未完成：PAPER03 当前仍为 10 条轨迹/8 题开发汇总；Small 实际包含两个 100 条轨迹集合、共 200 条唯一轨迹和 451 个问题映射。PAPER04 的旧实现扩量及 PAPER05 的单轨迹三批探针也没有替代完整验收。
GOAL.md 已补充确切缺口，queue 的过早 done 已恢复为待完成状态；已完成阶段无需重跑。

现在优先用现有本地 runner 和完整 Small manifest 启动正式规模 Raw RAG，随后推进 RAG+Notes、AgentRunbook-R 与当前选定 Ours/强 B3。第一个 baseline 完成即接入 Ours；逐轨迹保存结果，质量与成本同表。不要再把整理旧开发表当作新的完整规模结果。
完成构建主线后补正式更新、当前方法消融扩量、同条件重复和三个真实到达负载，持续交付论文表图。普通错误继续修复，不回到新一轮计划或框架建设。
本次只修正文档与队列，没有改实验代码、原始数据或模型服务，也没有启动第二个执行器。正在执行的 VS Code 会话应核实并沿用原生 Goal；文档本身不代表已激活或已收到。

以下保留之前的目标与执行记录。

# 执行更新：完整论文实验 Goal（2026-10-15）

用户最新要求：目标仍是完成支撑论文的所有必需实验；小规模实验是中间里程碑，不能用“先做两件事”把总 Goal 缩成局部任务。

请立即读取 GOAL.md。它给出可用于原生 Goal 的 objective、PAPER01–PAPER06 完整实验包、执行顺序和完成条件。
AGENTS.md、WORKPLAN.md、execution/queue.json 已同步此优先级；旧 native-first 任务作为延期补充保存，历史结果未更改。
当前下一步仍是八个两域更新配对案例及更新后质量验证，之后连续推进完整规模对照、消融扩量、关键重复、真实流式与论文交付。
冻结查询搜索，继续有效模型服务与现有进度；不重做 P0，不启动第二个竞争执行器。

在当前执行会话沿用并核实原生 Goal。文档更新不等于 Goal 已激活；若工具无法修改/恢复，准确记录其状态，不以重复创建绕过。

2026-10-15 PAPER01/PAPER02 progress: parameterized `tools/run_agentrunbook_updates.py`, completed 8 fixed web/enterprise state/workflow pairs plus an alternating-order repeat (32 paper-facing rows after excluding the pre-fix checker rerun). All rows pass source-grounded update checks; one fixed Reader regression is complete/parseable but B3 1/1 vs Ours 0/1, retained as a quality constraint. Main table/plot: `results/tables/agentrunbook_update_main.csv`, `reports/agentrunbook_update_main.md`, `reports/agentrunbook_update_cumulative.svg`.

Cold candidate v3 completed on enterprise `0ab99e0c` and `49f98e9e`: common bounded-preflight joint 412.44s vs single baseline 741.94s, controller calls 19 vs 35 (2 baseline failures), known LLM input 209,996 vs 291,019, 14 parsed joint groups, all 29 events/source mappings and save/reload checks pass. Detailed table/report: `results/tables/construction_pair_v3_common_preflight.csv`, `reports/construction_pair_v3_common_preflight.md`. The candidate is retained for fixed-10 expansion; full PAPER03–PAPER06 remain active.

2026-10-15 continuation: `report_update_main.py` emits `reports/agentrunbook_update_fresh_comparison.svg` and embeds state-revision, full eight-case revision, and growth Reader reports. Fresh/B0 touched-partition totals for the eight fixed revisions are 1,249.20 s / 56 controller calls / 589,121 known input tokens, versus B3 227.90 s / 18 / 132,987 and Ours 206.79 s / 16 / 119,650; all 48 persisted source-grounded rows pass. The fixed state regression has 36/36 complete parseable outputs; representative enterprise state remains Fresh 2/4, B3 3/4, Ours 2/4 in both repeats. Extended B3/Ours quality regression now covers all eight revision cases: 64/64 complete/parseable, zero truncation/service/parse failures, and both methods 21/32 correct (web B3/Ours 12/16 vs 13/16; enterprise 9/16 vs 8/16). It is an adapted development proxy, not official/native QA. Per-question data: `results/tables/agentrunbook_revision_case_reader.csv`. PAPER04 report/table/figure are now generated; controlled update-rate sweep and final scale selection remain open.

PAPER01 repeat extension: completed four B3/Ours passes over the same eight state/workflow revision cases, with actual order primary B3→Ours, r1 Ours→B3, r2 Ours→B3 (retained order deviation), and r3 B3→Ours to balance order. Each pass is 8/8 source-grounded/reload checks. Aggregate B3/Ours publish seconds are 227.90/206.79, 208.82/175.02, 662.50/186.42, and 610.64/219.36. In r2/r3 B3 re-extracts 66 event outputs (37/38 calls, ~426k input tokens) versus Ours 16 (12/13 calls, ~97k tokens), while r0/r1 remain near-ties on work. Summary CSV: `results/tables/agentrunbook_update_repeat_summary.csv`; raw run directories are `runs/agentrunbook-updates-main/repeat{2,3}-*`.
在现有 STATUS 的下一次正常更新中记录已读取本目标即可，无需新建回执或控制框架。随后立即执行实验，阶段汇报给新增数字及下一项实际动作。

文档更新前的副本保存在 reports/goal-history/。本次没有修改实验代码、模型服务或已有实验结果。

2026-10-15 continuation (local text-only/adapted; do not conflate with native Small): the previously running controlled update-rate screen completed on one enterprise trajectory from the same full-10 starting snapshot. For 1/3/6 state revisions, B3 publish latency was 156.38/174.15/176.29s (7 calls, ~97.2k input tokens, 14 event outputs at every point); Ours was 23.02/45.77/87.87s (1/2/4 calls, 14,325/28,639/52,394 input tokens, 2/4/7 event outputs). All six persisted source-grounded checks pass. Paired publish-time reductions are 85.3/73.7/50.2%, LLM input-token reductions 85.3/70.5/46.1%. A fixed 4-question Reader check at 6 revisions is B3 3/4 vs Ours 2/4, both 4/4 complete with zero truncation/service/parse failures; this matches the earlier enterprise state-revision direction and does not establish per-slice QA equivalence. Raw runs: `runs/agentrunbook-update-rate-screen-v1/`; table/report/figure: `results/tables/paper04_update_rate.csv`, `reports/paper04_update_rate.md`, `reports/paper04_update_rate.svg`.

The single cold-build candidate on two long enterprise trajectories completed with the existing 18k input limit, 2,048 event-output tokens, shared 12k/state preflight and save/load publication. Baseline vs common-preflight joint: 277.40s/32 calls/283,175 LLM input/5,868 output tokens vs 274.71s/20/224,445/6,282. Joint parsed 13 groups and split one; both methods preserve all 29 source-linked action/state transitions and pass reload validation. Embedding requests were matched at 8 calls/64 vectors; embedding input tokens were 132,324 vs 131,269. This is a small call/input-work reduction with effectively tied wall time (-1.0%) and +7.1% output tokens, not a material cold-build speedup. The already measured fixed-5 common-preflight expansion remains the negative wall-time point and is reused rather than repeated. Detailed table/report: `results/tables/construction_pair_v4_common_preflight.csv`, `reports/construction_pair_v4_common_preflight.md`. The v4 single-preflight logging extension and report scripts compile; the earlier wrong-haystack Reader attempt and aborted pre-run baseline are preserved and excluded.

2026-10-15 PAPER05 real continuous-arrival probe: `tools/run_agentrunbook_stream.py` completed a closed-loop source-prefix stream on enterprise trajectory `0ab99e0c`. The target trajectory was absent from independent B3/Ours clones; batches of 1, 2 and 3 newly arrived transitions were materialized only when each batch arrived. Each batch used the real local Qwen controller and Embedding, saved a queryable snapshot, reloaded it, and ran a retrieval probe. All 6/6 source-grounded arrival checks and 6/6 reload/retrieval probes passed. B3 publish totals were 38.38/50.79/98.12s (187.30s total), 9 controller calls, 76,918 known input tokens, 9 embedding calls/16 vectors, Freshness P50/P95 74.46/98.12s, goodput 0.0320 new transitions/s. Ours was 30.37/69.00/90.97s (190.34s total), 10 calls, 77,369 input tokens, 9 embedding calls/16 vectors, Freshness P50/P95 79.98/90.97s, goodput 0.0315. The current dependency key includes full action sequence/transition count, so prefix growth causes no event reuse and Ours is not selected for this stream protocol; this is a retained mechanistic negative, not a quality failure. Table/report/figure: `results/tables/streaming_freshness_goodput.csv`, `reports/streaming_freshness_goodput.md`, `reports/streaming_freshness_goodput.svg`.
