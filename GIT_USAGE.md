# 在服务器原项目目录直接提交

仓库：git@github.com:ysyjsk/agent_mem_26.git
Git 根目录：/data/predator/ly/agent-memory-construction-2026-10-12
默认分支：main

日常修改继续在原有 memory-construction/ 下完成，不需要复制到其他文件夹。

```bash
cd /data/predator/ly/agent-memory-construction-2026-10-12
git status
git add -A
git diff --cached --stat
git commit -m "更新方法和实验结果"
git push origin main
```

也可以在 memory-construction/ 子目录运行 Git；它属于同一仓库。需要提交整个项目时，回到上面的 Git 根目录。

若其他设备也有提交，在开始修改前执行 git pull --ff-only。发生分歧时保留本地提交并处理冲突，不使用强制推送。

数据、截图、模型、数据库/向量/请求缓存、备份和日志不加入仓库。代码、配置、报告、汇总表、逐题答案及所选性能记录会被跟踪。结果文件提交时由 Git clean filter 去掉长提示词与源上下文并脱敏凭据，原始磁盘文件保持完整；git show HEAD:文件路径 可以查看实际提交版本。

已经跟踪的第三方源码保持跟踪。第三方仓库内的新文件默认忽略，确有必要时只显式添加指定源码文件，不要强制添加整个第三方目录。

在新机器克隆后，先运行 python3 repository-tools/configure_repository_git.py，再提交原始结果文件。原发布目录 github-exports/agent_mem_26-20261015-0055 仅保留为历史副本，不再作为日常提交位置。
