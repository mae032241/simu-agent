# P4c2 冷 checkpoint：独立静态实现复审

结论：当前冻结生产与五个定向用例静态 PASS；未执行测试、HTTP、浏览器、项目导入、
安装、模型、solver 或远端操作。不能将此结论等同动态恢复验收。

## 实际链与边界

追读 CLI enroll/export/restore → archive 原 owner 锁/quiescent → 外 anchor 独占 →
原 generation 冻结 → 精确 payload 发布 → 原绝对 root 分阶段恢复 → 预算 owner 核验 →
paused 激活，以及 controller/contracts/runtime/delivery/authority/budget/experiments 写入 hooks。

外部 anchor 绑定同宿主、exact root/inode、instance/settings 和唯一 generation；完整
effect 持共享 lease，转移独占。settings-identity 中 cold_owner marker 先落、再落 binding，
中断或 binding 丢失不会误当普通未 enrolled。显式 enrollment repair 只认原 marker/
原 anchor/同 root inode/current active 代次，不新建或替代 anchor。

包不复制 native homes/凭据或延续执行批准；旧普通只读包无转移权。原 root 必须由操作者
移出，restore 不删除/覆盖现存根，不自动 continue、重放 unknown 或退款。scope 仅同宿主
原路径冷交接，不能据同路径/goal_id/hash/flock 推断跨宿主 owner 唯一，也不抗任意同 UID 篡改。

## 本次发现并关闭

1. checkpoint/metadata 读取与另次 pathname hash 分离：改同 fd stable decode+proof；
   inspect 前后核 metadata，实际 checkpoint digest 与被解码内容同源。
2. pending root 重入可能跳过普通 jobs/materials 核对：activation 前按 manifest 核全部
   原成员 hash/size/mode，仅容许本事务 owner/receipt/paused/reanchor 变化，不从包修覆盖。
3. inspect 后 actual manifest 重开：copy 与 activation 两次实际消费均同 fd 逐行 hash/
   size/fstat，与已验 metadata 绑定；尾部核完前不发布或激活。

完成后重复 restore 仅 acknowledge，不覆盖现 pause、ledger 或 clock。两次合法冷交接的
历史 transfer 原件仍沿 immutable 关系可验证；不依最新代次反授旧写权限。

## 负控证明范围

四个 source 用例覆盖双次交接、marker-before-binding 中断重试、缺依赖 inactive 重入/
实际 job 篡改、错宿主/缺锚/坏包；一个独立 Python 子进程实际持外部共享 lease，checkpoint
须拒绝，释放后才可导出。source fixture 的原科学节点与模型身份为合成输入，不证明真实
Codex session、许可证、solver 或整个部署可迁移。

另按 root 要求只读审 `test_instance_browser.py`：只用已有 Chrome/Chromium 与 CDP pipe，
缺失则 skip；核真实 read/manage cookie、read 无 controls/manage 有 controls、点击 pause
写原标记且无 accepted。有限等待、进程组终止/等待、server shutdown/close/join 均有 finally
清理；没有安装、真实科学推进或新执行权限。其动态资源峰值/清理结果须由 root 串行测试记录。
