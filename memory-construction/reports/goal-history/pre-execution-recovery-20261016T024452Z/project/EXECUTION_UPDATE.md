# 执行更新
update_id: focused-maintenance-v4-20261015
update_revision: execution-ready-r2-freeze

本次只优化执行方式，方法和 baseline 不变。优先级：合法结果复用 → 补真正缺失的维护单元 → 依据瓶颈自主优化 Ours → 完整 Small 和论文。

先读 GOAL.md、WORKPLAN.md、docs/EXPERIMENT_PROTOCOL.md、docs/REUSE_AND_OPTIMIZATION.md、execution/queue.json，再执行 execution/prompts/CONTINUE_RESEARCH.md。
由当前执行会话核对新作业和产物，更新 execution/reuse_inventory.csv，先输出已有/缺失/新增计算表后立即执行；不需要重审全历史。复用按阶段判定，不以整体文件哈希变化重跑全矩阵。

已核对：连续序列 B3/Overlay/Coalesced 十八条和两条确认均来自追加 Notes 启发式之前的核心版本。当前缺口预计 Source-only、Raw RAG、RAG+Notes 各六个维护＋查询单元，已有新增产物扣减。初始构建、正常 QA、B3/v13/Overlay 与历史 Delta Edit 优先复用，各自范围/版本标清。
Codex 获准自主读原文/官方资料并实现有证据的局部候选，不必等用户指定 trick；固定 baseline、正式样本与公平口径。细则见复用与优化文档。

当前会话自行写 execution/ack-focused-maintenance-v4.json：update_id、update_revision、received_at、current_activity、next_task、实际 native_goal_status，以及简短 interpretation：阶段级复用、只补缺口、自主有依据优化、固定公平比较。
本次部署不代写回执，不启动另一个执行器，不修改实验代码或历史结果。部署时为 pending_executor_ack；文件更新不代表实际会话已接收。

## 收敛补丁：本次最新要求
必要 Notes/Source-only/公开更新接口修复和真实链路检查通过后，冻结实现与数据，直接进入完整 Small，不要求 Ours 先胜过 Source-only。可选主要候选默认零个、全程最多两个且不得延误主线；正式冻结后不改 Reader/检索/预算/评分或按结果调方法。正式证据正负均可完成本轮。先读 docs/REUSE_AND_OPTIMIZATION.md 最后的四条收敛规则，并在回执 interpretation 中确认这些边界。
