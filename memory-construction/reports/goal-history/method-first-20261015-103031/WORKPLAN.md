# 当前工作计划：完整论文实验（2026-10-15 用户目标覆盖）

当前总目标与完整验收以 GOAL.md 为准，执行 execution/queue.json 的 PAPER01–PAPER06；不能在八个更新案例、十条冷构建或单个优化候选完成后结束研究 Goal。
本地 text-only/adapted 是当前有效路线。完整 Small 的基础对照、强 B3/Ours、更新、消融、扩量、质量、重复、真实流式及论文表图均列入必需交付。
当前先扩展已有事件级更新收益并补质量；随后收敛冷构建配置、冻结正式评测，持续完成其余实验。
下方旧 native-first 顺序及其阻塞依赖为历史记录，不再控制当前执行。历史原始结果、失败、负结果和操作安全规则保留。

# Agent Memory Construction — Workplan v4：native Small → RAG+Notes → 机制与论文评测

## 最新用户覆盖：构建成本优先（2026-10-14）

冻结查询环境：分块、tokenizer 复用、词项补证据、query embedding exact reuse；不再搜索检索量/证据顺序。查询收益单列。
当前执行顺序：AgentRunbook-R 两相邻转换真实联合抽取（完整轨迹先配对，随后固定 10 条）→ 构建 Embedding 完全相同输入复用 → 四格冷构建表 → 同表示/同通用优化的 B3/Ours 追加、状态修订、工作流修订。
质量以固定 8 题及事件/来源/状态变化覆盖为约束，按必要计算与发布成本选候选。保留 notes、events、原始证据及索引；不以取消视图制造收益。原生 Small/Judge 另行挂起，不阻塞此主线。
真实进度见 `runs/construction-pair-v1/`；既有原生 Goal 为 paused，当前工具无 resume 接口，不重复创建执行器。

**当前唯一关键路径：冻结官方 AgentRunbook-R 完整 Small → 紧接 RAG+Notes → 原生阶段计时与依赖机制 → B0/B1/B2/强 B3/Ours 分表 → 官方质量与真实流式评测（至少 3 次重复）。**

v4 的内部首表与优化结果继续保留为历史开发/机制证据，但不再定义当前外部基线门槛。当前外部主线的顺序、依赖和交付以本文件第 9.3 节及 execution/queue.json 为准。原有方法定义、数据可见性及正式实验规范保存在 WORKPLAN_REFERENCE_V2.md，按需查阅；其中 P0–P7 的旧前置顺序不再控制当前执行。项目代码根目录为 /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction。

## 当前主线覆盖（2026-10-14）

本节覆盖下方历史 F0–F2 条款中与当前优先级冲突的内容；历史首表、强 B3、H4/H5/H6、失败记录和负结果全部保留，不重跑。当前顺序固定为：

1. 完成官方 LongMemEval-V2 AgentRunbook-R 完整 Small（web + enterprise），使用完整轨迹、截图、问题、Reader、采样/思考/预算、评分入口和冻结上游代码；micro/prefix、截短轨迹、占位截图、text-only 或压缩预算只作诊断。
2. Native Small 完成后立即跑同一官方数据/入口下的 RAG+Notes，不把它放入 backlog 或等机制任务之后。
3. 随后沿真实 AgentRunbook-R 写入/查询路径增加阶段计时，再做依赖感知调度、细粒度失效、合法复用和一致发布；分开报告 B0/B1/B2/强 B3/Ours，不能削弱强 B3。
4. 冻结开发配置后，在独立数据上完成官方质量与至少 3 次配对重复，并按同一到达协议测真实流式 Freshness P95、Goodput 和阶段成本；checkpoint latency 不得代替 Freshness。

