# 当前执行规则：focused-maintenance-v4-20261015
执行修订：execution-ready-r2-freeze。最新用户指令优先；旧技能/报告中 B0、kernel、native Small 先行等不再控制任务。

每次输出先用一段话讲清本次动作。先读 EXECUTION_UPDATE.md，再读 GOAL.md、WORKPLAN.md、docs/EXPERIMENT_PROTOCOL.md、execution/queue.json；完整接续提示在 execution/prompts/CONTINUE_RESEARCH.md。

- GOAL.md 是唯一成果定义；EXPERIMENT_PROTOCOL 定义比较/准入/冻结；queue.json 是实际状态，不以 todo 文字覆盖真实已完成进度。根目录文档只导航。
- 固定局部维护方法和四行公开比较 Raw RAG、RAG+Notes、AgentRunbook-R/B3、Ours；Source-only 是关键消融；Overlay/Delta Edit 是已有核心对照。不增加外部框架，不把当前 B3 混成旧 workflow_b3。
- 下一项新增数字是 B3/Source-only/Ours 六轮开发表：先共同 Notes 规则与最小一致性检查，再真实单修订/查询。公开适配和写作可做相关 CPU 工作，不能把全部 baseline 完成作为必要修复的前置。
- 基于 v13 核心，关闭整条原文缺席即复用 Notes 的启发式，同时修正维护它的旧测试。Source-only 仍可检索最新 Raw State，受影响 Notes 按共同规则处理；不故意弱化对照。
- 先首轮/确认，后完整 Small 历史库正式维护实验。完整 Small 是本轮后续必需交付，不是首轮前置；必要一致性/公平性通过即冻结并扩量，效果不领先不是扩量门槛；完整正式交付仍须完成。
- 主要目标是成本；准确率上涨、所有更新零调用都不是验收条件。记录更新＋查询防成本转移。失败/缺评不能填 0；完整答案、准确率、截断分开。
- 每次一个主要候选、一至两个因素，实测后保留或淘汰；不按结果更换确认案例。旧结果只能在输入/语义/配置匹配时复用。
- 每个成功阶段及时落盘，修复失败单元继续。一次错误/负结果不结束仍可执行的工作；不扩建搜索、恢复、监督平台代替数字。
- 一次只运行一个 GPU 实验执行器。现有模型服务不等于实验 runner；先确认归属，不重复服务、不杀不明进程、不修改活动实验配置。
- 新运行与正式/开发表路径按 WORKPLAN；不搬动旧数据和代码，特别保留 runs/.../local-text-only 内实际被导入的 adapter。
- 这次部署仅改执行文档/技能，不代写实验完成、接收回执或原生 Goal 状态。当前服务器 VS Code 会话收到后记录 update_id＋update_revision 与下一实际任务，再立即执行。
- 每次恢复或阶段切换检查 EXECUTION_UPDATE.md 修订；输出新数字、原因、决定与下一实际动作。Goal 的暂停、预算和 blocked 遵循宿主规则。

- 先按 docs/REUSE_AND_OPTIMIZATION.md 更新 execution/reuse_inventory.csv，输出已有/缺失/新增计算后立即补缺。四行表是组装目标，不是从头重跑；新增 Source-only 不自动使旧 B3/Ours 失效。
- 每个重跑记录具体原因；评分可重评、日志可重聚合，不因整体哈希或计划名称变化重跑全矩阵。
- Codex 可自主读论文原文/官方实现，结合瓶颈改进现有 Ours，无需等待指定 trick；一次一个主要候选，最小配对。通用优化给适用对照，不新增 baseline，不改确认样本。

- 本轮已进入收敛：可选主要候选默认零个、全程最多两个，正式冻结后不做性能调参；必要实现错误照常修复。Reader/检索/预算/评分固定，维护表示优化不得混成独占通用查询收益。
- 正式结果正负均可形成完整结论并结束本轮；不要求 Ours 超过 Source-only。确认/正式数据用于改方法则记录暴露，不能仍称未暴露验证。
