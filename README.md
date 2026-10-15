# Agent Memory Construction

This Git repository is the live server project at /data/predator/ly/agent-memory-construction-2026-10-12, connected to git@github.com:ysyjsk/agent_mem_26.git.
Code, plans and analysis results are committed directly from this directory. Experiments run under memory-construction/.

- Current research objective: [memory-construction/GOAL.md](memory-construction/GOAL.md)
- Architecture and evidence: [ANALYSIS_GUIDE.md](ANALYSIS_GUIDE.md)
- Server commit instructions: [GIT_USAGE.md](GIT_USAGE.md)
- Result tables: [memory-construction/results/tables](memory-construction/results/tables)

Dataset/model/cache/backup files are ignored. The configured Git clean filter omits bulky prompt payloads and credentials from staged JSON result files, preserving final answers, scores, timing and token/call counts. Original experiment files are preserved on disk.
After cloning on a different machine, configure the filter once with python3 repository-tools/configure_repository_git.py before staging server-style raw result files.
EXPORT_MANIFEST.json describes the initial export preserved in repository history; current contents are versioned directly by Git.

## Historical initial package instructions

The original package notes below describe the initial handoff. Current implementation and results are in memory-construction/; follow its current GOAL.md and AGENTS.md.

# Agent Memory Construction — Codex 执行包 v2.0

日期：2026-10-12。目标：实现工作流感知的并发、增量记忆构建，获得可复现的真实实验结果，形成 WWW 投稿所需的方法和证据。

## 如何交给 Codex

1. 把整个文件夹放进你准备运行实验的项目目录；也可以直接让 Codex 打开这个文件夹。
2. 将 `START_HERE.md` 全文作为第一条任务消息发送给 Codex。
3. Codex 应读取 `WORKPLAN.md`、`configs/experiment-plan.json`、`STATUS.md`，执行环境发现，开始实现并持续运行实验。
4. 如果在另一台服务器执行，请把整个文件夹一起传过去；文件内部使用相对路径，不依赖当前电脑路径。

不需要另开多个聊天，也不要求多代理。执行者应优先使用所在项目和已有计算资源。

## 文件说明

| 文件 | 用途 |
|---|---|
| `START_HERE.md` | 可直接粘贴给 Codex 的完整启动指令 |
| `WORKPLAN.md` | 方法定义、代码接口、阶段任务、实验协议、优化路线和完成标准 |
| `configs/experiment-plan.json` | 结构化实验规格；执行者据此生成本机运行配置 |
| `STATUS.md` | 初始状态、断点恢复和每阶段更新模板 |
| `REFERENCE_V1.txt` | 用户原始 v1.0 方案，保留供追溯 |

## 当前状态

这个执行包已经写好，尚未实现研究系统、启动模型服务或运行数据集实验。文中 `python -m workflow_memory ...` 是要求执行者实现的命令接口，不是本文件夹已经提供的软件。所有性能数字均为研发目标或协议参数，不是实验结果。

执行者必须把命令、代码、数据、模型、运行日志和最终报告连起来，不能把“计划写好”“单元测试通过”或“模拟加速”当成研究完成。
