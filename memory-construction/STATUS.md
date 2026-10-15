# 当前执行状态：R5 adapted-matched web 部分失败；local text-only 诊断 smoke 已通过；native GPT/Judge pending

下方旧实验接续条目保留作历史日志；当前恢复点与活动运行状态以文末“2026-10-14 适配 Small 活动运行”条目为准。

- 用户已将主线切换为冻结 LongMemEval-V2 官方 AgentRunbook-R 完整 Small（web + enterprise）；H4/H5/H6 与 18 道题只保留为开发/机制/回归证据。
- 已核对官方仓库源码、Small haystack（451 题）、questions.jsonl（451 题）、trajectories.jsonl（约1.2GB）和官方评测入口；旧 `runs/lme-v2-agentrunbook-r-one-prefix6-20261013` 因 `127.0.0.1:18023` 无服务而只有空 prompt/pool，已标记失败诊断。
- 官方截图恢复正在进行：PID 2568699/2568703 的 Hugging Face `snapshot_download` 正在恢复 `web_screenshots.tar.gz` 与 `enterprise_screenshots_base.tar.gz`，不占 GPU；现有本地 web 包已证实截断（官方 2,562,302,847 bytes，本地 135,338,642 bytes），enterprise 包缺失。
- 截图下载完成后唯一下一条命令：
  `PYTHONNOUSERSITE=1 /data/predator/ly/Mem/.venv/bin/python third_party/LongMemEval-V2/data/prepare_data.py --data-root third_party/LongMemEval-V2/data/longmemeval-v2 --mode symlink`
  随后运行 `validate_data.py --tier small --check-screenshots`，校验通过才启动 native Small。

- 已验收首表：`results/tables/first_compare.csv` / `reports/first_compare.md`。
- 原始 run：`runs/fast-compare-v4-corrected-20261013`，24/24 checkpoints，0 失败。
- B0 386.814 s / 93 real calls / 183591 input / 7943 output tokens；
  Ours-dev 193.689 s / 45 calls / 90640 input / 3842 output。
- 12/12 配对结构相同；源事件 evidence 覆盖每 checkpoint 100%。
  范围仅 construction_kernel/text-only dev；QA not_evaluated，不是正式论文结论。
- 已完成同窗口 construction_e2e：`runs/fast-compare-v4-e2e-c1-20261013`；
  B0 286.444 s，Ours-dev 139.112 s，B3-c1 138.512 s；各12/12成功。
  Ours 对 B3-c1 为 -0.43%（轻微回退/近似持平），不宣称强对照收益。
- H2 batch2完成：Ours 100.288 s，B3-c2 100.270 s，各12/12成功、45真实调用，
  实际批宽2。两者较各自c1均约快28%；强对照仍平局（Ours -0.01784%）。
  同一run语义12/12相同；跨c1→c2仅2/12精确相同，需要Reader质量检查。
- H3完成：Ours89.008 s/B3-c2 88.650 s，各12/12成功；输入tokens64335。
  相对H2再降11.25%/11.59%；跨配置0/12语义精确相同，质量未评，尚不选正式配置。
- 12窗口扩量完成：132事件/36checkpoint每方法；Ours293.224 s/B3-c2 292.722 s，
  各132真实调用、267781输入/10913输出，0失败，独立audit中，强对照仍近似平局。
- 24窗口三方法已完成：`runs/fast-compare-v4-dev24-batch2-20261013`，180/180 checkpoint、0失败；
  B0 1268.666 s/413 calls，Ours-dev 476.220 s/205 calls，B3-c2 473.990 s/205 calls；
  Ours 对 B3 约慢0.47%，仍不宣称强对照优势。`results/tables/dev_scale24.csv` 保留真实汇总。
- 首轮 Reader：`runs/dev-reader-v4-first-20261013`，固定12题×7组=84次真实调用，
  全部运行完成但精确率很低，失败/unknown/低分保留；official_qa_status=not_evaluated。
- QA2：`runs/dev-reader-v4-quality-v3-qa2-20261013` 完成18题×5组=90次真实 Reader 调用；`runs/dev-reader-v4-quality-v3-qa2-rescored-20261013` 为 evaluator-only，90/90 行逐题对齐、仅5个 `shipping_checkbox_state` 评分修正，0 新模型/Embedding 调用。聚合表现已扩展为23行（13个 live rows + 10个不重叠 exact_field/semantic 分区行），H4b B0/Ours/B3 均14/14 exact-field、4/4 semantic，仍是 auto-source development proxy，非官方 QA。
- QA2 provenance 已记录：question manifest `05c50115f55605236da34873c035045e4729a4fef43510d1e8139407b73a6a5b`，source/output QA SHA 与 scorer SHA 见 `reports/dev_quality.md` / `reports/quality_repair_log.md`；累计 source Reader calls 246/246，rescore 行不重复计数。
- 当前没有活动 GPU 作业（2026-10-13T09:41:59Z 检查）；不重跑 P0 或已完成构建。
- 下一确切动作：先验收 temporal Reader/CPU 聚合和相关测试，再在既有快照上真实复测公开步骤检索；随后实施带版本哈希的输入保真候选并配对重跑。

