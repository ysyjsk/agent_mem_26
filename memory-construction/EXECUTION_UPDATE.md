# 接续：完成固定论文证据
update_id: focused-maintenance-v4-20261015
update_revision: execution-recovery-20261016
guidance_revision: paper-delivery-20261016

先读 GOAL.md、docs/PAPER_EVIDENCE_PLAN.md 和 execution/prompts/CONTINUE_RESEARCH.md，延续当前 Goal。任务状态仍以 execution/queue.json 为准。

此次有一项必须及时接收的科学设置纠正：B旧清单8例全部修改 thoughts，而源码中的 Coalesced/Overlay 直接维护要求 text。B尚未评测时已准备 maintenance-confirmation-v2，保留全部8条轨迹及位置、24道正常题和原方法预算，改为有原文锚点的受控字段修订。不要执行旧v1作为核心确认；旧文件原样留存。A冻结计划、方法代码、已有结果和活动作业不变。
B的新执行入口为 manifests/focused-maintenance-v4/maintenance-confirmation-v2/manifest.json。8目标、24更新、16诊断题、24正常题，144次回答；具体预选快照及评分方式已写入。B存在历史评测暴露，仅称同数据集新增维护修订确认。

已知OOM不做重复复现。恢复入口已修正后，优先解决失败请求的显存条件并补实际缺失Notes/Event；基础设施fallback不当作正式生成成功。不新增独立smoke或重复全套验证；首个成功恢复请求直接复用到实验。
顺序仍为A→B→C，离线写作并行。A84更新/126查询批次不改；四行主表、Source-only/Overlay机制对照和论文交付不扩大。

由实际执行会话更新现有CONFIRM的v2路径并写真实接收记录，保留原ack历史。只写文件不能保证VS Code会话立即读取；此次部署不代写回执、不启动模型、不改原生Goal或queue。
