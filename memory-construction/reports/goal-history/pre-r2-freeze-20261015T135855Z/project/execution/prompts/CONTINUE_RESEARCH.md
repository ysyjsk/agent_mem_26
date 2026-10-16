# 当前执行 Prompt：复用、补缺、自主优化
协议 focused-maintenance-v4-20261015；执行修订 execution-ready-r2。
项目 /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction

继续现有工作，立即读 EXECUTION_UPDATE.md、GOAL.md、WORKPLAN.md、docs/EXPERIMENT_PROTOCOL.md、docs/REUSE_AND_OPTIMIZATION.md、execution/queue.json 和当前 memory-research-loop 技能。旧“完成四行对照”应理解为组装合法证据＋补缺，不是四方法从头执行。

## 先输出缺口，再运行
短检查当前作业/新产物，更新 execution/reuse_inventory.csv，输出“已有结果—缺失结果—新增计算”对照表，随后立即执行第一项确实缺失的任务。已有清单是本次只读审计起点，核对与最终配置的兼容性即可，不再全面审计历史或重建环境。
按构建、更新、检索、Reader、评分分别复用。整体代码哈希变化不自动使未变策略/请求失效；查询变更只补查询，评分变更优先重评保存答案。每个重跑记录具体不能复用的原因。

## 当前实际缺口
优先新增 Source-only、Raw RAG、RAG+Notes 的历史修订＋对应查询，各六个单元；已有新增结果继续扣减，首次真实检查也计入。十八是维护单元估计，不是调用次数或强制数量。
B3/v13/Overlay 的六轮及原核心确认、重复优先复用。已核对序列十八条和两条确认都早于追加 Notes 启发式；关闭该规则不要求它们整体重跑。Raw RAG/Notes/AgentRunbook 初始构建和正常 QA 不重复做同配置实验。按兼容配置选记录，不挑最高分。
Delta Edit 保留历史版本，同条件可比则引用，否则分版本展示，不重开发或全量跑。历史异常检查先离线复核，真实错误只修复受影响部分。

## 实现后真正跑起来
确认现有 Ours 与已测 v13 核心一致，关闭不安全 Notes 规则并修正对应旧测试；Source-only 更新 Raw State 并失效受影响 Event，保留正常原文检索和共同 Notes 规则。
按协议完成失效不泄露、连续不复活、未受影响内容保留、实际保存重载四项检查，立即运行缺失单元。组装 source_only_compare.csv 和 public_main.csv 到 dev/，每行引用实际原始路径、版本、成本、质量/失败。
一项失败保留成功阶段，修复失败单元继续，不能只报告。缺 Judge 保存 pending，继续可靠可评分部分和成本测量。

## 自主分析并改进 Ours
你已获准自行阅读相关论文原文、官方代码和本项目失败样例，并选择当前方法内的局部优化，不必等用户指定 trick。
以实测成本分解确定一个瓶颈，针对性阅读后明确：文献具体机制、落到哪个函数、减少什么计算、对照如何公平、最小验证是什么。记录在 reports/ours_optimization.md，然后直接实现并跑最小配对；无可落实机制就回到实验，避免泛泛综述。
现有六轮 Ours 更新 LLM 已为零，查询占总墙钟约 87.6%。可检查维护后的重复证据/上下文、无效重算、选择性语义回退，不转向无关 QA 涨分搜索。通用优化给所有适用对照，方法特有改动单列；每轮一个候选、一至两个因素，只补受影响运行。
效果不好则分析原因再修复或简化，不能按分数换确认样本或削弱 baseline。证据已支持清晰贡献就收敛，推进正式实验，不无限微调。

## 后续交付与 Goal
确认阶段可复用合法历史确认，只补方法变化/覆盖不足的部分；不能把已暴露旧批次说成新 held-out。通过协议条件后自动进入完整 Small 历史库＋固定维护负载，不等再次批准。
原则上只构建 Raw RAG、RAG+Notes、AgentRunbook 三类初始记忆，合法旧分区可复用；B3/Ours/Source-only 从共同初始快照分成独立更新分支。修订前实际请求相同的 QA 可标 shared_reference 共用，不算多次独立测量或新零成本调用。
同步写方法/实验正文，交付正式主表、匹配 Source-only/Overlay 核心消融、分版本 Delta Edit、连续曲线、必要确认/重复、逐题数据和实际复现命令。
由本会话记录真实接收：update_id、update_revision、received_at、current_activity、next_task、native_goal_status；interpretation 确认“阶段级复用、仅补缺口、自主有依据优化、固定公平口径”。实际核对并按宿主能力延续/设置 GOAL.md 的目标；文件不等于原生 Goal 激活。
不要只回复已理解或计划。报告新增或复用的具体证据、原因与下一实际动作，然后继续。