官方 Judge 的 native reference 保持 gpt-5.2。2026-10-14 的实测中，LabForge 上该请求返回 HTTP 403/error1010；这只能记录为 judge_unverified/pending_judge，不能据此改称 gpt-5.6 官方 Judge。若使用已实测可用的 gpt-5.6-terra，结果必须单列为 adapted-matched 或 evaluator-only，不得与 pending_judge 或官方 hosted QA 分数合并。web 与 enterprise 截图下载可并行写入；resume 不保证复用同一个 incomplete 文件，两个归档都必须独立按大小、哈希和 gzip -t 校验后再准备数据。

若原计划中的 GPT Reader/Controller 在当前可用服务中不可用，用户已授权以阿里云兼容 API 的相近 Qwen 模型推进。此时仅作为单列 `adapted-matched`：本轮用 `qwen3-vl-plus` 处理完整视觉轨迹与 Reader，保留原温度、top-p、top-k、thinking 开关和输出预算；本地 Qwen3-Embedding-8B、冻结 AgentRunbook-R 算法、LongMemEval 官方题目/截图/评测入口不变。`qwen-plus` 只可用于 `evaluator-only`，不可计为官方 Judge。API key 通过运行时 `ALIYUN_API_KEY` 环境变量传递，不存文件、不进日志；原生 GPT 结果仍为 pending，不以适配分数代替。

## 1. 历史 v4 内部开发阶段（已完成，保留作证据）

1. 用一次短检查确认现有 GPU 作业归属、可用模型服务与输出进度。已有作业由其执行者在合适边界处理，不能杀不明归属进程，也不能重复装载两套 Qwen。**不重新做全机资源搜索或 P0。**
2. 阅读 `src/workflow_memory/live_pipeline.py` 中实际调用的构建接口，沿用已有本地 Qwen backend、数据适配器、`build_fresh`、`apply_delta` 与 `validate_snapshot`。当前真实 Fresh + incremental replay 只算 smoke/语义检查，下一步就是把增量方法接到真实 backend。
3. 实现或复用一个窄入口 `tools/run_fast_compare.py`，只负责固定工作负载上的两种方法、计时与调用统计、逐 checkpoint 落盘和结果 CSV。**不要先重构整个 live_pipeline、补全 tune、造通用调度框架或等待原生基线。**
4. 同一条短窗口先跑通 B0 与 Ours-dev，各自产生真实调用与可读取的快照；立即运行下面的 4 窗口配置。第一张表生成后分析差距并继续 F1/F2，不在“入口已实现”处结束。

若需要确认入口，可在读取现有函数签名后实现以下命令合同；它是待实现入口，不宣称目前已经存在：

```bash
PYTHONPATH=src /data/predator/ly/Mem/.venv/bin/python tools/run_fast_compare.py \
  --config configs/runtime.local.json \
  --manifest manifests/fastloop_dev_v1.json \
  --methods B0,Ours-dev \
  --out runs/<new-run-id>
```

已有等价命令时直接复用，在 STATUS 记下真实命令，不为统一命名重写程序。参数变化派生新配置，不能覆盖活动实验使用的 runtime 或已有结果。

## 2. 历史 F0 数据与资源约束（已完成，保留作证据）

- Python：`/data/predator/ly/Mem/.venv/bin/python`。
- 配置：`configs/runtime.local.json`；这是包装对象，模型设置在 `plan.models`，路径在 `paths`。
- 模型：已存在的 Qwen3.5-9B 构建模型；Qwen3-Embedding-8B 在后续完整索引计时中复用。优先使用已经工作的加载方式或现有服务，不再并行建设多个 OpenAI-compatible 服务。
- 数据：使用 `data/longmemeval_dev.jsonl`。本次已生成 `manifests/fastloop_dev_v1.json`：固定 seed=17，按 SHA256("17:"+trajectory_id) 选择 web/enterprise 各 2 条至少 8 事件的轨迹，取最多前 12 事件。具体窗口为 `0db80092`（12）、`170f5570`（9）、`4a5f0d7f`（12）、`ec6c60c2`（12），共 45 个源事件、12 个 checkpoint。检查源哈希和解析一致后直接用，不再重选数据。
- manifest 已固定轨迹/事件 ID、顺序、源文件哈希、checkpoint、输入模态和选择规则。checkpoint 为 4、8、12，9 事件窗口为 4、8、9。预设 checkpoint 是外部实验请求，不把未来内容、最终标签或未到达事件交给构建算法。
- 这是派生开发构建工作负载，不是官方 Small/Medium 复现。先核对已有文本字段；缺截图时两种方法统一使用现有文本输入并标记 `text-only`。完整视觉包、官方题目映射与 Judge 均不是 F0 的必要输入。
- 不下载整套截图来解锁文本构建对比。不另建全量数据仓库；已下载的完整 trajectories 保留，可在扩量时使用。

