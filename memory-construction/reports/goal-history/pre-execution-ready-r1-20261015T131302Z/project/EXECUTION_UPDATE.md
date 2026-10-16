# 执行纠正：focused-maintenance-v4-20261015

用户已确定：Codex 比较暂停；公开主表保留 Raw RAG、RAG+Notes、AgentRunbook-R、Ours；新增 Source-only 作为关键消融。此版本替代旧文档中“只差消融/写作”及“公开 RAG 仅作历史参考”的排序。

## 收到后立即执行
读 GOAL.md、WORKPLAN.md、docs/EXPERIMENT_PROTOCOL.md、execution/queue.json 和 execution/prompts/CONTINUE_RESEARCH.md。先核对实际活动作业，在安全阶段接续，不重跑已完成阶段或覆盖旧结果。
由当前执行会话写 execution/ack-focused-maintenance-v4.json，至少记录 update_id、received_at、current_activity、next_task 和实际 native_goal_status。本次部署没有代写接收回执。

## 下一项新增实验
ALIGN → SOURCE_ONLY：使用已验证 v13 核心和共同笔记策略，补 Source-only；先验证失效不泄露和保存重载，再完成已有两域各三轮的独立连续修订/查询。
紧接 PUBLIC_BASELINES：补 Raw RAG/Notes 同一维护负载，不适配新框架。CPU 等待期开始 paper/ 写作。

## 固定解释
Source-only 更新 Raw State、使受影响旧 Event 失效且不生成替代 Event；Ours 在 Event 中维护状态位置绑定的当前证据。此比较解释事件级证据维护整体价值。已有 overlay→coalesced 解释单独合并效果。
停止把“完整源行没有出现在笔记里”当安全复用依据。允许必要模型工作，保留强成本收益即可，不追求所有案例零调用。
Source-only/Ours 接近时看总成本和质量并定向修复或简化；不预定结果，不退回新框架或冷构建探索。

## 接收状态
部署时：pending_executor_ack。文件更新不能保证正在运行/空闲的 VS Code 会话立即读取；需要该会话收到本入口后实际确认。无本次原生 Goal 激活或实验启动声明。
