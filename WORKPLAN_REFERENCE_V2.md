# 历史研究规范：方法与正式评估参考

当前执行顺序、优先级和阶段门槛以 WORKPLAN.md v4 为准。本参考中的旧 P0–P7、MemForest 优先级和工程前置依赖已经被替代。仅按需查阅科学定义。

# Agent Memory Construction — Implementation & Experiment Workplan v2.0

日期：2026-10-12。目标会议：WWW。执行对象：能够读写项目、运行命令和调用已配置模型服务的 Codex。

## 0. 任务合同

完成一个可运行的研究系统，并以真实模型调用、真实数据、完整日志得到论文级实验结果。核心方向为：**工作流上下文分层、依赖驱动的增量维护、并发准备与一致发布**。

本计划替代 v1.0 的执行顺序和实现细节，保留 LongMemEval-V2、统一模型内部对照、外部原生系统对照与 WWW 投稿目标。

### 0.1 执行原则

1. 以实现和改进为主线。首轮收益不足时进入诊断与优化，不把早期 profiling 写成项目终止条件。
2. 每个阶段都产生代码、可运行命令和可检查产物。阶段验收失败就修复；通过后自动继续。
3. 先跑通小规模真实链路，再逐步扩大。不要等所有外部系统复现完成才开始自己的方法。
4. 持续保存结果，禁止把模拟时间、缓存回放、占位数字或外部论文数字标成自己的实测。
5. 完成计划不等于保证达到预设收益。若优化迭代后某项目标仍未达到，交付最佳真实版本、全部证据和具体剩余问题，不能把未达标写成达标。
6. 不需要为常规实施步骤重复征求许可。真正缺少计算资源或凭据时才请求必要信息，同时继续独立工作。

### 0.2 研发目标与结果口径

以下是优化方向，不是已有结论，也不是筛掉不好看的运行的条件：

- 在相同硬件、服务预算、到达序列、构建语义和质量约束下，争取相对强 B3 降低至少 20% 的 P95 Freshness。
- 争取减少至少 30% 的更新阶段构建输入 Tokens；同时报告输出 Tokens、总调用、真实 GPU/API 开销，不能只选有利口径。
- 相对同算法 Fresh 参照，开发目标是 QA 差值不低于 -2 个百分点；正式统计使用预注册的不劣界和配对区间，不能把“不显著”解释成“等价”。
- 确定性差分与故障测试中不允许未解释的丢失更新、错误失效、混合快照或重复状态变更。
- 官方最终 QA、过程中新状态的可读性、工作流知识保留都要测，避免只优化吞吐。

## 1. 方法定义：所有实现围绕这套构建语义

### 1.1 三层记忆

| 层 | 输入 | 输出 | 主要更新触发 |
|---|---|---|---|
| Evidence | 前状态、动作、后状态、截图、任务静态目标及必要的已知上下文 | 有来源的局部观察和候选事实 | 对应源输入变化 |
| State / Relation | 局部证据、身份解析、相关旧状态 | 状态投影、别名、关系、历史有效区间 | 相关证据或关系变化 |
| Workflow | 有序证据、步骤分组、已知阶段与结果 | 可检索的阶段摘要、程序笔记和经验 | 相关工作流片段变化 |

原始观察追加保存。LLM 抽取错误可以生成修订或撤销记录，不能用“证据不可变”阻止纠错。当前状态是对证据的派生视图，不把动作意图当成成功结果。

局部抽取不携带未来动作、最终成功标签或整条历史的动态摘要。未解析指代先保留 source span 与引用，再由 Resolver 消解。需要上下文的事件可以读取一个明确记录版本的上下文包，所有读取进入依赖集。

### 1.2 统一计算图

将操作表示为有版本的计算节点：

`Source → Extract → Resolve → State/Relation/Workflow View → Embed → Publish`

执行事件之间的先后关系用于因果解释；节点实际读取关系用于调度、缓存和失效。不要把原始轨迹整条因果链直接变成抽取阶段串行链。

同一构建规范定义 `F(H_prefix, config)`。Fresh 每次从源输入重算这个图；Incremental 保留有效节点，仅计算必要变化。保持分组规则、输入排序、摘要提示词、输出规范化和读取预算相同。

增量与全量精确一致性的适用条件是：计算依赖完整、计算图生成规则固定、外部非确定性调用由相同请求映射为固定响应。真实在线 LLM 下单独测质量稳定性，不声称字节级确定。

### 1.3 三个核心机制

**M1：上下文依赖分层。** 将局部观察与持续变化的工作流解释分开；旧局部事件不因新增无关步骤自动失效。粒度必须由真实事件内容决定，不把每个字或每个属性都拆成一次模型调用。

**M2：精确失效与传播停止。** 通过反向依赖找到受影响节点；重算后比较规范化输出。内容未变则停止传播到仅依赖内容的节点。内容、来源集合、工作流解释各自版本化，下游声明读取的字段。

**M3：依赖调度与一致发布。** LLM、Embedding 和候选视图生成在事务外并发执行；短事务校验读取版本并发布。独立组件可分别完成；跨对象状态/关系在同一发布单元内保持一致。

只对精确规范化字段做变化停止，不使用“Embedding 相似度很高”直接判定状态等价。若以后加入语义等价判定，必须作为单独方法和消融。