选择样本后固定，不根据输赢更换。正式数据暴露情况如实记录；这轮开发数据不能之后改名为 held-out 正式集。

## 3. 历史 F0/F1 方法与公平比较（已完成，保留作证据）

| 方法 | 当前用途 | 必须实际执行的行为 |
|---|---|---|
| B0 / Fresh Serial | 第一张表的基础 baseline | 每个预定 checkpoint 从该前缀重算同一构建规范；单 worker；不复用上个 checkpoint 的派生计算结果 |
| Ours-dev | 第一张表中的当前实现 | 首 checkpoint 真实构建，后续用同一事件序列更新；复用本方法已有有效节点，缺失/失效节点必须真实调用；记录实际启用的机制 |
| B3 / Strong Incremental Parallel | 第一张表之后的首要强对照 | 合法缓存、保守分区失效、有界并发与正确分区提交；不能用故意清空缓存或全局长锁削弱它 |
| B2 / Incremental Serial | 需要分解并发贡献时补 | 缓存和保守分区失效，单 worker |
| AgentRunbook-R native/adapted | 后续外部基础对照 | 使用冻结上游代码与匹配数据；原生与本地适配配置分开标记 |
| MemForest 及其他外部系统 | 后续补充 | F2 已有可比数据后再决定接入顺序，不在首表关键路径 |

B0 与 Ours-dev 接收相同外部 checkpoint 请求，输出相同必需视图。共享表示、提示词、窗口、模型精度、截断和输出预算；分别使用独立 store/cache，禁止 Ours 读取 B0 记录的响应作为免费模型调用。权重可常驻复用，方法计算结果不能串用。重复实验分别从空方法状态开始。

同一 GPU 预算下顺序执行方法，记录共享服务/并发干扰。冷启动加载耗时单列，计时前两种方法遵循相同 warm-up 规则。F0 并发度先固定为 1；Ours 尚未启用完整机制时就叫 Ours-dev，不能叫 Full。

F0 的 B0 是合法基础参照，但它只回答“当前增量实现相对 checkpoint 全量重算的收益”。**不能据此宣称胜过强增量方法或论文新颖性成立；下一优先级是 B3。**

## 4. F0：第一张真实对比表

### 最小实现范围

窄 runner 完成：规范化已选数据 → 调用已有方法 → 在同一 checkpoint 验证可读取快照 → 记录实际工作量 → 输出表。模型请求至少记录 method、window、checkpoint、request hash、input/output tokens、elapsed、成功/失败。每个 checkpoint 完成就追加落盘并刷新文件；某窗口失败保留失败行、继续其他可执行窗口，不让最后一步失败抹掉此前数字。

本轮可以采用 `construction_kernel` 口径，包含相同的抽取、状态/关系/工作流处理和本地发布，准确列出实现中实际存在的阶段；若 Embedding/向量索引、Reader、模型冷加载尚未纳入，就在两种方法中一致排除并明示。**此口径的延迟叫 checkpoint construction latency，不能叫端到端 Freshness。** 核心状态或必需视图没有正确生成时先修复，不能通过减少某个方法的输出伪造提速。

只补必要的计时、真实 backend 调用、失败留档和快照校验。通用断点恢复、批量调参器、完整报告生成系统可以后补；不要求先实现它们才开始测量。

### 本阶段必须交付

