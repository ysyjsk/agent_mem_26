# 给当前服务器 VS Code Codex 的接续提示
协议：focused-maintenance-v4-20261015；执行修订：execution-ready-r1
项目：/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction

继续现有进度并实际实现、运行；整体方法和 baseline 已固定，不再重写研究框架。本文件、GOAL.md、WORKPLAN.md、docs/EXPERIMENT_PROTOCOL.md 和 execution/queue.json 是当前执行口径。旧 memory-fast-results-v4、B0/kernel、native Small 先行不是本次 v4。

## 先做什么
短检查活动实验、已完成结果和现有模型服务；保留有效阶段，不重复启动。读取当前 memory-research-loop 技能，不依赖上下文里的旧副本。由本会话写 execution/ack-focused-maintenance-v4.json，记录 update_id、update_revision、received_at、current_activity、next_task、实际 native_goal_status；用简短 interpretation 字段确认“成本为主、Source-only 可正常查 raw、先首表后 Small、不新增 baseline”。不要代填已经完成的实验状态。

随后立即处理 ALIGN：在已有 updater 关闭“原文整行没有出现在 Notes 中即复用”规则，修改对应旧测试，使 Notes 按共同合法请求/依赖更新；保留历史结果。不要为了保持零调用或旧测试通过重新启用启发式。确认实际请求预算/thinking，不从服务默认值推断请求生效值。

## 第一张新增表
在 tools/run_agentrunbook_updates.py 所在链路补最小 Source-only：
更新 Raw State/索引，使共同受影响范围的旧 Event 失效，不生成替代 Event，也不注入 Ours 当前证据；保留未受影响 Event/Notes，受影响 Notes 按共同规则处理。
Source-only 保留正常 raw retrieval、共同补全、相同 Reader/预算；它不是 Raw RAG，也不保证零 LLM。

只补四项必要检查：失效不经任何正常检索/缓存路径漏出；连续修订不复活；未受影响条目/向量保留；实际保存重载后行为一致。新版 Raw State 必须可查。
检查通过即跑一个真实修订＋查询，然后完成既有两域各三轮 B3/Source-only/Ours 配对表。复用语义/配置/缓存匹配的旧 B3/Ours，否则补必要匹配运行。首表写 results/tables/focused-maintenance-v4/dev/source_only_compare.csv，包含成本、逐题质量、失败及来源，不以 smoke/空 CSV 代替。

## 首表之后连续推进
1. 补 Raw RAG、RAG+Notes 的薄局部更新入口，同一负载生成四行开发表；AgentRunbook-R/B3 是同一个公开方法，不能再添一行旧 workflow_b3。CPU 适配和 paper/ 写作可在等待实验时进行。
2. 按更新＋查询成本和错误样例修正一个主要瓶颈，一次一至两个因素，立即配对运行。准确率上涨不是目标；需要相对 B3 可重复降本且无未修复的系统性质量退化，对 Source-only/轻量方法有可解释价值。不追求全部更新零调用。
3. 按协议两阶段冻结 Manifest：先于确认分数冻结数据/修订/问题/评分/负载；确认前冻结候选代码/实际模型与配置/初始快照/缓存。先前看过的 v13 confirmation 不冒充新 held-out。bug 修复生成新版本，不覆盖旧清单；利用确认结果调参后记录其已暴露。
4. 首轮与独立确认符合协议条件，自动进入 SMALL_MAIN：完整 Small 历史库＋固定维护与查询集合，先估算初始成本，各架构初始构建一次并合法复用。它是本轮正式交付，不是现在的前置；也不是官方全部多模态 QA。不得默默缩库仍称完整 Small。
5. 同预选核心修订子集补 Source-only、Overlay、Delta Edit，复用有效连续实验和至少三次代表配对计时。正式表、曲线、逐题数据、方法/实验正文和实际复现命令一起交付。

## 遇到问题怎么继续
失败单元记录原因、修复并继续，成功阶段不重跑；缺 Judge 保存 pending 答案，继续可靠可评分部分与成本测量，不虚填质量通过。Source-only 持平时先看实际检索/事件证据是否发挥作用，必要时用已有局部编辑/回退或简化无效部分，不换一套方法。
同类改动两轮无效后转查另一个有证据的瓶颈。不得通过关闭对照能力、按结果换题、删除失败或不给 baseline 通用优化制造差距。没有收益且未完成交付时不能宣布论文就绪；也不能只留待办结束可继续的授权工作。
不重做 P0、不新增外部框架、不搬迁实际 adapter、不造新恢复平台；只用一个 GPU 实验执行器。阶段报告给新增数字、原因、保留/淘汰决定与下一项实际动作，随后继续。

## 本会话 Goal
实际查询原生 Goal。无 Goal 且支持时使用 GOAL.md 的“总目标”创建；相符时延续。若旧目标无法改写，记录事实并继续本轮授权工作，不把未完成旧目标标 complete 来换名，不创建第二执行器；暂停/恢复/预算按宿主权限处理。文件更新不等于 Goal 已激活。
最终结束依据 GOAL.md 完成条件，不能把首表、确认或文档齐全当成完整 Small 和论文交付完成。