### 1.4 第一版数据结构

至少实现下列结构，可采用 dataclass/Pydantic + SQLite；无需先引入分布式框架。

```text
SourceEvent:
  event_id, trajectory_id, environment_family, environment_instance_id?
  source_sequence, source_revision, arrival_sequence, observation_time?
  goal, pre_state_ref, action, post_state_ref, screenshot_hashes
  observed_outcome?, causal_predecessors, raw_content_hash

Evidence:
  evidence_id, source_refs, source_versions, source_spans
  subject_ref, predicate, value, modality, certainty
  event_kind: intent | attempt | observation | confirmation | failure
  valid_scope, content_hash, provenance_hash, revision

ComputeNode:
  node_id, operator, operator_version, prompt_hash, model_fingerprint
  read_dependencies[], read_fields[], predicate_scopes[]
  output_refs[], content_hash, provenance_hash, interpretation_hash
  status, input_fingerprint, retry_count

PreparedUpdate:
  update_id, source_event_ids[], read_version_vector
  affected_scopes[], writes[], index_delta_ref, predecessor_updates[]

PublishedSnapshot:
  epoch, parent_epoch, object_versions, index_manifest
  included_event_frontier, included_update_ids[], checksum
```

`environment_family` 不能替代环境实例 ID。没有跨轨迹持续状态证据时，状态键以 trajectory/episode 隔离；可复用程序知识按环境家族共享。不要用两个轨迹的记录顺序臆造同一个世界的状态演化。

## 2. 工程组织与接口

### 2.1 项目布局

已有相关仓库时在其中建立清晰子目录；没有时创建 `memory-construction/`。执行包文件可位于代码根目录，也可通过 `--plan` 显式指定。

```text
memory-construction/
  WORKPLAN.md, STATUS.md
  pyproject.toml
  src/workflow_memory/
    __main__.py, cli.py, config.py
    adapters/longmemeval_v2.py
    adapters/agentrunbook_r.py
    adapters/memforest.py
    adapters/codex_native.py
    ir.py, event_store.py, extract.py, resolve.py, views.py
    dependency.py, cache.py, scheduler.py, commit.py, retrieval.py
    telemetry.py, replay.py, evaluation.py, statistics.py
  prompts/                 # 独立版本化，不散落在脚本中
  configs/                 # plan / runtime / frozen
  manifests/               # 数据划分、工作负载、版本、模型
  tests/                   # 有意义的语义、故障及契约测试
  third_party/             # 固定版本原生基线；改动以 patch 留档
  data/                    # 原始数据只读，派生数据独立目录
  runs/<run_id>/
  reports/
  results/tables/, results/figures/
```

不要修改原生基线的算法来便利比较。适配器改动、计时插桩和方法改动分别保存并说明。

### 2.2 要实现的 Python 接口

```python
normalize_trajectory(raw) -> list[SourceEvent]
plan_graph(history_prefix, algorithm_config) -> ComputeGraph
build_fresh(history_prefix, model_backend, config) -> Snapshot
apply_delta(snapshot, events, model_backend, config) -> UpdateReceipt
query(snapshot_id, question, retrieval_budget) -> EvidenceBundle
validate_snapshot(snapshot_id) -> ValidationReport
```

`UpdateReceipt` 区分 accepted、prepared、committed、queryable。Freshness 只使用满足预定义读语义的 queryable 时刻。

官方适配器实现其仓库要求的 `insert(trajectory)` / `query(question)` 接口。流式控制器调用自身 `apply_delta()`，不要伪称官方接口支持逐事件原生流式输入。

### 2.3 要实现的 CLI 契约

下列命令在本计划编写时尚不存在。P0 先建入口，各阶段补齐能力；未实现的命令明确报错，不得空跑后返回成功。

```bash
python -m workflow_memory doctor --plan configs/experiment-plan.json --out configs/runtime.json
python -m workflow_memory prepare-data --config configs/runtime.json
python -m workflow_memory run --suite pilot --config configs/runtime.json
python -m workflow_memory check --suite correctness --config configs/runtime.json
python -m workflow_memory run --suite dev --config configs/runtime.json
python -m workflow_memory tune --config configs/runtime.json
python -m workflow_memory freeze --config configs/runtime.json --out configs/frozen.json
python -m workflow_memory run --suite main --config configs/frozen.json
python -m workflow_memory run --suite scale --config configs/frozen.json
python -m workflow_memory run --suite ablations --config configs/frozen.json
python -m workflow_memory run --suite stress --config configs/frozen.json
python -m workflow_memory report --runs runs --out results
python -m workflow_memory reproduce --manifest results/reproduce_manifest.json
```

`run` 支持 `--resume` 和 `--dry-run`；dry-run 只能生成任务清单及资源估算，结果状态必须为 planned。正常运行输出 run_id 和日志路径；失败返回非零状态。断点恢复逐节点验证缓存与源版本，不能只看输出文件是否存在。

## 3. 环境与模型

### 3.1 自动发现

发现当前项目、Python、GPU/显存、可用磁盘、已有数据缓存和已配置模型服务。只在项目、用户明确给定路径和常规模型缓存内查找；不读取无关历史会话。报告凭据存在与否，不记录值。

