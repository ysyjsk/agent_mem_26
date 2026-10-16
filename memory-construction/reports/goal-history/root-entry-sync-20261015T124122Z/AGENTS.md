# 当前目录已直接连接研究 Git 仓库（2026-10-15）

Git 根目录为本目录，远端为 git@github.com:ysyjsk/agent_mem_26.git，分支 main。直接在本目录提交，不再使用 github-exports 作为发布工作目录。
当前研究总目标和优先级以 memory-construction/GOAL.md、memory-construction/AGENTS.md 和 memory-construction/execution/queue.json 的最新条款为准；下方旧 native-first 条款仅作历史记录。
数据、模型、缓存和备份由 .gitignore 排除。结果 JSON/JSONL 的 Git clean filter 只过滤提交内容，不能据此修改或截断服务器原始结果文件。

# 当前执行合同：native Small 先行，随后 RAG+Notes 与机制论文评测

## 当前主线（2026-10-13）

当前唯一主线顺序为：

1. 冻结 LongMemEval-V2 官方 AgentRunbook-R 完整 Small（web + enterprise）原生结果；
2. 紧接着完成同一官方数据/入口下的 RAG+Notes 对照；
3. 沿原生写入/查询路径加入阶段计时，再接入依赖感知调度、细粒度失效、有效复用和一致发布；
4. 在共享模型、输入、预算和资源下，分别报告 B0/B1/B2/强 B3/Ours 机制消融；
5. 冻结配置后完成官方质量、独立数据至少 3 次重复，以及真实流式 Freshness/Goodput。

已有 v4 内部首表、强 B3、H4/H5/H6 和 18 道开发题全部保留，但属于历史开发/机制/回归证据，不是当前 native Small 或论文质量的门槛。MemForest 保留在 backlog，不扩展通用框架。

## 执行规则

- 必须使用官方完整轨迹、截图、问题、Reader、采样/思考/预算、评分入口和冻结上游代码。micro、prefix、截短轨迹、占位截图、text-only 或压缩预算运行只能作诊断，不能称 native Small。
- 本地服务或路径修复必须在 `native` 与 `adapted-matched` 目录中分开记录；不得静默改变模型、提示词、预算、采样、thinking 开关或输入范围。
- web 与 enterprise 截图归档可并行写入；`resume` 不保证复用同一个 incomplete 文件。每个归档都必须独立完成、按准确大小/哈希和 `gzip -t` 校验后，才运行 `prepare_data.py`/`validate_data.py`。
- 默认 Judge 模型仍是 `gpt-5.2`。若实际 API models/请求未核实可用，只标记 `judge_unverified` 或 `pending_judge`；不得未经实测替换为 `gpt-5.6`。
- Goal 工具状态由父 agent 维护；已核实的旧 Goal 为 blocked/unfinished 且 objective 仍是旧文本，工具没有 resume/update 能力时不重复 create。文档更新不等于 Goal 已激活。
- 不杀不明归属进程、不覆盖活动 runtime、不删除失败结果；每次向用户输出前先用一小段话说明本次准备做什么。

执行细节以同目录 `WORKPLAN.md`、`GOAL.md` 和 `execution/queue.json` 为准；若与历史 v4 首表条款冲突，以本主线合同为准。
