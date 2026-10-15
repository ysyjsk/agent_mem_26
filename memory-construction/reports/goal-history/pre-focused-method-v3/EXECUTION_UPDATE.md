# 最新实际接续（2026-10-15）

最新用户要求：方法探索＋相关外部强基线提前参与，不立即全量。历史文档保存在 reports/goal-history/external-method-selection-20261015/；所有实验原始记录不变。

原生Goal本次get_goal返回blocked、旧研究objective未完成。没有resume/update文字能力；不重复create或伪造complete。当前会话直接继续执行，无竞争执行器。

已完成 bash tools/run_method_v12_normal_readers.sh（session31325退出0），输出 runs/method-first-20261015/v12-normal-readers.log：reply/count三方正常Reader各7/8，24/24完整。更新成本为既有v12测量，非本次重测：overlay总0tokens/2.9297s，delta3106tokens/14.9519s，B344288tokens/46.2007s。不能把固定题回归当作修订值/失效结论验证。

当前实际运行：tools/run_memforest_shared_dev.py --domain web --output runs/memforest-shared-dev-20261015/web-v1（session89708）。日志runs/memforest-shared-web-20261015.log。每域一个user，每完整轨迹一个session；原树/去重/增量/agentic查询算法保留，现有HTTP服务，无独有状态截断。每轨迹save，build_progress及所有阶段调用落盘。不要并发启动GPU实验或覆盖目录。

已准备未启动的有限接续：web MemForest阶段结束→bash tools/run_method_v12_remaining.sh（剩余Title/sort三方＋四例正常修订值检索）→MemForest enterprise→bash tools/run_method_v12_semantic_cases.sh。两个新反例及问题已事前固定并验证源锚点：Description填写拒绝、Type实际Emergency而动作目标Normal。它们是新修订案例而不是独立新轨迹。27项CPU单测通过。

新表入口tools/report_method_external_dev.py，报告reports/method_external_dev.md。历史外部成本与当前分支维护成本分表标注，未把旧Ours当当前方法。事件/notes审查reports/method_v12_quality_review.md；正常修订值结果待补。query参数未变，方法尚未冻结。

v11旧followup已完成，不再执行。v12此前只有定向生成记忆诊断，不能称正常检索质量保持或最佳冻结。当前外部历史表的Ours为旧实现，不得混称当前方法。