Windows 机器可以使用已有 WSL/Linux 服务或远程 OpenAI-compatible 端点；不要假定原生 Windows 的推理服务与 Linux 配置等价。也不要假定 9B 构建模型与 8B Embedding 模型一定能同时装入当前 GPU。

### 3.2 统一内部实验栈

| 角色 | 指定模型 | 冻结要求 |
|---|---|---|
| Extraction / Resolve / Workflow | `Qwen/Qwen3.5-9B` | checkpoint、模板、视觉预处理、精度、上下文、采样、输出限制 |
| Embedding | `Qwen/Qwen3-Embedding-8B` | checkpoint、截断规则、query instruction、维度 |
| Reader | `Qwen/Qwen3.5-9B` | 官方 QA 读取配置与证据预算 |
| Judge | `gpt-5.2` | 请求模型、返回模型标识、提示词、reasoning 设置、日期 |

内部性能默认使用一致的低随机性构建配置；temperature=0 也不等于硬件级确定性。确定性验证仍使用按请求内容索引的响应回放。

原生 Baseline 保留固定版本对应配置。LongMemEval-V2 原方案中的 Codex v0.117.0、`gpt-5.4-mini` / xhigh、Judge medium 等在执行前与冻结仓库核对并记录。原生 Codex Memories 使用独立源码版本，不能与 V2 检索基线版本混同。

### 3.3 资源缺失时的推进

优先复用已有服务和缓存。无法调用指定模型时先完成数据、计算图、存储、回放、差分、日志和测试；列出唯一必要的资源缺口。开发替代模型只能进入标记为 exploratory 的运行，不与正式配置合并统计。

每个 suite 执行前生成调用量、数据量和存储需求估算。遵守用户已有预算及服务限流；没有预算配置时不要凭空设定金钱额度。新购买资源需要用户另行授权，使用现有已授权服务继续推进。

## 4. 数据和信息可见性

### 4.1 固定来源

- LongMemEval-V2：`https://github.com/xiaowu0162/LongMemEval-V2`。
- 本次审查参考 commit：`2cc8c540bdb87fe6761629b585e727e1c4704520`。
- 数据：`https://huggingface.co/datasets/xiaowu0162/longmemeval-v2`，执行时解析并固定 dataset revision 和校验和。
- MemForest：`https://github.com/Concyclics/MemForest`。
- 本次审查参考 commit：`2b5af6d9f92618b30f3e8b7eb99412c1d5eddd6d`。

优先用这些固定版本；不可获取或存在已确认修复需求时记录替代 commit 与差异。禁止在同一正式实验中混用移动的 main。

### 4.2 数据适配要点

公开轨迹主要是有序 state/action 记录，包含 thought、AXTree 和 screenshot，并不自带完备的语义读写集。第一版以“前状态—动作—后状态”构造 SourceEvent，不假装拥有原始工具运行时的所有事件字段。

审查版本的 Schema 与代码对 action 位置的措辞存在差异。适配器必须检查真实样本和官方转换函数，确定动作对应的前后状态，形成可视化/文本对齐样例并测试；不要仅靠字段说明猜测。

截图与文本都参与源哈希。所有方法保留相同可访问的证据类型。若提供文本实验，独立标为 text-only，不能与保留截图的方法直接做质量归因。

### 4.3 三套协议

**A / Official QA：** 使用冻结版本的官方 Small/Medium 清单与评估器，保留官方 Reader/Judge 行为。报告 Accuracy、类别准确率和原定义 Query Latency。

**B / Streaming Construction：** 从同一原始轨迹生成在线回放。单轨迹内部顺序固定，跨轨迹到达顺序由清单定义。只暴露当前前缀，outcome 仅在结束事件到达后可用。不得提前读取未来截图、完整动作 trace、最终轨迹长度或最终标签。依赖分析和分组决策同样受此限制。

**C / Controlled Stress：** 重复投递、乱序完成、源修订、跨对象冲突、失败重试等受控负载。逐项标明 derived/synthetic 与修改内容；只用于机制与正确性，不混入官方 QA。

### 4.4 开发与正式数据

先生成轨迹重复、近重复、共享实体和 Small/Medium 重叠报告。Small 的同一 domain 问题共享历史，不能随机分题后就宣称历史互不泄漏，也不能把 451 道 QA 当成 451 次独立构建工作负载。

优先从不属于正式 Small 的轨迹组选择开发窗口，按环境/episode/近重复组隔离。Medium 若包含这些开发轨迹，标明暴露比例，并另报未暴露子集。

若无法获得完全隔离的开发历史，仍完成官方协议复现，同时把它标为标准化 benchmark evaluation；另外生成固定分组的开发/测试系统窗口，明确该部分是派生协议。不得凭空宣称 held-out。

开发质量题优先使用可从前缀明确定位答案的状态、失败和工作流题。自动构造题记录生成者、证据范围与交叉核验结果，不叫人工金标。官方答案只交给评估器；开发选择不读取正式测试错误逐题调参。

## 5. 内部对照与外部基线

### 5.1 同一分层算法的执行对照

| ID | 名称 | 重算与调度 |
|---|---|---|
| B0 | Fresh Serial | 每个规定 checkpoint 全量重算，单 worker |
| B1 | Fresh Parallel | 同一全量计算图，有界并发 |
| B2 | Incremental Serial | 使用缓存，按保守分区失效，单 worker |
| B3 | Strong Parallel + Incremental | 缓存＋局部分区失效＋有界并发＋正确的分区串行提交 |
| Ours | Full | 精确依赖＋传播停止＋依赖调度＋一致发布 |

