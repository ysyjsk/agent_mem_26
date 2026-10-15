# 当前研究 Goal：原生 Small → RAG+Notes → 机制与论文评测

v4 内部首表、强 B3、质量修复和开发曲线继续作为历史证据保留；当前主线已切换为完整的 LongMemEval-V2 AgentRunbook-R Small 原生复现。GOAL.md 只记录授权与恢复点，不会自动激活会话中的原生 Goal。

## 当前执行目标

/goal 在 /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction 按 WORKPLAN.md、AGENTS.md 和 memory-research-loop 持续执行：先完成冻结 AgentRunbook-R 的 LongMemEval-V2 Small（web + enterprise）native 结果，保留完整轨迹、截图、问题、Reader、采样/思考/预算、调用与阶段计时；紧接运行 RAG+Notes；随后沿原生写入/查询路径接入依赖感知调度、细粒度失效、合法复用和一致发布，并在相同资源与预算下报告 B0/B1/B2/强 B3/Ours。冻结开发配置后，在独立数据上完成官方质量、至少 3 次配对重复和真实流式 Freshness P95/Goodput。所有失败、退化和 pending_judge 如实保留；MemForest、通用 tune/恢复框架不阻塞主线，技术错误自主修复并持续推进，满足最终论文验收前不标记完成。

已有同一研究 Goal 时延续其授权范围，不创建第二个执行器；文档更新不等于 Goal 已启用。当前 Goal 工具状态已核实为 blocked/unfinished，objective 仍为旧文本，不能通过重复 create 修复，本轮继续沿用户最新主线执行并保存恢复点。

## 已完成并必须保留的历史证据

- manifests/fastloop_dev_v1.json、results/tables/first_compare.csv、reports/first_compare.md：4 窗口 B0/Fresh 与 Ours-dev 的真实 construction-kernel 对比。
- results/tables/first_compare_e2e.csv、results/tables/dev_strong_compare.csv、results/tables/dev_iterations.csv：端到端、强 B3、优化和负结果。
- 12/24 窗口性能、H4/H5/H6、Reader 质量修复与 QA2 evaluator-only 重评分：只作开发/机制/回归证据，不替代 native Small 或官方 QA。

这些结果不能被覆盖、重跑冒充新实验，也不能把 text-only、micro/prefix、截短轨迹或压缩预算结果称为 native Small。

## 当前主线与验收

1. 恢复并独立校验 web、enterprise 的完整截图归档（大小、SHA256、gzip -t），再运行官方 prepare_data.py/validate_data.py；使用冻结上游 AgentRunbook-R、完整 Small haystack、问题和评分入口。
2. 输出 runs/agentrunbook-r-native-small-20261013/ 及逐题答案、原始调用/tokens、构建/query 阶段耗时、失败/重试、配置/代码/数据哈希。Native 与本地服务 adapted-matched 分目录、分配置、分表。
3. Native Small 完成后立即运行 RAG+Notes；随后增加原生阶段计时，完成依赖调度、细粒度失效、有效复用、一致发布，以及共享资源下 B0/B1/B2/强 B3/Ours 分表。
4. 冻结开发配置，在独立数据上完成官方质量、至少 3 次重复和流式 Freshness P95/Goodput；checkpoint latency 不得冒充 Freshness。

官方 Judge 的 native reference 保持 gpt-5.2。截至 2026-10-14，LabForge 上该请求实测 HTTP 403/error1010，只能记为 judge_unverified/pending_judge，不能改称官方 gpt-5.6 Judge。已实测可用的 gpt-5.6-terra 只能单列为 adapted-matched 或 evaluator-only，不得与 pending_judge 或官方 hosted QA 分数合并。

## 持续执行规则

不重跑 P0、不重启有效作业、不杀不明归属进程；保留失败和负结果。必要外部输入缺失时明确记录，同时继续执行不依赖它的工作。只有真实目标完成、用户暂停、宿主预算限制或所有剩余必要工作确实依赖外部输入时才结束；写完计划、回执、脚本或 smoke 通过都不算完成。
