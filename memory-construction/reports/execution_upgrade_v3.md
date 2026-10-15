# 持续实验执行机制升级结果

2026-10-12。服务器：ly@zjuaces-gw。

研究代码根目录：`/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction`。

## 实际诊断

旧 workplan 给出了研究路线，但没有可核验的跨轮任务状态、运行所有权和失败后的下一项选择机制。状态文档曾将模型/数据描述为缺失；实际已经有本地 Qwen 的成功 pilot，包含 13 次真实构建调用。该 pilot 的配对方法是 replay、QA 行数为零，距离真实配对性能和官方质量实验仍有距离。另有两个遗留 running 记录需要确认归属和恢复边界。

核查时 `tune` 仍是空入口，日志集中在结束时写入，报告分类和重现验收也不完整。另一 Codex 正在修改研究代码，因此这些发现是时间快照；新队列要求先核对最新证据，不能回滚它已经完成的修复。

## 已部署内容

- `AGENTS.md`：错误进入诊断修复，阶段通过继续下一项，不以一次错误或 smoke 完成结束任务。
- `GOAL.md`：G1 开发闭环和 G2 论文实验验收，含可直接用于原生 Goal 的目标文本。
- `execution/queue.json`：11 项有依赖、有证据要求的任务；Judge 实评分单列，避免阻塞独立性能实验。
- `/home/ly/.codex/skills/memory-research-loop/`：项目专用技能；Windows 本地技能目录也已安装，项目内保留备份。
- `execution/research_loop.py`：观察现有证据；监督单次命令，保存独立日志、进程身份、心跳和终态，同类受管作业加锁。
- `EXECUTION_UPDATE.md`：供当前 VS Code Codex 读取的纠正说明与接收回执要求。
- START_HERE、WORKPLAN、STATUS 增加执行更新入口，原文件备份到父目录 `.execution-upgrade-v3-backup/`；未修改研究源码。

监督脚本不会自行修改研究代码或生成优化假设。真正的诊断、修改和实验决策由采用该技能的 Codex 执行。技能和 GOAL.md 文件也不会自动唤醒空闲会话；原生 Goal 需要在真正执行实验的会话中启用。[官方 Goals 说明](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)

## 已验证

服务器上 10 项监督机制测试全部通过：回放结果分级、遗留 running 不被改写、局部阻塞、冲突终态、PID 身份、失败后修复再运行、超时退出、重复启动拒绝、启动失败留档、接收回执不被推定等场景。

项目已有 4 项契约测试通过，实际由新监督脚本启动并记录：

`execution/attempts/20261012T153937Z-e72a08a1/`

技能格式校验通过。本次验证没有启动新的 GPU 实验，也没有将测试结果冒充研究提升。

## 当前交接状态

**已部署；另一个 VS Code Codex 尚未确认接收。** 用户表示稍后转发。该 VS Code 实例的通信通道没有连接到本桌面的会话消息工具，因此未尝试冒充消息送达，也未创建第二个执行器争抢原会话。

在其当前会话发送：

> 请立即读取 /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/EXECUTION_UPDATE.md，按其中要求读取新版规则、写入接收回执，然后从现有进度继续修复和优化实验，不要只汇报或重新从 P0 开始。

由执行 Codex 写入 `execution/ack-memory-loop-v3.json` 后，可以核验接收时间、下一任务及原生 Goal 状态。没有回执前，不声称已经及时纠正或已经启用跨轮自动续跑。

## 查看状态

在代码根目录运行：

```bash
python3 execution/research_loop.py --root . inspect --write
```

观察结果在 `execution/observed.json`，其中 `executor_update` 显示真实回执，`actionable_tasks` 显示依赖满足的任务。不要用监督心跳代替实际实验进度。