所有组共享证据表示、提示词、逻辑分组、Reader、检索预算、必需视图与正确性规范。B3 允许合理批处理和已实现的局部优化；不能人为加全局长锁、移除缓存或制造错误使它变弱。

B0/B1 在大量 checkpoint 上可能昂贵。完整历史做冷启动全量；逐前缀 Fresh 差分在预先固定的 checkpoint 上执行。B2/B3/Ours 使用同一流式事件序列持续更新。不同工作范围的结果分表，不能把每前缀全量时间与单次冷启动时间混算。

### 5.2 方法消融

- Representation：完整轨迹上下文抽取 vs 分层抽取。这是记忆算法变化，单独测质量和计算，不宣称两者语义完全相同。
- Ours - precise invalidation：失效扩大到 B3 的保守分区，保持输出语义。
- Ours - early stop：受影响节点全部传播重算，保持输出语义。
- Ours - dependency scheduling：保留精确增量，使用 FIFO/分区队列。
- Ours - coalescing：关闭批内合并，检验批处理贡献。

前三个执行消融用一致参数控制；最终方法与 B3 的公平性能比较允许双方使用相同开发预算分别调优。初版验证器不能在正式实验中作为“可关闭提速开关”。

### 5.3 外部系统执行优先级

1. AgentRunbook-R：先接通真实数据和官方 QA，记录原生抽取与笔记耗时。
2. MemForest：尽早接通构建与检索；研究在线流式时检查其 asynchronous implementation，不能只测兼容层粗锁。
3. RAG+Notes：作为轻量质量与写路径对照。
4. Codex Native Memories：适配线程/轨迹和隔离工作区，区分调度等待、提取、整合、持久化。
5. V2 Codex 与 AgentRunbook-C：完成官方 QA/Query Latency 对照，放独立表。若使用 C v2，版本与在线学习设定独立命名。

外部原生配置与统一模型适配配置分开。对多模态不原生支持的系统，任何文本化/视觉描述前处理都计入构建耗时和费用，并单列信息损失。没有忠实实现完成前不得称为原生复现。

Codex Native 可能等待会话空闲再更新。原生运行报告完整调度延迟；比较构建内核时在已符合输入资格的相同任务上计时，并明确已剥离调度政策。禁止把小时级默认等待直接算成我们算法的加速。

## 6. 缓存、依赖与发布的实现约束

### 6.1 缓存键与有效性

缓存键包括 operator/schema/prompt/model 版本、完整请求内容、截图内容哈希、实际读入对象的相关字段版本、上下文规则与采样参数。不要无差别纳入全局 epoch 或整个 history hash。

节点 ID 不能使用 LLM 的自由文本实体名称作为唯一身份；源节点由 trajectory/step/revision 构造，派生节点由稳定 scope、操作和参数构造。

对“查无匹配记录”、范围检索、候选集合变化，记录 predicate/scope version，避免新对象插入后漏失效。结构化 context provider 返回已实际读取的依赖集，LLM 输出的 memory_keys 仅为候选。

未知关系保守扩大到可界定的作用域，先用 trajectory/episode；无法界定时扩大到相关环境分区。记录回退范围与原因，尽量通过更好的解析逐步减少扩大范围，不能隐瞒依赖不确定性。

### 6.2 传播与历史

同一对象状态重复不等于新证据不存在：Evidence 追加，来源视图更新；只依赖内容的节点可以跳过。字段比较规范化需保持时间、否定、失败、单位和对象身份。

完整历史依据源事件顺序与显式有效时间解释，不能按 worker 完成顺序覆盖“最新状态”。无法建立不同 episode 的时间关系时保留并列事实及作用域。

分组采用固定事件区间或可重建的确定规则。若采用封口片段＋可变尾部，片段关闭条件不能偷看未来。Fresh 与 Incremental 重建相同分组；动态重分组单列为算法变体。线程完成顺序不得改变逻辑分组；批内合并只省去可安全跳过的中间计算，规定 checkpoint 上仍须得到同一 F(H_prefix)。若合批抽取改变模型请求及记忆内容，将其作为算法变体同步应用到所有内部执行对照，再重新验证质量。

### 6.3 并发与事务

以有界 asyncio/task worker 为起点。记录 ready、queue、model、retry、validation、embedding、commit 等耗时。LLM 请求期间不持有数据库写锁。

提交前验证实际 read set、predicate scopes 和 predecessor updates。冲突重试从最新合法输入重算；连续冲突后降为该作用域的串行队列，不能无限旋转重试。合并重复更新时保留每个源事件的覆盖记录。

SQLite 短事务分配发布 epoch 并提交对象版本/索引 manifest。Embedding 或索引文件先写独立临时版本，校验并持久化后再发布引用。Reader 绑定一个 epoch，按对象版本范围和该 epoch 的索引读取；后台索引压缩不改变可见语义。

跨作用域更新在一个短事务中发布。Reader 可以读到尚未包含待处理新事件的旧一致快照，但不能混读同一事务的新旧半份。这样的旧快照不算新事件已经 freshness 完成。

