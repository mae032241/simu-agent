# P4c1 归档 I/O 原语抽取独审

结论：**静态 PASS，无剩余阻断。** 精确范围：新增 `src/scidiscovery/archive_io.py`、旧 `instance_archive_files.py` / `instance_archive_records.py` 重导出、`test_instance_archive.py` 一处实际 owner 拦截，以及作者证据 `P4C_ARCHIVE_IO_EXTRACTION_20261017.zh-CN.md`。对工作树相对 HEAD `3ac974d` 的本节点变化独审；并行 P2d/P3c 不在此结论内。

## 核对结果

- 新模块仅标准库，未带入旧 service/SQL/package 初始化依赖。八个定义：`ArchiveError`、`canonical`、`safe_id`、`check_path`、`hash_file`、`fsync_directory`、`durable_json`、`copy_verified`。
- 独立使用标准库 AST 比较八个定义与 Git 原件，全部等价；唯一排除的是 `durable_json` 已说明的旧 records `canonical` 局部导入，现直接调用同模块原实现。没有执行或导入项目代码。
- 旧 records/files 直接导入新 owner 的同一函数/异常类；不分别重定义异常。旧 records 后续局部调用 files.check_path 仍由原路径重导出满足。旧 `Files`、roots、清理、SQL 与归档/恢复 owner 不迁入新模块。
- `tests/operations/test_instance_archive.py:893` 的既有负控继续拦截旧入口，并新增实际 owner `archive_io.hash_file`。若 `copy_verified` 在全局 exclusive 内执行整份哈希，该负控仍可失败；避免函数搬迁后 globals 改变而漏查。旧 `files.os.link` 拦截仍指向共享标准库 os 对象。没有新增测试矩阵。

## 证据与限制

独立八定义 AST 等价检查、限定 `git diff --check` 均通过。未运行 pytest/collect、业务 import、CLI、HTTP、构建、安装或任何真实执行。AST 等价与静态消费者核对不证明实际文件系统竞争、掉电或运行时行为。

此提交只是 P4c1 前置复用：没有导出包/包 reader/restore 命令，没有可推进副本、归档恢复资格、权限或容量策略变更；不代表 P4c1 产品功能或 P4c2 可写恢复完成。
