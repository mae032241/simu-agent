#!/usr/bin/env bash
# Serial, isolated fixture A/B. No deployment or real TCAD solver.
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
evidence="$repo_dir/docs/plans/evidence/author-token-r4-20260920"
python_bin="${SCID_AB_PYTHON:-/home/da/miniconda3/bin/python}"
case "${1:-}" in
  '') check_only=false ;;
  --check) check_only=true ;;
  *) echo "用法：bash $0 [--check]" >&2; exit 2 ;;
esac

[[ -x "$python_bin" ]] || { echo "Python 不可执行：$python_bin" >&2; exit 2; }
command -v codex >/dev/null || { echo 'PATH 中找不到 codex' >&2; exit 2; }
for name in before.tar.gz final-candidate.tar.gz revision1-sources.tar.gz \
  before-release-supplement.json native_workflow.py native_transport.py \
  measurement_contract.json run_guarded.py; do
  [[ -r "$evidence/$name" ]] || { echo "缺少文件：$evidence/$name" >&2; exit 2; }
done
[[ -r "$repo_dir/docs/plans/evidence/mcp-response-levels/probe_handoff_usage.py" ]] || {
  echo '缺少 probe_handoff_usage.py' >&2; exit 2;
}
if "$check_only"; then
  echo '入口文件检查通过；未启动模型，未验证登录或运行时依赖。'
  exit 0
fi

cd "$repo_dir"
trial_dir="$(mktemp -d /tmp/scid-r4-ab-XXXXXXXX)"
trial_id="${trial_dir##*/}"
trap 'rc=$?; if (( rc != 0 )); then echo "已停止（退出码 $rc）；结果保留在 $trial_dir" >&2; fi' EXIT
echo "结果目录：$trial_dir"
echo '固定 sol/medium，串行运行；1536 MiB 采样守卫，超限或失败即停，不自动重试。'
mkdir -p "$trial_dir/A" "$trial_dir/B"
tar -xzf "$evidence/before.tar.gz" -C "$trial_dir/A"
tar -xzf "$evidence/final-candidate.tar.gz" -C "$trial_dir/B"
tar -xzf "$evidence/revision1-sources.tar.gz" -C "$trial_dir/B"

# Restore only baseline supplements whose original byte identities were recorded.
"$python_bin" - "$evidence" "$trial_dir" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

evidence, trial = map(Path, sys.argv[1:])
for item in json.loads((evidence / 'before-release-supplement.json').read_text()):
    relative = Path(item['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise SystemExit('Unsafe supplement path')
    raw = (trial / 'B' / relative).read_bytes()
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise SystemExit(f'Baseline supplement identity mismatch: {relative}')
    target = trial / 'A' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
PY

for group in root worker; do
  for item in A:1 B:1 B:2 A:2; do
    version="${item%:*}"
    pair="${item#*:}"
    label="$trial_id-$group-$version-$pair"
    echo "开始：$label"
    rc=0
    SCID_AB_MEMORY_LIMIT_MIB=1536 "$python_bin" "$evidence/run_guarded.py" "$label" \
      "$python_bin" "$evidence/native_workflow.py" \
      --source "$trial_dir/$version" \
      --group "$group" \
      --output "$trial_dir/$group-$version-$pair" \
      > "$trial_dir/$group-$version-$pair.log" 2>&1 || rc=$?
    if [[ -f "$evidence/$label.json" ]]; then
      cp "$evidence/$label.json" "$trial_dir/$group-$version-$pair.guard.json"
    fi
    if (( rc != 0 )); then
      echo "失败：$label；日志：$trial_dir/$group-$version-$pair.log" >&2
      tail -n 30 "$trial_dir/$group-$version-$pair.log" >&2
      exit "$rc"
    fi
    echo "完成：$label"
  done
done
echo "全部调用已结束：$trial_dir"
echo '仍须核验任务正确性和逐响应计量资格，才能认定 A/B 收益。'