## 7. 阶段执行清单

### P0 — 环境、数据、项目与可恢复运行

**执行：**

1. 读取项目指令，发现资源，建立代码根目录及独立环境；复用可用依赖。若执行包位于代码目录之外，将工作计划、配置与状态复制到代码根目录，记录原件路径，此后以代码根目录的状态为准。
2. 实现 doctor、配置解析、run_id、结构化日志、resume 与任务清单。
3. 固定源码和模型标识；下载/检查必要数据，先准备开发轨迹对应截图。
4. 核对动作与状态对齐、outcome 释放时刻、截图引用、重复轨迹及划分。
5. 运行文本、双截图、Embedding 和 Judge 小请求，实际检查响应结构与模型标识。

**产物：** `reports/environment.md`、`configs/runtime.json`、`manifests/versions.json`、`manifests/data.json`、`manifests/splits.json`、`reports/data_audit.md`。

**完成：** 指定资源的可用/缺失状态明确；可用链路真实 smoke 成功；缺失资源不以占位成功掩盖。模型未通时先进入不依赖模型的实现任务。

### P1 — 真实基线闭环与耗时分解

**执行：**

1. 在隔离开发数据中固定 24 条轨迹：web 与 enterprise 各 12，尽量覆盖成功、失败、长短轨迹与多步状态变化；不足时按实际数量记录。
2. 先对 4 条轨迹跑 AgentRunbook-R 的真实构建、持久化、检索和 QA，再扩展 24 条。
3. 为基线添加 observer-only spans；记录逐调用输入规模、图像数、Tokens、错误和重试。
4. 接入 MemForest；同步记录批量路径与在线异步路径适配差异。
5. 输出瓶颈排序与具体优化任务；马上进入 P2，不等待其余外部系统。

**产物：** `reports/baseline_profile.md`、`results/tables/pilot_baselines.csv`、至少一组真实调用与 QA 日志、阶段耗时图。

**完成：** 能定位耗时来自上下文、推理、重复维护、队列还是持久化。收益暂不明显时选择对应 P5 路线继续。

### P2 — 分层构建算法与 Fresh 参照

**执行：**

1. 实现 IR、局部证据抽取、Resolver、State/Relation/Workflow views 和统一检索接口。
2. 将局部抽取的依赖限制到实际需要的观测和已知上下文；工作流层允许读取相关有序片段。
3. 定义 observed/attempted/failed 的状态语义，处理未解析指代与失败动作。
4. 实现 B0 与 B1；保存逻辑图、输入指纹、节点输出和出版快照。
5. 在同一开发集比较原始完整上下文抽取与分层抽取的质量、Tokens、调用数量和状态错误。

**优化：** 质量丢失时先检查上下文缺失、指代与截图解释，再扩大相关局部窗口或补充分区上下文；保留对照，不立刻退回每个事件都带全轨迹。

**产物：** 可运行 Fresh 构建器、`reports/representation_quality.md`、`results/tables/representation.csv`、版本化 prompts 和错误样本。

### P3 — 增量执行与可解释的正确性

**执行：**

1. 实现 B2：保守分区失效＋缓存，先串行完成更新。
2. 实现实际读依赖收集、反向索引、范围依赖与精确失效。
3. 分开内容/来源/解释指纹，实现变化传播停止与必要索引更新。
4. 用相同请求内容映射固定响应；在 10%、25%、50%、75%、100% 前缀以及固定的追加/修订位置比较 Fresh 与 Incremental。
5. 回放遇到新请求时，使用确定性测试后端，或明确采集真实响应后封存；不得按调用次序匹配不相同请求。
6. 验证重复投递、来源修订、别名变化、关系插入、范围查询、未成功动作、不同 episode 同名对象。

**正确性条件：** 规范化内容、来源、历史与检索可见性一致。比较忽略运行时间和物理文件顺序，不能忽略本来要验证的状态字段。

**产物：** `reports/equivalence.json`、最小反例、固定 replay manifest、`reports/correctness.md`。有限测试通过不能宣称证明了所有自然语言依赖的完备性。

### P4 — 强 B3、依赖并发和一致发布

**执行：**

1. 实现正确的 B3：分区增量、缓存、并发准备、分区提交；不要添加人为长锁。
2. 实现 Ours 的 ready queue、版本检查、冲突重试、局部串行回退和 Reader 快照。
3. 加入有限批内合并；B3 与 Ours 使用相同到达序列与同等调参预算。
4. 并发度从 1、2、4 开始跑真实模型，稳定后扩展 8、16；实际服务端并发、排队与 GPU 利用率一并记录。
5. 注入 worker crash、提交前后 crash、超时、重复与乱序完成，验证原子发布和恢复。

**产物：** `results/tables/dev_concurrency.csv`、`reports/recovery.json`、冲突率/重试率/提交耗时曲线、B3/Ours 真实运行。

### P5 — 根据结果持续优化，形成正式候选

**执行：**

1. 使用第 10 节的诊断表，每轮明确一个瓶颈、一个改动、一个可测预测。
2. 首先完成默认配置；目标未达到时完成至多 3 轮有根据的机制优化，每个被调优方法每轮最多 12 个候选配置。仍有资源预算时可继续，并在 decision_log 说明新增理由。
3. 每轮先做局部验证，再在同一开发窗口跑 B3/Ours 的配对真实实验；保留所有配置与失败运行。
4. 只在开发数据选择窗口大小、分组粒度、并发、批处理和回退阈值；B3 获得同等优化预算。
5. 选出质量约束下的最佳候选；记录性能、费用、质量的权衡，不只挑最快但损失质量的运行。