1. `results/tables/first_compare.csv`：至少 B0 和 Ours-dev 两行已实测汇总，附各窗口/各 checkpoint 明细路径；失败项保留状态，不造齐全的数字。
2. `reports/first_compare.md`：方法、工作范围、样本数、输入模态、计时边界、原始 run 路径、结果差距、最大瓶颈和下一项代码改动。
3. run 下可追溯的 manifest、逐请求及逐 checkpoint 记录，包含失败尝试。

第一张表至少包含：

```text
run_id, method, config_hash, workload_hash, input_modality, scope,
n_windows, n_checkpoints, successful_checkpoints, failed_checkpoints,
initial_build_s, update_total_s, checkpoint_latency_p50_s, checkpoint_latency_p95_s,
live_model_calls, input_tokens, output_tokens, reused_nodes, invalidated_nodes,
snapshot_checks_passed, qa_status, raw_metrics_path
```

不支持的 token 统计写 null 和原因，先补 tokenizer/响应 usage 插桩，不用字符数冒充 token。小样本 P95 只作描述，附样本数，不作稳定尾延迟结论。未有官方 QA 就写 `not_evaluated`，不能填 0 或 accuracy=1。模型输出异常或服务失败计入失败比例，不能只汇总有利成功窗口。

对共同成功的配对 checkpoint 汇总耗时/调用/token 变化，同时报告两边全部失败数。Cold Build、后续 Update 和整轮 Total 分开。B0 每个 prefix 全量构建的多次成本，与 Ours 完成相同 checkpoint 服务请求的成本比较；不能混成“一次最终构建 vs 所有在线更新”。

**F0 完成条件是文件中有这轮真实数字，而不是创建脚本、打印 help、跑离线测试或 native smoke。表生成后立即分析并进入 F1/F2。**

## 5. F1：补全计时边界与强 B3

先延用 F0 相同窗口，不扩数据、不新增外部系统。

1. 如果 F0 是 kernel 口径，接上相同 Embedding、索引与可读发布边界，生成 `first_compare_e2e.csv`，保留 kernel 表解释推理与维护开销。完整端到端指标定义沿用参考规范，未来到达率实验再测正式 Freshness。
2. 实现/接通 B3 并真实运行，保持保守分区增量、合法缓存和正确发布，不借用 replay。先 c=1 确保语义，再在可用模型服务上测 c=2；不先扫 1/2/4/8/16 大网格。若后端实际上串行，明确记录有效并发，先获得 c=1 强增量参照，后续修复实际并发，不把仅传了 concurrency 参数叫并行成功。
3. B3 和 Ours 获得相同配置选择机会。数据、视图、缓存有效性、预算均匹配后输出 `dev_strong_compare.csv`。

不要求 B0/B1/B2/B3 全部齐备才能开始优化。先修与当前两/三种方法比较直接有关的正确性问题，再测量。

## 6. F2：围绕已有数字持续优化

每轮只选一个主要瓶颈，先列预期再改代码；默认最多 1–3 个候选，不先实现通用 tune 搜索器。先用 4 窗口做配对实验，方向有效后扩为 12、24 个固定开发窗口。可以直接用现有配置文件和窄脚本循环执行。

| 数字或错误现象 | 优先改进 | 下一轮确认 |
|---|---|---|
| 旧事件反复触发模型调用 | 查不必要的全局版本/上下文依赖，收紧失效范围 | 重算节点、调用量、tokens 及状态检查 |
| Tokens 降了但耗时没降 | 查单请求粒度、队列、重复模型加载与索引成本 | 阶段耗时与调用数，保留同预算 baseline |
| 新输入导致无效传播 | 稳定规范化，分开内容/来源/解释版本 | 传播停止率与来源完整性 |
| 并发越高越慢或 OOM | 调整实际 in-flight/batch，减少无效上下文峰值 | 两边同资源下的吞吐、失败率与延迟 |
| 状态或检索错误增加 | 修 attempted/observed、指代、workflow 上下文 | 明确证据范围的质量题与错误样本 |

