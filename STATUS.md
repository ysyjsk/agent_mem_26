# 当前执行状态：内部 v4 结果保留，转入官方 AgentRunbook-R Small 原生复现

- 当前主线：冻结 LongMemEval-V2 官方 AgentRunbook-R 完整 Small（web + enterprise）；内部 H4/H5/H6 和 18 题保留为开发/机制/回归证据，不再作为主目标。
- 官方截图归档正在由 Hugging Face `snapshot_download`（PID 2568699/2568703）恢复，网络下载不占 GPU；本地 web archive 已证实截断，enterprise archive 缺失。
- 数据恢复完成后先执行官方 `prepare_data.py --mode symlink` 与 `validate_data.py --tier small --check-screenshots`，再启动 native Small；smoke/micro/prefix/text-only 不计完成。

- 首表：`memory-construction/results/tables/first_compare.csv` 已由 B0/Fresh 与 Ours-dev 真实生成；随后 e2e、B3、H2/H3 与 12/24 窗口扩量均已保留。
- 24 窗口最新真实表：`memory-construction/results/tables/dev_scale24.csv`；B0/Ours/B3 均180/180 checkpoint成功，Ours 对 B3 仍约慢0.47%。
- 首轮 Reader 质量代理已完成但分数低，未评官方 QA；当前修复目标是步骤检索错位、失败/状态信息遗漏及 state/workflow/index 没有进入 Reader。
- H4a/H4b 已完成固定快照质量修复；QA2 源 run `memory-construction/runs/dev-reader-v4-quality-v3-qa2-20261013` 的 90 次 Reader 调用已完成，evaluator-only rescore 仅修正 5 个布尔/字符串评分，不新增模型调用。按 exact_field/semantic 分区追加到 `memory-construction/results/tables/dev_quality.csv`，H4b 三方法均 14/14 exact-field、4/4 semantic；official QA 仍 `not_evaluated`。
- 质量聚合与 provenance 见 `memory-construction/reports/dev_quality.md`、`memory-construction/reports/quality_repair_log.md`；当前累计真实 Reader source calls 246/246，QA2 分区行不重复计数。
- 下一动作：CPU 验收 temporal/collect 修改和测试，随后在既有快照上真实复测时序候选，再做带版本哈希的证据保真候选配对测量。
- 延后：MemForest、长链路原生适配、全量截图、通用 tune/恢复/报告框架。已有产物保留。
- 活动作业仍由服务器 VS Code 执行者管理，本次未中断实验或修改研究源码/runtime。
- 接收状态：以 execution/ack-memory-fast-results-v4.json 为准；仅部署文件不表示会话已经读取。

历史状态已备份，后续只更新本文件的当前事实；不要重复旧的“无模型/无数据”判断。