**产物：** `reports/optimization_log.md`、`results/tables/dev_candidates.csv`、正式候选与 B3 的配置、剩余性能问题列表。

目标不足触发进一步实现改进，不自动取消后续正式实验。若三轮后进入正式评估，应明确实际达到哪些目标，不能循环调正式测试集直到出现正结果。

### P6 — 冻结与正式实验

**执行：**

1. freeze 检查缺失版本、占位端点、未解决正确性问题、测试数据暴露记录和必需视图定义。
2. 生成 `configs/frozen.json`、实验任务清单和统计方案，锁定选择规则。
3. 跑 Small 正式 QA 和写路径；跑 Medium 扩展；补齐外部系统对照。
4. 跑执行机制消融、到达负载、并发、更新比例和冲突负载。
5. 每种主要性能条件默认 5 个配对重复，随机/交错方法执行顺序。先用短校准确认运行时长足够形成稳定尾延迟；保留全部重复。
6. QA 默认每个主要方法做 3 次独立构建和回答重复，并保留逐题/逐构建对应关系。若原生成本限制重复数，事先记录并分表，不冒充同精度比较。
7. 正式阶段发现 bug 时，登记修复、生成新冻结版本，并重跑所有受影响对照；旧结果保留且标记 superseded。

**产物：** 带完整 manifest 的正式 runs、逐事件/逐题结果、全部模型请求使用量和统计中间数据。

### P7 — 结果整理与论文材料

**执行：**

1. 从原始日志生成第 11 节结果表与图，不手工填写指标。
2. 审计缓存、超时、失败、到达协议、信息可见性、相同 GPU 预算和原生适配边界。
3. 对改进最大的、没有改进的、质量下降的场景分别做可复核解释。
4. 输出方法描述、相关工作对比、实验设置、主要结果、消融和局限；只使用本项目已验证的主张。
5. 从一个干净输出目录执行一组小规模 reproduce，核对 manifest 和结果生成链路。

**产物：** `reports/final_research_report.md`、`results/reproduce_manifest.json`、`results/tables/*.csv`、`results/figures/*.pdf` 与 `.png`、实验复现说明。

## 8. 实验工作负载

### 8.1 冷启动与更新分开

冷启动：空库输入完整指定历史，测首次构建 makespan、质量与成本。

流式更新：从相同固定初始快照开始，使用相同的事件到达清单，测增量延迟与吞吐。初始快照创建成本单独报告，同时给出摊销/端到端总成本，不把基线初建算进更新而把 Ours 排除。

应用层结果缓存与增量中间结果缓存分开。冷启动不允许预置抽取结果；更新实验允许复用本系统在前缀阶段合法生成的中间结果。推理服务前缀缓存设置对所有内部方法一致，分别标记 cold/warm。

### 8.2 到达过程

使用开放到达回放：事件按预定时间进入，不等上一个事件完成再发送。记录排队与积压，不通过闭环发送隐藏过载。

在开发数据上估计强 B3 的可持续事件吞吐 `mu_ref`，生成 `0.25 / 0.50 / 0.75 / 0.90 / 1.10 × mu_ref` 的绝对到达率，并对所有方法使用相同清单。正式数据不重新根据 Ours 速度修改负载。

Primary 流式比较默认使用冻结的 `0.75 × mu_ref`，同时报告整条负载曲线。到达过程至少包含固定间隔和固定种子的突发模式。短轨迹窗口可拼接不同、作用域隔离的 episode；不能把同一原始事件无说明复制成大量独立自然样本。

### 8.3 更新与冲突

- 新增比例：1%、5%、10%、25%、50%、100%，分母为规定前缀的源事件数；新增与原事件修订分开。
- 冲突目标：0%、10%、30%、50%、80%，仅受控负载；定义为同批候选更新之间写写或读写集合相交的比例，并同时报告实际冲突/验证失败率。
- 相同实体不必然冲突，不同实体也可能共享关系；不要用名字重合直接冒充实际冲突。
- History Scale：Small、Medium 与固定前缀。模型输入裁剪策略固定，超限样本必须统计。

先单因素和关键两因素交互，再扩展；不要直接做所有维度的笛卡尔积。默认主线：并发×负载、更新比例×历史规模、冲突率×调度方法。

## 9. 指标、日志和统计

### 9.1 Freshness 与 Goodput

为每个源事件预先定义 required views 和依赖前驱；在更新结果尚未产生前就冻结要求。默认包括相关证据、状态/关系、当时应可生成的工作流视图及可检索索引。任务最终经验只有终止信息到达后才成为必需视图。

`freshness(e) = earliest_queryable_time(e, required_views, causal_predecessors) - scheduled_arrival_time(e)`。

若多个源事件被合并进一次更新，分别保留各自 arrival time。允许正确吸收后续更新的快照覆盖早期事件，但必须证明早期证据与必要历史仍可读取。只写原文或入队不算完成。

