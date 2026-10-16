# 当前项目入口与已核实陷阱
协议 focused-maintenance-v4-20261015；execution-ready-r2-freeze。此文件提供路径，不另定任务次序。

- 项目：/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction；SSH ly@zjuaces-gw。
- 已验证解释器：/data/predator/ly/Mem/.venv/bin/python；模型在 /data/predator/ly/Mem/models/，实际服务和请求配置以运行时核对为准，不照搬历史 GPU 编号/thinking 默认值。
- tools/run_agentrunbook_updates.py：当前维护入口；测试 tests/test_agentrunbook_update_dependencies.py。当前旧 Notes 行缺席规则和保护它的测试必须一同改正，不能只为绿测试保留无效假设。
- tools/run_method_v13_sequence.py：历史两域三轮逻辑/命令参考，其 RUN/POLICIES 写死旧路径；新实验要新输出，不能直接覆盖历史。
- runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py：实际 adapted 评测入口；该 runs 子目录含可导入代码，禁止当无用结果搬走。
- 开发数据：runs/dev-adapted-text-v1/data；已有序列 runs/method-first-20261015/v13-sequential；正式 Small 数据 third_party/LongMemEval-V2/data/longmemeval-v2/。初始库完整性与合法快照由执行会话核实。
- 旧 src/workflow_memory、tools/run_dev_reader.py 和旧 workflow_b3 不是当前 AgentRunbook-R/B3 的默认入口，不因看到未实现 tune 而重回旧框架。
- 可选监督器实际在 execution/research_loop.py：在项目根目录可用 python3 execution/research_loop.py --root . inspect。其旧实现检查仅作观察，不能覆盖当前队列；无需修复无关历史缺口。
- 新路径和数据/运行 Manifest 条件集中在 WORKPLAN.md 与 docs/EXPERIMENT_PROTOCOL.md，不复制另一套协议。

- 实验复用与自主优化唯一细则：docs/REUSE_AND_OPTIMIZATION.md；清单 execution/reuse_inventory.csv。先前序列/确认多为 a04bcf7c… 核心，不能因新加策略改变整体哈希判废。
- 历史表：results/tables/dev_adapted_first_compare.csv、method_focused_main.csv、method_v13_sequence.csv、method_v13_confirmation.csv、method_v13_repeats.csv。汇总表指回原始 run；method_focused_main 的聚合行不是额外独立重复。