每轮更新 `results/tables/dev_iterations.csv` 和简短 optimization_log：baseline/候选 run、改动、耗时与 token 差值、质量/正确性状态、保留或回退理由、下一项。保留失败及负结果。未改善就根据证据改下一处，不能只说“效果不明显”；也不为凑次数重复无变化实验。

首个研究目标是形成 **初版 → 至少两轮有依据的优化 → 强 B3 对照** 的可解释开发曲线；不是承诺每轮都会赢。若已达到预设目标且无进一步合理假设，记录收敛并进入扩量。

## 7. 历史外部 baseline 条款（已由当前主线覆盖）

- **现在延后 MemForest。** 保留已有下载、源码、smoke 和日志；不继续新增适配或额外 GPU 作业，除非 F2 已有结果或当前运行几乎完成且不占主线资源。正在运行的任务由执行者确认归属后在安全边界处理，不粗暴中断有效结果。
- AgentRunbook-R 完整 Small 已从 deferred 移入当前 R5 主线；完整截图、服务匹配和官方入口是当前必要依赖。
- RAG+Notes 已从 deferred 移入 R6，必须紧接 R5 完成；Codex Native 等其他外部方法仍可留作后续补充。
- F0/F1 记录状态校验与真实输出，F2 尽早加入已能定位证据的开发质量题和 Reader；官方 Judge 缺项只影响官方评分。开发 proxy 与官方 accuracy 分列，不能替代论文质量结论。
- 当内部强对照和有效优化曲线形成，冻结配置、数据划分和统计计划，完成官方 Small、Medium、正式配对重复、机制消融及主要外部对照。正式结果不用于继续挑参数。正式表中的科学要求仍按参考规范执行。

## 8. 卡住时的决策规则

**持续推进看的是是否靠近下一张结果表，而不是工具调用数量。**

- 一个准备环节连续约 20 分钟没有增加可运行性或测量证据，就重新判断它是否是 F0 的必要依赖。非必要立即移到 deferred 并回到窄 runner；必要则缩小复现、修复后重试。20 分钟是检查节点，不是硬停止有效计算的超时。
- 同一网络/依赖故障不要机械循环；全量数据/截图等非 F0 必需资源的下载留存进度，主线改用已验证本地数据。不要不断重复创建下载进程。
- 真正必要的模型、核心函数或显存问题需要修好；不得通过离线后端冒充真实结果。GPU 有主线有效作业就等待其进度，同时处理直接需要的 CPU 代码；不要为了“有事可做”重开 MemForest 支线。
- 每个长命令记录输出文件和状态；现有监督脚本可直接用，不扩建新的自动化系统。只在有代码/配置变化或新的失败证据时重复测试。
- 进度消息写清“离第一张/下一张表还差哪个具体动作”。中间汇报后立即做该动作；不能用增加 TODO 或列 blocker 代替执行。

## 9. 当前验收与继续工作

**历史验收（已完成并保留）：** F0 的真实两方法表、F1 的完整计时和强 B3 表、F2 的优化曲线及差样本。它们不再是当前 native Small 的门槛。

**当前验收：** R5 native Small → R6 RAG+Notes → R7 原生阶段计时/依赖机制及 B0/B1/B2/强 B3/Ours 分表 → R8 冻结官方质量、独立至少 3 次重复与流式 Freshness/Goodput。MemForest、通用 tune/恢复框架仍不阻塞主线。

**论文验收：** 冻结后的真实质量、性能、强对照、统计与机制证据充分，原始日志可复现。近期开发表不能冒充正式论文结论。模型/数据/预算相同提高可比性，但本地原生复现仍需核对版本和输入；遇到适配问题继续修复或安排后续，不以“配置相同”代替实际结果。

### 9.1 质量优先接续（2026-10-13）

24 窗口 B0/Ours-dev/B3-c2 的真实 construction_e2e 已完成并保留在
`runs/fast-compare-v4-dev24-batch2-20261013`；当前 R4 不因性能扩量自动完成。
首轮 Reader 代理已完成但精确恢复很低，属于需要修复的负结果，不得用它宣称质量提升。下一轮按以下闭环执行：

