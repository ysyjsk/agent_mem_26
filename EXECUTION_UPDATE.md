# 执行更新：memory-fast-results-v4（历史回执与当前接续）

v4 内部首表、端到端/强 B3、开发优化曲线和质量修复已经完成并保留；这些产物不再是当前外部基线门槛。父 agent 维护 `execution/ack-memory-fast-results-v4.json` 与 `STATUS.md`，本文件不重复写回执，也不把文档更新当作 Goal 已激活。

当前主线已切换为：

1. 完整 LongMemEval-V2 AgentRunbook-R Small（web + enterprise），使用完整轨迹、截图、问题、Reader、预算和冻结上游入口；
2. 紧接 RAG+Notes；
3. 沿原生写入/查询路径接入阶段计时、依赖感知调度、细粒度失效、有效复用、一致发布，并分表 B0/B1/B2/强 B3/Ours；
4. 冻结配置后，在独立数据上完成官方质量、至少 3 次重复和真实流式 Freshness P95/Goodput。

当前下一动作只恢复并独立校验 web、enterprise 两个官方截图归档（大小、SHA256、`gzip -t`），再运行 `prepare_data.py` 和 `validate_data.py`。不得用 micro/prefix、截短轨迹、占位截图、text-only 或压缩预算 smoke 升级为 native Small；Native 与 adapted-matched 必须分目录、分配置、分表。

官方 Judge native reference 保持 `gpt-5.2`。截至 2026-10-14，LabForge 请求实测 HTTP 403/error1010，只能标记 `judge_unverified`/`pending_judge`；可用的 `gpt-5.6-terra` 只能单列 `adapted-matched` 或 `evaluator-only`，不能与官方 hosted QA 合并。

已有 Goal 工具状态仍为 blocked/unfinished，不能重复创建；继续沿用户最新主线推进。
