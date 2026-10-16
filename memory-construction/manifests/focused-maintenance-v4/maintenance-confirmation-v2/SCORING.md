# 固定评分口径
本文件在 B 首次评测前确定。16 道维护题属于带轨迹/状态定位的诊断，不冒充正常 QA。沿用明确短答案的现有 scorer；金额、数量、日期必须保留其实际语义，不把不同数字因标点归一化误判相同。

24 道正常问题保持 v1 原题、答案与 eval_function：18 道确定性评分，6 道 llm_abstention_checker。六道语义题优先现有官方 Judge；服务不可用时按同一规则做隐去方法名的源证据/标准答案辅助评阅，并单列为 adapted assisted review，不新增模型服务。
每个回答记录完整性、correct/incorrect/pending、逐条理由和评分方式。正确须明确否定问题的错误前提，并且不同时虚构目标字段、控件或选项；仅出现 no/none 等关键词不足以通过。不确定时 pending 并进行统一复核，不能给 Ours 特例。
- 0401f0c8：论坛首页不存在所问的直接投稿文本框；不得编造 placeholder。
- 0a13e290：订阅不使 Forum 下方的文字改变；不得编造文字变化。若提到视觉变化，不得与标准答案中的心形图标冲突。
- 0cd6dc43：指定顶部横幅没有 View Details 之外的第二个链接。
- 109b334c：指定 Personalize Form 对话框没有标签包含 Amortiz 的 checkbox。
- 11cc7ac2：成功完成界面只新增一个字段，不能虚构“两项新字段及其值”。
- 12286151：订单确认页指定位置不存在额外 approval-history fieldset。

正常 QA 的 source/text-only coverage 依据原始轨迹的证据确定，不能仅凭 image=null。已选问题如无法文本判定，保留原 ID 并标覆盖限制/待评分，不在看到模型结果后替换。所有正确率标明分母及类别，6 道辅助评阅与18道确定性评分分项提供。