1. 先在既有固定快照上真实复测公开步骤时序检索（不读 gold/raw source），比较 source recall、精确字段和语义回答；
2. 修复构建输入保真：失败/告警中间 span、控件值及 `selected/disabled` 等状态字段、action/URL 原字面事实与版本化来源引用必须与 LLM 语义抽取并存，不能以规则答案替代真实模型；
3. Reader 请求同时暴露已发布的 state/workflow/index 受预算限制的视图，避免已有视图只在快照中存在而不进入 Reader；
4. 原 12 题保持不变，补冻成功/失败、状态和语义题；开发 proxy 与官方 QA 分列，gold 仅 evaluator 使用；候选必须在同一窗口、同预算下与 B0/B3 配对真实测量，失败与退化保留。

以上改动均须带新的 prompt/cache/version 哈希；旧 compact-v2 与已有 run 不覆盖。质量有效候选确认后，才进入消融、重复测量、扩量冻结和独立评测。

完成一个当前任务后从 `execution/queue.json` 取下一项。当前 active tasks 为 R5→R6→R7→R8；MemForest、通用 tune/恢复和其他外部系统留在 backlog，不阻塞主线。STATUS 只简述当前命令、最近真实表和下一个具体动作，不再维护多份相互冲突的“大项目完成百分比”。

原生 Goal 的建议表述见 GOAL.md；没有 native Goal 能力时也要在当前轮继续工具执行。文件修改不等于正在运行的 VS Code 会话已读到，接收方式见 EXECUTION_UPDATE.md。

### 9.2 当前接续：质量修复后的机制差距（2026-10-13）

复用已完成的 24 窗口性能、H4a/H4b 与 QA2 真实 Reader 结果，不重启 P0 或旧实验。
H4b 在固定开发 proxy 上恢复了字面证据，但 Ours-dev 与强 B3 的质量仍持平，且
construction_e2e 为 218.883 s / 215.861 s；这不是 Ours 优势。QA2 的 evaluator-only
重评分保留原始输出，只修复 scalar JSON 类型比较，不能记作新的模型实验。

下一轮固定早/中/晚 source revision 的 `revision_stress`，两方法各自独立 store/cache、
相同 Qwen/prompt/batch2 机会，真实调用后记录提取 cache hit/miss、LLM tokens、
实际重建节点分类、可读发布和快照检查；`construction_kernel` 与未测 Embedding
必须明确区分，不拿两种不同定义的 reused/invalidated 数直接作性能结论。
随后按实测决定 `scope_isolation` 与证据保真不变的 Embedding/局部重组优化，
有效候选才进入消融、扩量、冻结和独立数据至少三次重复。官方 QA 继续单列待评。

### 9.3 当前主线：原生 AgentRunbook-R Small → RAG+Notes → 机制与论文评测（2026-10-14）

用户已将下一项交付改为官方外部基线，优先级高于本节此前的 H6 机制候选。保留
`results/tables/first_compare.csv`、24 窗口 B0/Ours/B3、H4/H5/H6 与 18 道开发题
的原始记录，不重跑它们；它们继续作为开发、机制和回归证据，不能代替原生基线或
论文质量结果。当前外部评测目录为 runs/agentrunbook-r-native-small-20261014/adapted-aliyun-vl/{web,enterprise}/。截图恢复及完整数据校验已通过；web 的 adapted-matched Small 已结束但因 Aliyun `HTTP 400 Arrearage` 仅完成 67/100 轨迹，native GPT/Judge 仍标记 pending；失败证据不得升级为 Small 结果。

1. 直接使用仓库 `third_party/LongMemEval-V2` 的冻结 AgentRunbook-R、官方
   `evaluation/run_eval.py`/`harness.py`、`agentrunbook_r.json`、Small haystack
   和对应官方问题。准备完整截图并运行官方 `web` 与 `enterprise` Small；不得用
   micro/prefix、占位截图、截短轨迹、text-only 或压缩预算 smoke 记作完成。
