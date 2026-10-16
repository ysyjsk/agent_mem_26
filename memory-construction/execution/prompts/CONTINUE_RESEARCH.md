# 继续执行：以论文结果为交付
延续当前 Goal。读取 EXECUTION_UPDATE.md、GOAL.md、docs/PAPER_EVIDENCE_PLAN.md 后直接补缺，不重复已完成的 dry-run、全量测试或 OOM 复现。

当前优先级是解决真实阻塞并完成既定论文证据。恢复入口的状态修复已做；由你在安全持久化边界修复长请求显存条件，首个修复后请求直接补失败 Notes/Event，复用所有有效分区。catch-all 产生的占位笔记不能冒充正常构建；只补受影响条目，不能重建全库或偷减输入。共同后端修复纳入实际 runtime freeze，不计为 Ours 收益。

A 保持 full-small-recovery-v1 的84更新/126查询批次和现有执行依赖；一次一个GPU执行器，保留健康作业。每完成可比配对即更新论文表，不等全部结束才写作。

B 改用 manifests/focused-maintenance-v4/maintenance-confirmation-v2/manifest.json：原v1八例都是 thoughts 修订，不能检验源码要求 text 的直接 Coalescing；v2已在首次B模型调用前按源证据准备8条真实字段锚点的受控修订。原轨迹/状态位置、24正常题和方法预算未增加，旧v1保留。不要再运行v1的泛化追加句子。
B 总量24更新、48诊断回答、96正常QA回答；正常QA使用manifest指定的每域代表快照，按SCORING.md完成18确定性＋6语义题并如实标评分方式。运行前补实际快照与runtime哈希。B仅称同数据集新增维护修订确认，不称held-out。

将B v2接到现有CONFIRM任务，不新建状态体系；以实际证据记录首次阅读本指导的时间与继续动作，不能只回“已读”。执行前如发现B v1已被另一个作业调用，保留暴露记录并明确分版本，不能覆盖历史。
成本包含更新、controller和Reader，Embedding另列。分别报告当前事实、未改事实、旧值误用、正常QA。Source-only/Ours看事件证据整体作用；Overlay/Coalesced看三轮累计成本，不能只凭零LLM或块数宣称独特贡献。
按PAPER_EVIDENCE_PLAN完成四表两图和正文。固定范围内遇到实现错误自行最小修复并继续；没有新故障就继续实际实验，不再重复审计、调参、改题、加baseline或扩大数据范围。每次汇报只给新增有效数字、真实缺口和下一已启动任务。
