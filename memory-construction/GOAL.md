# Goal：质量约束下的有效记忆维护方法
版本：2026-10-15 / focused-method-v3。依据 reports/FOCUSED_METHOD_GOAL_20261015.md；取代外部框架优先及旧 native-first 排序。旧文档归档 reports/goal-history/pre-focused-method-v3/，原始结果保留。

在现有链路上持续优化或替换方法，以派生记忆质量和正常检索下游可用性为约束，取得相对相关强对照可重复的实际 tokens、模型计算或发布耗时收益。收益成立后及时冻结，完成对应范围的必要实验、表图、方法/实验章节及复现入口。不以基线数量、脚本完成或负结果整理作为完成条件。

## 当前执行
- METHOD01可信快照与合法缓存核对已完成，直接复用。
- 暂定低成本起点v12 source_overlay：零更新LLM，旧解释可能冲突，尚未冻结。delta_guarded仅为语义修复对照。
- 四例三方正常回归/修改事实QA已完成：overlay14/16与8/8，edit13/16与8/8，B3 14/16与7正确+1截断未评。生成events/notes审查见reports/method_v12_quality_review.md。
- v13 source_coalesced已完成核心验证：两域三轮连续修订/查询，B3更新70,580 tokens/206.049s，合并版0/12.841s；包含查询与Reader总LLM tokens 214,714→140,111，18/18序列单元均完整，合并版12/12正确、B3 11/12。两条未调参轨迹及拒绝/选择不匹配案例均3/3。
- 当前最佳可用版本升级为 source_coalesced + 安全文本修订笔记复用：仅当完整旧/新源行均不在笔记中才复用笔记；enterprise选择不匹配由3,260更新tokens/14.646s降至0/1.779s，Reader仍3/3。语义编辑降为消融，不再默认调用。
- 主比较使用现成AgentRunbook-R/强B3，Raw RAG/RAG+Notes历史结果明确标注。暂停MemForest/LightMem新适配及扩量，保存已有产物，不作为冻结门槛。下一步是冻结配置、核心消融和论文交付，不再扩外部框架。

## 决策与质量
一个当前最佳＋一个主要候选，每轮一至两个因素。最大差距→假设→最小改动→真实配对→成本/质量解释→保留或淘汰→下一轮。两轮同类无改善则换机制。主指标总LLM输入+输出tokens，同时报告发布墙钟、Embedding、失败及查询增量；初始/更新/查询分开。
普通固定题回归与修改事实QA分列。检查生成events/notes的新事实、过期结论、未改信息及状态归属；raw保存或正则不替代质量。同架构固定Reader/检索，通用优化给B3，独立合法缓存，负结果保留。

## 收敛与完成
最小证据包已基本具备：results/tables/method_focused_main.csv、method_v13_confirmation.csv、method_v13_repeats.csv、method_v13_sequence.csv，以及results/figures/method_v13_cumulative.svg。仍需补最终核心消融（去掉事件依赖复用、去掉当前证据合并/安全笔记复用）和论文方法/实验章节、局限、复现入口；未声明小样本质量统计等价或未测冷构建/增长收益。

## 原生Goal
2026-10-15本次get_goal返回null；上一可见记录blocked/unfinished旧objective。没有恢复/改写接口，不宣称active、不为改文字complete、不另建竞争执行器。当前会话直接推进；文档不代表自动激活。总研究未完成。
