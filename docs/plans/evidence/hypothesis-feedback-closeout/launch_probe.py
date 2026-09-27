"""Run one already queued compiled Worker serially; keep transport logs private."""
import json
import os
from pathlib import Path
import subprocess
import sys
base=Path('/tmp/scid-feedback-closeout')
case, stage=sys.argv[1:]
command=json.loads((base/f'{case}-{stage}-command.json').read_text())
env=dict(os.environ)
tmp=base/'cli-tmp';tmp.mkdir(exist_ok=True)
bin_dir=base/'bin';bin_dir.mkdir(exist_ok=True)
binary=Path('/home/da/.nvm/versions/node/v25.2.1/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex')
assert binary.is_file()
link=bin_dir/'codex'
if not link.exists(): link.symlink_to(binary)
env.update(TMPDIR=str(tmp), PATH=str(bin_dir)+os.pathsep+env['PATH'],MALLOC_ARENA_MAX='2',RAYON_NUM_THREADS='1',TOKIO_WORKER_THREADS='1')
# Live remote inference uses the declared Operation Run wall budget; local pytest
# remains separately capped at 180 seconds. The existing launcher guards 1 GiB.
attempt=command[command.index('--receipt-name')+1]
log=base/f'{attempt}-transport.log'
contract=json.loads((base/f'{case}-{stage}-contract.json').read_text())
# The catalog remains authoritative; use the exact declared timeout.
timeout=contract['operations'][0]['timeout_seconds']
with log.open('wb') as stream:
    done=subprocess.run(['timeout','--signal=TERM','--kill-after=5',str(timeout),*command],env=env,stdout=stream,stderr=subprocess.STDOUT)
print(json.dumps(dict(exit_code=done.returncode,log=str(log))))
sys.exit(done.returncode)