Goodput 以预先定义且处理正确的源事件/更新单元为分母，不能按系统自行拆出的 memory 条目计数。端到端计时包含抽取、依赖分析、失效、Embedding、重试、索引、持久化与排队。

超过截止时刻尚未可读的事件记录为 unfinished/censored，单列完成率、积压和违约率。不要从延迟样本中默默删除；无法可靠估计整体 P95 时标为不可估计并给出界限。过载实验与稳定负载分开。

### 9.2 质量与正确性

- 官方整体及分类 QA；同算法 Fresh/B3/Ours 的配对差值。
- 当前状态正确性、失败动作不误记为成功、跨 episode 隔离、历史与来源保留。
- Fresh/Incremental 的 replay 差分；真实模型结果的质量差异。
- 重试、崩溃、重复事件、乱序完成后的状态与读取一致性。
- Reader 证据预算和检索方式固定；外部原生方法独立说明。

语义正确性与事务正确性分开：快照原子不代表 LLM 提取的事实一定正确，LLM Judge 打分也不能代替事务验证。

### 9.3 每次运行必须保存

```text
runs/<run_id>/
  manifest.json                 # 代码、模型、数据、配置、硬件、种子、协议
  status.json                   # planned/running/completed/failed；不是只有成功
  events.jsonl                  # 到达、处理、被覆盖和可读时间
  spans.jsonl                   # 阶段及队列耗时
  llm_calls.jsonl               # 请求哈希、模型、tokens、重试、费用、缓存状态
  dependencies.jsonl            # 节点实际读集、范围读、失效传播
  snapshots.jsonl               # epoch、版本与索引 manifest
  correctness.json
  qa_per_question.jsonl
  metrics.json
  stderr.log
```

本地模型若无法取得美元费用，报告 GPU 秒、GPU 类型与可用利用率；API 费用使用实际可核对单价或账单，缺失写 null，不猜价格。模型服务耗时与客户端网络等待尽可能分别记录。

### 9.4 统计方法

性能以相同 workload/run seed 配对，报告原始各重复、配对比值及区间。事件并非独立样本，使用运行/轨迹组或时间块作为重采样单位，并说明块选择。不要把数千事件当成数千独立环境。

QA 保留逐题配对结果，报告差值区间和跨构建波动。对共享历史相关性做分组敏感性分析；Small 只有少数共享历史时，明确区间适用范围，不声称已刻画跨环境泛化不确定性。

不劣判断：预注册 `delta=0.02`，只有质量差值置信区间下界高于 `-delta` 才支持该口径的不劣。样本不足时报告估计和区间；重复 Judge 不能替代新的独立问题。

P95、成本、质量都报告，不用后验挑一个赢的指标替换 Primary。所有调参和最终选择发生在开发阶段。

## 10. 结果不理想时的具体优化路线

| 现象 | 首先检查的证据 | 执行改进 | 必须保留的对照 |
|---|---|---|---|
| 新事件导致大量旧节点失效 | 节点输入指纹和依赖扇出 | 移除不必要全局版本；分离 overview/state；精确化上下文包 | 修改前后失效图及 QA |
| 抽取 Tokens 很大 | 每节点重复上下文、AXTree、图片数 | 固定局部窗口；相关上下文引用；批内共享静态上下文 | 相同信息与视觉预算 |
| 调用数量超过省下的 Tokens | 单事件调用粒度和网络开销 | 相邻独立局部事件合批抽取，保留逐事件输出及完整批依赖 | 批大小及尾延迟 |
| 工作流 QA 下降 | 丢失的关系、阶段、失败原因 | 增加独立 workflow reconcile；为困难事件扩大局部上下文 | 质量/成本权衡 |
| 状态 QA 下降 | attempted/observed 混淆、指代 | 改事件类型与确认规则；增强 Resolver，保留原始证据 | 来源与当前状态题 |
| 精确增量几乎不停止传播 | 哪个输出字段一直改变 | 内容/来源/解释拆开；稳定规范化；减少无用输出字段 | 来源完整性与状态一致性 |
| 并发变高反而更慢 | 服务端队列、GPU 饱和、KV 占用 | 降并发、统一 token 预算、批调度、缩短关键上下文 | 相同硬件/服务预算 |
| 热对象反复冲突 | read/write 冲突和浪费调用 | scope 内合并、短队列串行化、独立 scope 并行 | 同样批处理机会的 B3 |
| 全局发布阻塞独立更新 | commit wait、snapshot 构建时间 | 短事务、索引 delta、按依赖组件准备与发布 | 混合读取/故障测试 |
| 依赖维护本身太贵 | dependency CPU/LLM spans | 实际输入追踪＋结构化 scope；减少推测性 LLM 分析 | 漏失效反例与回退率 |
| 原生基线适配很慢 | 适配日志和具体不兼容字段 | 独立适配分支；先完成内部/MemForest/AgentRunbook-R 主线 | 如实标明未完成项 |

每轮记录：原因、修改、预期、真实效果、质量变化、是否保留。可以根据证据调整方法实现；改变构建语义时同步更新所有内部对照、版本号和质量验证。

## 11. 最终表格、图和论文叙事

### 11.1 必须输出的表

