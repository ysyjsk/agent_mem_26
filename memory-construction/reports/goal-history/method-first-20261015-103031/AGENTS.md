# 当前执行合同：完整论文实验（2026-10-15 用户目标覆盖）

用户已明确：总目标是完成支撑论文的整套实验并获得可重复的成本收益，小规模实验只作中间里程碑。
以本目录 GOAL.md 的研究总目标、PAPER01–PAPER06 实验包和完成条件为当前执行合同；队列中的同名任务为当前计划。
继续本地 text-only/adapted 路线：更新主结果 → 冷构建配置收敛 → 两域完整 Small 基础对照与质量 → 关键消融/扩量 → 重复与真实流式评测 → 论文表图和复现交付。
质量是约束，构建/更新耗时、调用与 tokens 是优化主指标。native GPT/视觉、外部官方 Judge 和 MemForest 保留为后续补充，不阻塞本地主线。
已有服务、结果和查询配置沿用；必要修复后继续运行，不把一张小表、脚本实现或计划更新当作总目标完成。
这次仅澄清执行文档，不代表原生 Goal 已激活；由当前执行会话核实其真实状态，避免重复执行器。
保留“不杀不明归属进程、不覆盖活动配置或结果、输出前简述本次动作”等操作规则。

以下为历史合同：与上方和当前 GOAL.md 冲突的优先级、依赖及完成条件均已被取代；历史事实继续保留。

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

执行细节以本目录 `WORKPLAN.md`、`GOAL.md` 和 `execution/queue.json` 为准；若与历史 v4 首表条款冲突，以本主线合同为准。
