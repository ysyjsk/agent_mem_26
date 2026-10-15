# 当前研究 Goal：原生 Small → RAG+Notes → 机制与论文评测

## 最新执行覆盖：构建必要计算（2026-10-14）

查询搜索已结束。当前进行完整轨迹上 single-event vs adjacent-pair 的真实冷构建，之后固定 10 条四格（baseline/joint/embedding-reuse/combined）和 B3/Ours 三类局部更新。保留所有必需事件、notes、索引；8 题质量是约束，不是优化排序目标。见 `runs/construction-pair-v1/`。
本轮工具核实原生 Goal 仍 paused；没有 resume 接口，未创建重复 Goal、未宣称 active 或 complete，继续当前授权下实际执行。

## 用户当前覆盖优先级（2026-10-14，本地 adapted 持续执行）

当前执行用户明确指定的 text-only/adapted 路线，不由下方历史 native 顺序阻塞。
原生 Goal 查询返回 **paused**（objective 已是当前 adapted 目标）；工具没有 resume
接口，因此不重复 create，也不把文档更新当 active。当前轮继续实际执行。

新增实测：固定 8 题、10 条完整轨迹/91 states；共同分块后的 AgentRunbook-R 与 J
均 6/8，L tokenizer 复用保持逐题 prompt 完全相同，把 prompt wall 34.32s 降至
6.09s。扩量为 20 条完整轨迹/293 states，L 构建发布 283.06s，仍 6/8。
强 B3/Ours 已接现有 core + 相同表示/模型/Reader，真实运行目录为
`runs/dev-adapted-text-v1/results/*-workflow-*-v2`，不是旧前缀数据。
随后执行有限配对/消融命令 `bash tools/run_adapted_followups.sh`。
表图与论文初稿已生成，仍随实际结果刷新；未宣称目标完成。

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

1. 已完成 web、enterprise 完整截图归档及 Small 数据校验；adapted web Small 已在
   `runs/agentrunbook-r-native-small-20261014/adapted-aliyun-vl/web/` 真实运行但因 Aliyun
   HTTP 400 `Arrearage` 在 67/100 trajectories 后失败，完整 Small 与 enterprise 仍未完成；
   失败目录保留，不把部分结果称为 R5。
2. Reader/Controller 暂以用户授权的 qwen3-vl-plus 适配 GPT，Embedding 使用本地 Qwen3-Embedding-8B，qwen-plus 仅 evaluator-only；交付逐题答案、原始调用/tokens、构建/query 阶段耗时、失败/重试、配置/代码/数据哈希。该结果标为 adapted-matched；native GPT 与官方 Judge 仍 pending。
3. Native Small 完成后立即运行 RAG+Notes；随后增加原生阶段计时，完成依赖调度、细粒度失效、有效复用、一致发布，以及共享资源下 B0/B1/B2/强 B3/Ours 分表。
4. 冻结开发配置，在独立数据上完成官方质量、至少 3 次重复和流式 Freshness P95/Goodput；checkpoint latency 不得冒充 Freshness。

官方 Judge 的 native reference 保持 gpt-5.2。截至 2026-10-14，LabForge 上该请求实测 HTTP 403/error1010，只能记为 judge_unverified/pending_judge，不能改称官方 gpt-5.6 Judge。已实测可用的 gpt-5.6-terra 只能单列为 adapted-matched 或 evaluator-only，不得与 pending_judge 或官方 hosted QA 分数合并。

## 2026-10-14 适配运行恢复点

由于 GPT Reader/Controller 当前不可用，用户已授权的阿里云兼容 Qwen 适配运行曾使用完整 Small
数据，但本次 DashScope 响应为 `Arrearage`，因此仅留下 partial adapted evidence；API key
只通过运行时环境变量传入，不写入文件。隔离 `local-text-only` runner 已可调用本地
Qwen3.5-9B/Qwen3-Embedding-8B 完成官方 schema 的 micro smoke，并写入
`adapter_provenance.json`；它明确是 `diagnostic-text-only`，不替代 native GPT、视觉 Small
或官方 Judge。官方 Judge 状态仍为 `pending_judge`；任何新完整 adapted 运行必须使用
全新目录并通过完整 gate 后才能继续 enterprise。

## 持续执行规则

不重跑 P0、不重启有效作业、不杀不明归属进程；保留失败和负结果。必要外部输入缺失时明确记录，同时继续执行不依赖它的工作。只有真实目标完成、用户暂停、宿主预算限制或所有剩余必要工作确实依赖外部输入时才结束；写完计划、回执、脚本或 smoke 通过都不算完成。