1. `main_internal.csv`：B0/B1/B2/B3/Ours 的范围匹配结果；Cold Build 与 Streaming Update 分列/分表。
2. `native_systems.csv`：外部系统质量、实际配置、资源和适配开销，不伪装成统一模型排行榜。
3. `official_qa.csv`：Small/Medium、类别、Reader/Judge、原生版本、准确率及重复。
4. `mechanisms.csv`：有效复用率、LLM 工作量、失效比例、传播停止率、回退、冲突、依赖开销。
5. `ablations.csv`：各机制贡献和质量。
6. `correctness_recovery.csv`：故障类型、注入数量、恢复结果、错误和反例链接。

主流式表至少包含 QA 差值、P50/P95/P99、完成率、Goodput、输入/输出 Tokens、GPU/API 成本。指标 NA 必须附原因，不能填零。

### 11.2 必须输出的图

1. 新增证据比例—旧计算失效比例，说明 M1/M2 的作用。
2. 更新规模—实际 LLM 工作量，区分来源复用和下游少算。
3. 到达率—P95 Freshness 与积压/完成率，比较 B3/Ours/MemForest。
4. 并发度—Goodput 与 GPU/队列开销。
5. 关键路径分解，含依赖分析与重试成本。
6. Small→Medium 的时间、成本和质量变化。
7. 质量—延迟或质量—成本散点，呈现方法的实际权衡。

每张图保留对应 CSV、作图脚本、单位、误差区间和运行清单。使用标准科学绘图工具，导出 PDF 与 PNG。

### 11.3 论文主张组织

主张一：工作流解释的变化会扩大传统抽取输入依赖；分层使局部观察产生可测的稳定性。

主张二：字段级依赖与变化传播停止减少维护工作，收益超过依赖追踪开销。

主张三：在固定质量、资源、输入与可见性要求下，依赖调度改善一致记忆的更新延迟。

以上主张逐项用结果支持或收紧。WWW 场景围绕 web/enterprise agent 的多步状态与工作流经验展开；不要只写一般任务调度加速。树形索引、并行抽取、版本检查单独存在并不自动构成新颖性，相关工作比较需说明本方法的具体依赖粒度与语义区别。

## 12. 完成标准与断点恢复

### 12.1 必须满足的执行完成标准

- [ ] 真实模型、真实 LongMemEval-V2 轨迹可以完成构建、持久化、检索和官方 QA。
- [ ] Fresh、B3 和 Ours 可运行，其他内部组及消融已按计划完成。
- [ ] 分层表示、精确失效、传播停止和调度机制都有对应实现与日志。
- [ ] 差分、来源、历史、快照和恢复测试有记录，未解决错误明确列出。
- [ ] 开发阶段优化记录完整，正式配置和数据暴露情况已冻结。
- [ ] Small、Medium、主负载、消融、扩展性和故障实验有真实产物或具体资源阻塞说明。
- [ ] 外部基线逐项标明 completed / blocked / adapted，不隐瞒省略系统。
- [ ] 统计、主表、图和报告均从原始日志自动生成，可追溯至代码和配置。
- [ ] 至少一组小规模 clean-output 复现成功。

基础执行完成与“性能目标达成”“论文可投”分别记录。资源阻塞时只标记受影响项，不把整项研究虚报完成。

### 12.2 继续工作方式

每个阶段/迭代更新 STATUS.md，写下代码目录、活动 run_id、进程/作业标识、已完成项、最新证据、下一条确切命令和阻塞。运行中断后先检查活动进程与状态，避免重复发起昂贵实验。

`reports/experiment_ledger.csv` 记录每次运行的 method、protocol、split、workload、config hash、code commit、model fingerprint、repeat、status、metrics path 与 superseded_by。

`reports/decision_log.md` 记录改变假设、实现、参数、预算和正式配置的依据。不要仅凭上一段聊天记忆继续实验。

## 13. 已核对的参考依据

以下资料用于明确起点，不替代执行时的版本核验和实测。

- [LongMemEval-V2 官方仓库](https://github.com/xiaowu0162/LongMemEval-V2)：数据准备、基线与评测接口。
- [AgentRunbook-R 审查版本源码](https://github.com/xiaowu0162/LongMemEval-V2/blob/2cc8c540bdb87fe6761629b585e727e1c4704520/memory_modules/agentrunbook_r.py)：已有异步事件抽取；事件提示词读取完整 trace/outcome，提供分层改造入口。
- [公开数据 Schema](https://huggingface.co/datasets/xiaowu0162/longmemeval-v2/blob/main/SCHEMA.md)：state/action、截图、共享 haystack 的结构。
- [MemForest 在线实现说明](https://github.com/Concyclics/MemForest/blob/2b5af6d9f92618b30f3e8b7eb99412c1d5eddd6d/reproducibility/implementation/README.md)：区分异步并发实现和批量写路径计时。
- [MemForest 论文](https://arxiv.org/abs/2605.23986)：并行抽取与局部树维护相关工作。此处指 Concyclics/MemForest，不与其他同名项目混淆。
- [Codex Memories 官方说明](https://learn.chatgpt.com/docs/customization/memories)：后台生成和会话资格会影响端到端更新时间。
- [OpenAI 长任务实践](https://developers.openai.com/blog/run-long-horizon-tasks-with-codex)：采用可恢复的规格、里程碑、验证与状态记录组织执行；本文不依赖特定 Codex 自动持续运行功能。