2. native GPT Reader/controller 与 official Judge 当前不可用，用户已授权的替代运行
   使用 qwen3-vl-plus Reader/controller、Qwen3-Embedding-8B、原温度/top-p/top-k、
   thinking、completion/context budget、检索参数和 Reader 协议；qwen-plus 仅作
   evaluator-only。必须标为 adapted-matched，逐项记录模型/端点适配，不能称 native。
3. 当前适配交付目录为 runs/agentrunbook-r-native-small-20261014/adapted-aliyun-vl/，至少包含
   两域逐题答案、调用/tokens、构建与查询阶段耗时、失败/重试、配置与代码哈希、
   评分状态、官方问题/轨迹/截图 manifest。Judge 暂不可用则 `pending_judge`，并
   继续保存构建/查询结果；不能把开发 proxy 填入官方表。
4. Native Small 完成后立即运行同一官方数据/入口下的 RAG+Notes；随后再在真实 AgentRunbook-R 写入路径增加不改变语义的阶段计时，定位
   抽取、note、Embedding、等待、重算、发布和 query 成本。第一轮只改变调度、精细
   失效、合法复用和一致发布；任何新 IR/记忆表示单独做质量消融。
5. 外部 native/matched 对照与内部 B0/B1/B2/强 B3/Ours 必须分表；共享 batch、请求
   cache、通用输入和索引优化，不能削弱强 B3 来制造收益。之后采用相同到达过程的
   流式协议，单独报告 Freshness P95、Goodput 和阶段耗时；checkpoint latency 不得
   充当 Freshness。

截至 2026-10-14，web/enterprise 截图归档已通过准确大小、SHA256、gzip -t、
prepare_data.py 和 validate_data.py（451 questions, 1870 trajectories, 200 Small
unique trajectories, 5095 states；web 240 / enterprise 211）。web 的完整 adapted-matched
运行已结束但未通过完整 gate；其阶段指标写入 memory_build_metrics.jsonl，原始调用写入
memory_workspace/shared/model_calls.jsonl。观察到若干极快 async_text RuntimeError；上游
源码显示每批 asyncio.run() 复用同一个 AsyncOpenAI 客户端；该生命周期修复已在隔离副本中
验证，但本次运行的终止原因是 Aliyun HTTP 400 `Arrearage`。保留当前运行和失败，不覆盖或
重启；隔离 local-text-only smoke 仅作诊断，不能升级为 Small。Judge native reference 保持 `gpt-5.2`；
已知 LabForge 请求 HTTP 403/error1010，不能宣称官方 hosted QA。若采用已实测可用的
`gpt-5.6-terra`，只标 `adapted-matched`/`evaluator-only`，与 `pending_judge` 分开。

#### 2026-10-14 04:52 接续记录

- adapted web Small 已结束并失败：5322.23s，67/100 trajectories success，1 failed；
  `model_calls.jsonl` 1490 行（1398 success、67 RuntimeError、15×429、10×400），终止错误为
  Aliyun `Arrearage`。`failure_summary.json` 与全部原始日志保留；缺少完整
  `memory_build_summary.json`、`prompt_build_summary.json`、`per_question.jsonl` 和
  `aggregated_metrics.json`，因此 R5 仍 `in_progress`。
- 隔离 `local-text-only` runner 已加入显式 `--text-only`、强制本地导入优先、
  `adapter_provenance.json` 和本地 embedding tokenizer 默认；
  `smoke-run-enterprise-v3` 用本地 Qwen 完成 1 trajectory/1 question、4-state prefix，
  prompt `image_url=0`，评分 0/1，明确为 `diagnostic-text-only`，不计 official/native Small。
- 下一实际动作：保持失败目录不变，继续不依赖外部视觉服务的窄 RAG+Notes/内部机制验证；若
  获得可用视觉端点，再在新目录重启完整 web→enterprise adapted-matched，否则把 R5 的
  native/adapted 部分明确记为外部服务阻塞而不填假分数。
