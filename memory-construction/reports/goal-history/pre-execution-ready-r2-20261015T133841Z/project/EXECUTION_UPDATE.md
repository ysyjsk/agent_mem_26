# 执行更新
update_id: focused-maintenance-v4-20261015
update_revision: execution-ready-r1

方法与 baseline 不变，本次只明确执行目标、Source-only 准入、正式 Manifest 与 Small 阶段，并修正旧技能冲突。当前唯一执行入口为本目录；仓库根目录已改为导航。

先读 GOAL.md、WORKPLAN.md、docs/EXPERIMENT_PROTOCOL.md、execution/queue.json，再执行 execution/prompts/CONTINUE_RESEARCH.md。旧上下文中的技能不控制本轮；最新副本为 execution/skill/memory-research-loop/SKILL.md，同时同步到服务器安装位置。

当前执行会话先检查已有活动作业，在安全边界接续，再自行写 execution/ack-focused-maintenance-v4.json：
update_id、update_revision、received_at、current_activity、next_task、native_goal_status 和简短 interpretation（成本优先；Source-only 保留 raw retrieval；先首表后正式 Small；baseline 不增加）。这是实际理解与接收记录，本次部署不代写。

下一实际动作：共同 Notes 规则及对应旧测试 → Source-only 四项一致性检查 → 一个真实修订/查询 → 两域各三轮三方开发表。公开更新适配和写作紧随，不先重做环境或全库构建。
首轮/独立确认支持后自动进入完整 Small 历史库正式维护负载和核心消融；不再另等批准。初始构建、更新、查询成本分开，重点是更新＋查询总成本且质量可用，不要求 QA 必须上涨或更新全为零调用。

部署时接收状态：pending_executor_ack。文件或技能更新不能自动唤醒正在运行/空闲的 VS Code 会话；只有该会话实际记录才算接收。本次没有修改实验代码、执行模型请求或宣称原生 Goal 激活。
