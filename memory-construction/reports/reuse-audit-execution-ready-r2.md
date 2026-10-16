# 去重审计与优化起点
协议 focused-maintenance-v4-20261015 / execution-ready-r2。只读检查服务器现有文件，不是新实验。

|已有证据|本次核对|默认下一动作|
|---|---|---|
|dev_adapted_first_compare.csv|40 行，含构建复用、检索变体和重复；三种公开初始构建/正常 QA 都有记录|按阶段/配置选兼容记录，禁止按最好分挑选|
|method_v13_sequence.csv|B3/Overlay/Coalesced 各 6 行；18 个原始 update_metrics 均为 a04bcf7c… 核心，保存快照与查询指标存在|优先复用，不因关闭后加 Notes 规则全部重跑|
|method_v13_confirmation.csv|两条轨迹/4 行，均 a04 核心，快照存在|原版本确认复用，不称新 held-out|
|method_v13_repeats.csv|8 行历史重复，部分 derived_checks=False|先用旧快照离线复核检查语义；不能直接填质量通过或全部重跑|
|method_focused_main.csv|20 行混合原始/聚合/不同版本，含 v12 Delta Edit 和后加 Notes 个例|按版本引用，聚合不再计作新样本|
|新 focused-maintenance-v4 目录|未发现新增 runs/tables/manifests，接收回执仍缺失|优先补 Source-only/Raw RAG/Notes 维护，执行前再扣减新产物|

六轮 Ours：更新 0 LLM tokens；发布时间合计 12.841s；更新＋查询 140111 tokens / 103.886s；Reader 123082 tokens。按该表的累计口径查询墙钟约 87.6%，Reader 约占总 LLM tokens 的 87.8%。这指向维护后重复证据/上下文与选择性回退的分析，不能变成无关 QA 搜参。

历史 AgentRunbook 正常查询缺 query embedding reuse 的记录不能直接充作当前匹配查询成本；其构建 32 次失败 usage 未知也不能记零。可复用对应已知阶段，不因此重做全部构建。

execution/reuse_inventory.csv 是阶段级候选清单，最终相容条件由执行会话针对将用的记录核实。首轮预计缺少三个策略各六个维护单元，不是十八次 LLM 调用。完整 Small 是后续新规模，与开发复用不冲突。
