# Goal：完成局部记忆维护的可写作证据
科学协议 focused-maintenance-v4-20261015；运行修订 execution-recovery-20261016；收尾指导 paper-delivery-20261016。

## 目标
保持 v13 Coalescing 和现有公开架构对照，以真实配对数据回答：局部维护是否降低更新成本、事件证据维护是否有价值、合并是否优于追加，并检查质量变化。完成正式结果、表图、论文正文与复现材料，不重开方法搜索。

## 固定顺序
1. 直接修复已知 OOM 对失败条目的影响，复用完整有效分区。首个修复后请求即用于补缺；不再专门复现 OOM 或重复已有 dry-run。基础设施占位 Notes/Event 不等于正式语义构建成功。
2. A：完成 execution/full-small-recovery-v1/experiment_plan.json 已登记84更新单元、126查询批次；保留健康作业和匹配结果，不变更 A 的数据/方法矩阵。
3. B：使用 manifests/focused-maintenance-v4/maintenance-confirmation-v2/manifest.json 的8条轨迹、24更新单元、16诊断题及24正常题，共144次回答。旧v1八例 thoughts 负载不能验证直接 Coalescing，保留为设计历史；v2在模型评测前修正，未增加计算预算。
4. C：按 docs/PAPER_EVIDENCE_PLAN.md 形成四表两图、paper/manuscript.md、paper/reproduction.md。离线写作现在并行，每组有效配对完成即填表。

## 边界与完成
- 主表 Raw RAG、RAG+Notes、AgentRunbook-R/B3、Ours；Source-only与Overlay作机制对照，不增加外部框架。
- text-only/adapted完整Small背景历史上的受控局部修订；不是官方全部QA或多模态复现。B有历史评测暴露，仅称同数据集新增维护修订确认。
- 更新/检索controller/Reader/Embedding分别记账，初始构建另列；unknown、失败、截断、待评分不混为0。同源独立分支，公平运行设置。
- 固定范围交付齐全且结论与成本—质量及机制证据一致才完成；不要求Ours提高准确率或战胜所有对照。真实负结果保留，缺失测量继续补，不能用负结论替代未完成工作。
- 不新增trick、样本批次或重跑全部baseline。修复只影响必要阶段；明确错误自主修复后接续，不停在报告。

详细方案只维护 docs/PAPER_EVIDENCE_PLAN.md；科学比较见 docs/EXPERIMENT_PROTOCOL.md；状态只看 execution/queue.json。本文件不等于原生Goal。实际服务器会话延续已有Goal，不为了换文案伪标complete；宿主不能改写目标时按本补充继续，不启动重复执行器。
