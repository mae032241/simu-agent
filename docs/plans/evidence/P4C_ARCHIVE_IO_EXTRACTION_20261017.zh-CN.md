# P4c 归档文件原语前置迁移

状态：实现冻结，[独立静态审查通过](P4C_ARCHIVE_IO_EXTRACTION_REVIEW_20261017.zh-CN.md)。仅迁移既有公共原语，不代表新归档包或可写恢复完成。

## 精确范围

- 新 `scidiscovery/archive_io.py`：原 `ArchiveError`、`canonical` 及 `safe_id/check_path/hash_file/fsync_directory/durable_json/copy_verified`。只有标准库依赖，不导入旧服务/SQL。
- 旧 `instance_archive_records.py` 和 `instance_archive_files.py` 重导出同一实现对象；原旧入口继续调用，不复制状态或调整旧归档合同。
- `durable_json` 改为直接使用同模块的原 `canonical`，移除会带入旧 records 的局部导入。其余函数/类正文不变。
- 仅修正一处既有负控的拦截位置：`test_full_ownership_scans_and_payload_hashes_stay_outside_global_exclusive` 同时拦截新 owner 的 `archive_io.hash_file`，防止搬迁后漏查 `copy_verified` 内部哈希。不新增或运行旧套件。

## 检查及边界

八个搬迁定义与 Git 原件 AST 等价（仅排除已说明的 `canonical` 局部导入）；四个改动 Python 文件可 AST 解析。未导入执行模块，没有 pytest、安装、构建或业务子进程。

这是 P4c1 包内只读归档的前置复用；未接 export/view/restore CLI，未实施 P4c2 可写恢复，也未声称现有文件系统原语可以抵御任意同 uid 并发攻击或具有硬实时保证。
