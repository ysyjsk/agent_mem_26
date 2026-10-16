# Agent Memory Maintenance

当前工作：基于源证据的局部记忆维护。执行版本 focused-maintenance-v4-20261015，修订 execution-ready-r2-freeze。

从 [START_HERE](START_HERE.md) 开始。研究目标是尽快取得可信的成本—质量结果并交付论文稿件；以既有 AgentRunbook-R/text-only 链路为起点。

## 项目入口
| 路径 | 用途 |
|---|---|
| GOAL.md | 总目标和完成条件 |
| WORKPLAN.md、execution/queue.json | 阶段顺序与实际状态 |
| EXECUTION_UPDATE.md | 给当前执行会话的最新纠正与接收要求 |
| docs/EXPERIMENT_PROTOCOL.md | 公开 baseline、Source-only、指标和公平比较 |
| execution/prompts/CONTINUE_RESEARCH.md | 可复制的完整执行提示 |
| paper/README.md | 论文交付清单、现有证据和写作入口 |
| tools/ | 已工作的更新、查询和汇总脚本；沿用现有入口 |
| runs/、results/、reports/ | 原始记录、派生表图、分析；部分 runs 内含正在导入的 adapter，原路径保留 |
| third_party/ | 已有公开实现；不重新适配新框架 |
| src/、tests/ | 原 workflow-memory 实现与测试，保留作历史/必要复用 |

公开比较：Raw RAG、RAG+Notes、AgentRunbook-R（合法缓存维护适配）、Ours。
机制比较：B3、Source-only、Ours；已有 overlay/coalesced 解释合并作用。
Codex、AgentRunbook-C、MemForest、LightMem 暂停。旧 README 和计划已备份，旧报告不控制当前排序。

## 新产物组织
沿用现有 tools 和数据，不搬迁正在被脚本引用的目录。后续新增实验使用 runs/focused-maintenance-v4/，开发首表使用 results/tables/focused-maintenance-v4/dev/，正式表图使用 results/tables/focused-maintenance-v4/ 和 results/figures/focused-maintenance-v4/，论文正文放 paper/。
本次结构调整只整理文档入口；未声称已运行新的 Source-only 或 baseline 实验。

首轮必要一致性/公平性和冻结检查通过后，无论初步胜负都进入完整 Small 历史库＋固定修订/问题主实验；不是首轮前置，也不冒充官方全部多模态 QA。Manifest 两阶段冻结，详细条件以实验协议为准。

执行去重与自主优化集中在 [REUSE_AND_OPTIMIZATION](docs/REUSE_AND_OPTIMIZATION.md)。先按阶段复用初始构建/正常 QA/更新/确认/重复，只补缺失维护；Codex 可依据瓶颈自主读原始资料、改进现有 Ours。不是重跑整个矩阵。

## 长实验后台运行

需要跨越 Codex 会话的构建、维护或重复实验时，统一使用 detached launcher，不直接在前台执行：

```bash
cd /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction
./execution/launch_detached.sh JOB_NAME -- python tools/your_experiment.py ...
./execution/background_status.sh
```

每个任务的 PID、命令、状态、退出码、stdout 和 stderr 保存在 `execution/background/JOB_NAME/`。launcher 使用 `nohup + setsid`，运行进程脱离当前终端并由 PID 1 接管；不要删除该目录，直到结果已汇总。