```bash
PYTHONPATH=src /data/predator/ly/Mem/.venv/bin/python -m pytest -q tests/test_dev_reader.py tests/test_temporal_retrieval.py
```

- 旧失败/负结果全部保留；未覆盖活动 runtime、未杀不明进程。
- MemForest/长链路原生适配/全量截图/通用框架保持 deferred。
- 原生旧 Goal 当前 reports blocked/unfinished；工具拒绝启动重复 Goal。
  当前用户 `continue` 已在执行，文件更新不冒充 Goal 已激活。

## 2026-10-13 23:30 native matched runtime 接续

- 保留既有 HF-Xet 进程 PID 2568699/2568703；enterprise screenshot archive 从 402 MB
  增长到约 671 MB，I/O 与 socket 均持续变化，web 文件仍等待同一 snapshot 顺序，未
  重复下载、未中断进程。
- 本地 matched runtime 已启动并完成真实服务加载诊断：chat PID 2739955 在物理 GPU0
  使用 Qwen3.5-9B，embedding PID 2739956 在物理 GPU1 使用 Qwen3-Embedding-8B；
  `/health`、`/v1/models`、一次 chat（top_p=.95/top_k=20/thinking=true）和一次
  embedding 均返回成功。GPU 显存约 18.4/14.8 GiB；服务日志保留在
  `runs/agentrunbook-r-native-small-20261013/matched-runtime/`。
- 修复仅限本地适配层：显式 `PYTHONPATH`、物理 GPU1 的逻辑 `cuda:0`、按请求转发
  `top_p/top_k/chat_template_kwargs.enable_thinking`；官方 LongMemEval-V2 源码和
  AgentRunbook-R 算法未改。详情见同目录 `config.json`，结果须标为
  `native-code/matched-runtime`，不能称 hosted native。
- LabForge `/v1/models` 当前没有官方默认 `gpt-5.2`，因此官方 evaluator-only 的 LLM
  评分若执行将显式使用可用的 `gpt-5.6-terra`（medium reasoning），并在结果中单列
  配置适配；Reader/controller/embedding 仍使用本地 Qwen，Judge 不可用时保留
  `pending_judge`，不以该适配分数替代 hosted-native 质量。
- 服务诊断中的一次短回答不计 Small；官方完整运行仍等待截图校验。截图完成后立即执行
  `prepare_data.py --mode symlink`、`validate_data.py --tier small --check-screenshots`，
  再按 web→enterprise 启动完整 `run_eval.py`，输出目录不覆盖旧失败尝试。
- 已启动单用途续接 PID 2786190，日志为同目录 `continuation.log`；它只等待既有下载
  PID 2568699/2568703，并在精确尺寸/SHA256 校验、Small 5095-state 覆盖校验通过后
  自动运行两域官方入口。当前尚未产生 Small 评分，不能把该后台续接视为完成。

## 2026-10-14 01:32 adapted-matched Small 接续

- 两份官方归档已完成独立校验：web 2,562,302,847 bytes、SHA256
  `68699c6842412e09a6f89d3c05c5ae8813275918002b52d82dec43ab24dd01fb`；enterprise
  3,354,163,660 bytes、SHA256 `5c4a67ae0856aa1ede9b040e7da7c7a2d0b76fdd6344ef87380bcdf9f4b6d7a3`；
  两者 `gzip -t` 均通过。
- `prepare_data.py --mode symlink` 与 `validate_data.py --tier small --check-screenshots`
  已通过：451 questions、1870 trajectories、Small 451 haystack questions、
  web 240 / enterprise 211、Small 200 unique trajectories / 5095 states。
- 既有 `/web`、`/enterprise` 和 `matched-qwenplus-v2` 目录均为失败或诊断，不计正式结果，
  不覆盖。新的运行必须写入 `runs/agentrunbook-r-native-small-20261014/`；采用
  `adapted-matched`：Reader/Controller=`qwen3-vl-plus`（DashScope compatible），
  Embedding=本地 Qwen3-Embedding-8B，Evaluator=`qwen-plus` 仅 evaluator-only。
