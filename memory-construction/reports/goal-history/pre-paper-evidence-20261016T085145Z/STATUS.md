# 状态入口
当前执行修订：execution-recovery-20261016。

唯一任务状态：[execution/queue.json](execution/queue.json)。最新可用表与实际原始路径由队列证据和 execution/reuse_inventory.csv 指向。本文件不复制任务状态；原有完整历史已备份。

2026-10-16 核查发现正式评测请求/声明不符、开发库代替完整 Small、公开维护对照缺失、计量与检查口径问题；详见 [EXECUTION_RECOVERY](docs/EXECUTION_RECOVERY.md)。旧“全部完成”不是有效验收结论。
当前部署只完成局部入口修复、离线核验工具和任务纠正，未运行新的模型实验。实际接收回执、实时作业与原生 Goal 状态由服务器执行会话记录。
