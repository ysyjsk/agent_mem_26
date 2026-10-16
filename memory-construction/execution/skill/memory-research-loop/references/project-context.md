# 当前入口与容易漏掉的事实
当前执行修订 execution-recovery-20261016，任务和状态只从项目 EXECUTION_UPDATE.md / execution/queue.json 读取。

- SSH ly@zjuaces-gw；项目 /data/predator/ly/agent-memory-construction-2026-10-12/memory-construction；已用解释器 /data/predator/ly/Mem/.venv/bin/python。
- tools/run_agentrunbook_updates.py 是当前维护入口；tests/test_agentrunbook_update_dependencies.py 是现有维护测试。Source-only 已有实现和开发序列，不从头重写。
- tools/run_focused_formal_reader.py 已接 tools/focused_runtime.py；配置来自 execution/experiment_contract.json，必须在 harness 导入前生效。修复后真实请求仍待执行会话验证。
- 原 adapter 在 runs/agentrunbook-r-native-small-20261014/local-text-only/run_eval_local_text.py；目录含实际代码，保留。后续共享代码放 tools/，不再放 runs。
- 实际发送内容查看 prompt_rows.jsonl 的 messages；prompt_messages 可能已转为 image_path。run_args 不是全部环境 flags；新 run 的 effective_runtime.json 记录已解析环境，仍需查实际 messages。
- execution/verify_evidence.py --current 查登记产物；--reader-dir、--manifest、--main-table 可指向纠正后的新产物。只做结构检查，不认证语义或论文完成。
- 官方历史映射 third_party/LongMemEval-V2/data/longmemeval-v2/haystacks/lme_v2_small.json；域通过 questions.jsonl 关联。开发 data-expanded20 每域 10 条，不是完整 Small。
- 已有开发连续序列 runs/focused-maintenance-v4/dev/sequence-final；旧 v13 在 runs/method-first-20261015/v13-sequential。历史序列脚本写死旧输出，新实验不得覆盖。
- 旧 formal 和 repeat-20261016 查询不符 text-only；更新快照与有效成本分阶段保留。正式 Raw RAG/Notes 维护仍缺，冷构建参考不能替代。
- 长实验沿用 execution/launch_detached.sh / background_status.sh；不要另建执行器。execution/research_loop.py 的历史实现检查不决定研究范围。
- 常规修复路径、首次 8 回答和完成验收见 docs/EXECUTION_RECOVERY.md；不把此参考文件复制为另一份进度。