- `harness.py`/`agentrunbook_r.py` 已通过 `py_compile`；Reader 请求构造检查确认
  `max_completion_tokens`、`extra_body.enable_thinking`、`top_k` 字段正确。
- 下一实际动作：先启动新目录 web Small；运行时 API key 只通过 `ALIYUN_API_KEY` 环境变量
  注入，不写入配置、日志或报告。

## 2026-10-14 适配 Small 活动运行

- web 已在 `runs/agentrunbook-r-native-small-20261014/adapted-aliyun-vl/web/` 以完整 Small
  启动，当前仍在构建 100 条 Small 轨迹；不得重启或覆盖。
- 配置标记为 `adapted-matched`：Reader/Controller=`qwen3-vl-plus`（DashScope 兼容端点），
  本地 Embedding=`Qwen3-Embedding-8B`，`qwen-plus` 仅 `evaluator-only`；native GPT 与官方
  Judge 仍为 `pending_judge`。
- 活动记录包含 `memory_build_metrics.jsonl` 与
  `memory_workspace/shared/model_calls.jsonl`；当前已保留成功调用及少量极快的
  `async_text` RuntimeError，不隐藏失败。初步高概率原因是跨 `asyncio.run()` 复用异步客户端，
  但异常消息尚未落盘，故在本轮完成前不把推断写成定论。
- web 完成后下一项是修复/验证该生命周期问题（独立目录、不覆盖本轮）并运行同配置 enterprise，
  然后生成 adapted 与 native pending 分列的 R5 表。
- 来源检查确认冻结上游 HEAD 2cc8c54 在逐轨迹 asyncio.run() 循环之间复用实例级 AsyncOpenAI，且未 close/aclose；这是确定的客户端生命周期缺陷，但不能仅凭记录的 RuntimeError 类型认定每个请求都由它直接导致。最新 26/100 构建点仍未生成逐题 Reader/评分文件；本次观察错误要分别统计 RuntimeError 和 RateLimitError。

## 2026-10-14 03:35 运行中接续

- 汇总器已修复官方 `questions.json` 使用 `id`、逐题输出使用 `question_id` 的字段差异，并加强 question/trajectory ID 覆盖、重复行、坏行和 prompt-row 完整性门槛；只读快照不会把部分运行标为 complete。`PYTHONPATH=src ... pytest -q tests/test_dev_reader.py tests/test_temporal_retrieval.py` 通过（15 passed）。
- 已完成隔离 AsyncOpenAI 生命周期修复副本 `runs/agentrunbook-r-native-small-20261014/async-fix-runtime/`；修复回归测试 2 passed，未改活动 web 或冻结上游源码。
- 一次性后续 supervisor 已捕获当前运行时环境但不落盘密钥，等待 web 完整产物后在独立 `adapted-aliyun-vl-asyncfix/enterprise/` 运行修复版 enterprise；若 web 不完整则停止，不自动扩展实验。

## 2026-10-14 04:52 当前恢复点

- 阿里云 adapted web Small 已真实结束但失败：5322.23s，67/100 trajectory success，1 failed；
  `memory_workspace/shared/model_calls.jsonl` 1490 行（1398 success、67 RuntimeError、15×429、
  10×400），终止错误为 HTTP 400 `Arrearage`。`failure_summary.json` 已写入，未生成
  per-question/aggregate 完整 gate 文件，不计 R5 完成，不启动 enterprise 复用该配置。
- 隔离副本 `runs/agentrunbook-r-native-small-20261014/local-text-only/` 已加入显式
  `--text-only`、本地导入优先、AsyncOpenAI 生命周期修复和本地 Embedding tokenizer 默认；
  `smoke-run-enterprise-v3` 以官方 schema 的 4-state prefix 完成 1 trajectory/1 question，
  本地 Qwen3.5-9B + Qwen3-Embedding-8B 真实调用，prompt `image_url=0`，评分 0/1。
  这是 `diagnostic-text-only`/micro 负结果，不能替代视觉 Small 或官方 QA。
- 下一实际动作：保留所有失败与 smoke 记录，继续不依赖外部视觉服务的窄 RAG+Notes/内部机制
  验证；若得到可用视觉端点，只在全新目录重跑完整 web→enterprise，否则保持 R5 pending/blocker，
  不编造质量分数。
- 已完成同一 fixture 的窄 RAG 消融：`results/tables/local_text_smoke_compare.csv` /
  `reports/local_text_smoke_compare.md`。RAG-without-Notes 为 3.630s build、0.046s query、
  2 calls；RAG+Notes 为 17.683s build、0.132s query、7 calls；两者 Reader proxy 均 0/1。
  这是 text-only/micro 成本—质量负结果，不是 R6 官方结果。
