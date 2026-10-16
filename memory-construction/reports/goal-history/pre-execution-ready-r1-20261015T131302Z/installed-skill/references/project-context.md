# 当前优先级已更新为 v4

先读项目 WORKPLAN.md v4。当前先做现有小数据上的 B0/Ours-dev 真实 first_compare.csv，随后补强 B3 并迭代。MemForest、完整 tune、通用恢复与全量截图都不再是首表前置条件。下面保留的 v3 快照只用于查路径，不决定任务次序。

# 项目快照和恢复入口

核对时间：2026-10-12 15:25 UTC。此文件是已观察事实，不替代重新探测。

- SSH：`ly@zjuaces-gw`；执行包 `/data/predator/ly/agent-memory-construction-2026-10-12`，代码在其 `memory-construction/`。
- Python：`/data/predator/ly/Mem/.venv/bin/python`。旧 environment.md 用系统 Python，不能据此认定该虚拟环境缺依赖。
- 两张 RTX 3090 Ti，各约 24 GiB。构建/Reader 在 cuda:0，Embedding 在 cuda:1。不要任意混用其他研究项目的显存。
- 本地模型目录：`/data/predator/ly/Mem/models/Qwen3.5-9B` 和 `/data/predator/ly/Mem/models/Qwen3-Embedding-8B`。
- `configs/runtime.local.json` 是包装对象：模型设置在 `plan.models`，路径在 `paths`。嵌入 plan 来自 `configs/local-experiment-plan.json`；修改配置时保持其加载和哈希合同。
- 派生数据 `data/longmemeval_dev.jsonl`、`data/longmemeval_smoke.jsonl` 已存在。核对 manifest、划分与解析完整性后使用，不能再次认定“没有任何数据”。

## 已有证据

- `runs/20261012T143904Z-pilot-db6b8886f4-0d099bd4/metrics.json`：真实 transformers_local 构建，13 次模型调用，43 段 Embedding；paired methods 使用 replay，qa_rows=0。只说明真实构建 smoke 已通。
- `runs/20261012T143545Z-pilot-db6b8886f4-51632bdd/`：CUDA OOM 后已有成功 pilot，因此“从不恢复”不准确。
- `runs/20261012T144342Z-dev-db6b8886f4-d7ffd42d/`：KeyboardInterrupt 失败。
- `runs/20261012T145028Z-dev-db6b8886f4-525fda9f/`、`runs/20261012T150134Z-dev-db6b8886f4-4a2b8ecf/` 仍标 running。后者 progress 为 22/24 trajectories、284 live calls，更新时间 15:12:07 UTC；15:25 的项目 cwd 进程检查没有发现对应实验进程。这是需核对的中断候选，不是完整实验结果或确证进程死亡。
- judge_probe 为 not_configured；仅证明该次 Judge 探测不可用。

## 实际代码缺口

1. `cli.py` 的 `tune` 分支直接返回 not_implemented；这是研发任务。
2. `live_pipeline.py` 真实调用集中在 Fresh，增量经 Recording/Replay 验证；尚不能给出真实 B3/Ours 加速结论。
3. 多个 suite 共用同一路径，不能用 suite 名称证明 Small/Medium/消融已经实现。
4. 大部分 JSONL 在结尾集中写入；进程中断时证据易丢失。progress 心跳不等于可恢复 checkpoint；逐轨迹持久化与幂等恢复需要实现并做故障验证。
5. `report` 把同样 rows 写到六张不同用途表，`reproduce` 主要检查文件存在。两者还需真正分类聚合与数值核验。
6. STATUS 和环境报告落后于实际资源、模型运行和数据。

## 启动参考

在代码根目录使用已验证环境，并先读当前 CLI help 获取真实参数。`PYTHONPATH=src /data/predator/ly/Mem/.venv/bin/python -m unittest discover -s tests -v` 可验证现有离线契约。不要把离线测试循环当成实验优化。

监督脚本：`python3 execution/research_loop.py --root . inspect --write`。
运行示例：`python3 execution/research_loop.py --root . run --task S01 --hypothesis '验证状态修复后的离线契约' --timeout 180 --resource cpu -- /data/predator/ly/Mem/.venv/bin/python -m unittest discover -s tests -v`。若项目未安装，调用者设置 `PYTHONPATH=src`。

重点在队列中的恢复、真实配对与开发优化；不需要重新从空仓库开始。
