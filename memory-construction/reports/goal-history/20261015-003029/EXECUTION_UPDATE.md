# 执行更新：memory-fast-results-v4（历史回执与当前接续）

v4 内部首表、端到端/强 B3、开发优化曲线和质量修复已经完成并保留；这些产物不再是当前外部基线门槛。父 agent 维护 `execution/ack-memory-fast-results-v4.json` 与 `STATUS.md`，本文件不重复写回执，也不把文档更新当作 Goal 已激活。

当前主线已切换为：

1. 完整 LongMemEval-V2 AgentRunbook-R Small（web + enterprise），使用完整轨迹、截图、问题、Reader、预算和冻结上游入口；
2. 紧接 RAG+Notes；
3. 沿原生写入/查询路径接入阶段计时、依赖感知调度、细粒度失效、有效复用、一致发布，并分表 B0/B1/B2/强 B3/Ours；
4. 冻结配置后，在独立数据上完成官方质量、至少 3 次重复和真实流式 Freshness P95/Goodput。

当前下一动作只恢复并独立校验 web、enterprise 两个官方截图归档（大小、SHA256、`gzip -t`），再运行 `prepare_data.py` 和 `validate_data.py`。不得用 micro/prefix、截短轨迹、占位截图、text-only 或压缩预算 smoke 升级为 native Small；Native 与 adapted-matched 必须分目录、分配置、分表。

## 2026-10-14 用户覆盖后的真实构建交付

查询侧已冻结：chunks、tokenizer reuse、lexical backfill、neighbor=0、query embedding exact reuse；O 真实计数为24→8 embedding calls、1788→596 input tokens、16 hits，8/8 prompts byte-equivalent，质量差异保留为采样波动。

构建 v1/v2 已真实运行并保留。首轨迹 joint：事件请求7→4、控制器总调用8→5、输入38824→29581；无首轨迹墙钟收益。固定10条 v2 矩阵：baseline 830.00s/93 calls/735023 input/192 vectors/7-8；joint 1025.77s/78/686954/192/7-8；embedding reuse 882.95s/97/736591/184 (8 hits)/7-8；combined 989.91s/76/666712/184 (8 hits)/6-8。所有 cells 81 events/20 notes/91 states、结构覆盖通过；V2 共享 preflight=18000、既有 bounded fallback、controller retries=0、物理 API failures=0。联合减少必要请求/tokens，但未稳定缩短 wall；embedding 是低风险向量节省；combined 不是质量约束下最终 wall winner。

局部更新已完成：从 `full10-web-combined` 独立副本重复 state/workflow 修订，并从 screen 独立副本追加真实新轨迹前缀。State revision B3→Ours 事件输出4→2，update publish22.11→12.62s，LLM input8012→3926；workflow revision均2 events+2 notes，Ours input5370 vs9458、publish21.36 vs33.81s。所有保存/加载校验通过；结果见 `results/tables/agentrunbook_update_b3_ours.csv` 与 `reports/agentrunbook_update_b3_ours.md`。

官方 Judge native reference 保持 `gpt-5.2`。截至 2026-10-14，LabForge 请求实测 HTTP 403/error1010，只能标记 `judge_unverified`/`pending_judge`；可用的 `gpt-5.6-terra` 只能单列 `adapted-matched` 或 `evaluator-only`，不能与官方 hosted QA 合并。

已有 Goal 工具状态仍为 blocked/unfinished，不能重复创建；继续沿用户最新主线推进。
