# 接续：完成现有矩阵，再补一次独立证据
update_id: focused-maintenance-v4-20261015
update_revision: execution-recovery-20261016
guidance_revision: paper-evidence-20261016

先读本文件、execution/queue.json、GOAL.md 和 docs/PAPER_EVIDENCE_PLAN.md，再按 execution/prompts/CONTINUE_RESEARCH.md 接续。
这次只整理收尾顺序；运行修订、v13方法、baseline和活动冻结配置不变。

旧入口中“尚未做修复验证、先产生8个回答”等指令是恢复阶段历史，不能据此重做已完成实验。已有开发修复与公开维护结果按 queue 和原始证据复用；当前实际作业与进度由执行会话核实，不照抄文档时间点。

当前顺序：
A. 完成已登记 full-small-recovery-v1，保留健康作业与成功单元。
B. 复用完整初始快照，补一批未用于调参的新修订及正常 QA；单独预冻结清单，不修改 A。等待时先离线准备，GPU任务顺序接续。
C. 分开组织维护主表、合并机制、质量与独立确认，完成论文。

由实际执行会话把 B 接到现有 CONFIRM/WRITE/PACKAGE 任务；不要另建状态体系。queue中的旧 goal说明若仍不含本补充，由该会话同步，保留真实状态和活动作业。队列接续依赖调整为 SELECT → SMALL_MAIN → CONFIRM → PACKAGE，WRITE 并行且 PACKAGE 等待 WRITE；去掉 SMALL_MAIN 对本次新增确认的反向依赖，旧确认结果作为历史保留。这仅由执行会话更新任务依赖，不改活动登记计划。
原生 Goal 继续，不为换文案伪标完成。

首次读到本指导时，由执行会话写 execution/ack-paper-evidence-20261016.json，记录实际收到时间、当前作业、保留阶段、下一任务与真实查询的 Goal 状态。本次文档部署不代写接收、不激活会话、不启动实验。
