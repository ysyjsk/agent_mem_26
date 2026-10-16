# 执行计划：focused-maintenance-v4-20261015

总目标见 GOAL.md；方法与指标见 docs/EXPERIMENT_PROTOCOL.md。下表与 execution/queue.json 使用相同任务 ID。

| ID | 当前状态 | 本项交付与下一步 |
|---|---|---|
| EVIDENCE | 已完成、复用 | v13 序列/重复/确认及 v11 编辑结果；原始文件保留。新笔记规则不与旧版结果混算。 |
| ALIGN | 待执行会话接收 | 检查现有作业；采用已验证 v13 核心和共同笔记策略，登记版本与固定数据。一次短核对，不重做环境。 |
| SOURCE_ONLY | 待 ALIGN | 在已有 updater 中增加 Source-only；先完成两域各三轮独立连续快照与正常查询，输出 source_only_compare.csv。 |
| PUBLIC_BASELINES | 待 ALIGN | 复用 Raw RAG/RAG+Notes/AgentRunbook-R 实现，补薄局部替换入口；跑同一修订与查询负载，输出 public_main.csv。 |
| SELECT | 待首两项真实结果 | 在现有维护方法内修复或简化；单一候选、每轮一至两个因素。结果足以支持主张才固定最终版本。 |
| CONFIRM | 待 SELECT | 固定版本后使用未调参完整轨迹确认；复测必要正常 QA；补实际缺失的成本重复和核心消融，不重跑全部旧实验。 |
| WRITE | 可立即做 CPU 工作 | 按 paper/README.md 写问题、方法与设置，结果来自表格且注明版本；实验期间持续更新。 |
| PACKAGE | 待 CONFIRM、WRITE | 完成四行公开主表、机制表、序列图、正文与复现入口，逐项核对结论和证据。 |

## 执行顺序
先启动 Source-only 的最小可用实现和首个真实单元；结构/失效行为正确后跑完整已有六轮。不要先写新通用 runner。
GPU 工作顺序为 Source-only → 公开主比较 → 定向修复 → 确认；同一执行会话可在等待时做公开基线 CPU 适配或写作，不启动第二实验代理。
第一次主表不等待全部正文完成；写作也不等待最终总表。

## 数据与复用
- 起点：runs/dev-adapted-text-v1/data 的两域共享完整轨迹及八道原始问题；既有修订序列在 runs/method-first-20261015/v13-sequential。
- 已完成三轮序列、两条确认轨迹及成本重复，均归入其原版本。细节与路径见 paper/README.md。
- 首轮只补 Source-only 缺失单元；随后补 Raw RAG/Notes 的同负载结果。旧结果输入、语义和配置相符才复用，时间比较还应注明运行条件。
- 在看新结果之前，从现有完整数据中选剩余未调参轨迹作为确认批次，并记录选择依据、修订及证据覆盖。八道旧问题的重复回答不算新增独立样本。
- 原有八道正常问题按方法在需要的最终快照上回归，不给每个无关中间版本重复跑全套。

## 实验期间的决定
优先降低总成本并保持可用性。Source-only/Ours 更新均为零 LLM 时，改看实际查询成本、Embedding、证据长度及质量，不继续优化“低于零”。
无优势时检查事件证据是否被检索使用、源状态定位及过期解释处理；用已有局部编辑/抽取回退修复必要失败，不新建大架构。
若公开轻量方法在相同质量下也更便宜，如实记录并针对事件/工作流能力改进；不删除该 baseline，也不把通用缓存改进独占给 Ours。

## 新输出位置
- 原始新增运行：runs/focused-maintenance-v4/（执行会话实际运行时创建）
- 最终汇总：results/tables/focused-maintenance-v4/（public_main.csv、source_only_compare.csv、ablation.csv、confirmation.csv）
- 图：results/figures/focused-maintenance-v4/
- 正文与复现：paper/；旧草稿继续作为素材，旧 runs/tools/third_party 不搬迁。
