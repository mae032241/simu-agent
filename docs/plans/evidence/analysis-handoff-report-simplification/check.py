"""Existing serial 512 MiB guard, reused for analysis reading and delivery checks."""
import json, os, resource, signal, subprocess, sys, time
from pathlib import Path
import psutil
base=Path(__file__).resolve().parent
start=time.monotonic(); peak=0; stopped=None
log=base/f'check-{time.time_ns()}.log'
env={**os.environ, 'OPENBLAS_NUM_THREADS':'1', 'OMP_NUM_THREADS':'1', 'MKL_NUM_THREADS':'1', 'PYTHONDONTWRITEBYTECODE':'1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}
def limits():
 resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
 resource.setrlimit(resource.RLIMIT_CPU,(120,120))
with log.open('wb') as stream:
 p=subprocess.Popen(sys.argv[1:],stdout=stream,stderr=subprocess.STDOUT,env=env,preexec_fn=limits,start_new_session=True)
 while p.poll() is None:
  try:
   family=[psutil.Process(p.pid)]+psutil.Process(p.pid).children(recursive=True)
   current=0
   for proc in family:
    try: current+=proc.memory_info().rss
    except psutil.Error: pass
   peak=max(peak,current)
   if current>512*1024**2:stopped='tree_memory_limit'
   if time.monotonic()-start>150:stopped='wall_timeout'
   if stopped:os.killpg(p.pid,signal.SIGKILL)
  except psutil.Error:pass
  time.sleep(.05)
 rc=p.wait()
record=dict(command=sys.argv[1:],exit_code=rc,duration_seconds=round(time.monotonic()-start,2),peak_tree_rss_bytes=peak,stopped=stopped,log=log.name)
with (base/'checks.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
print(log.read_text(errors='replace')[-14000:]);print(json.dumps(record))
sys.exit(rc if rc>=0 else 128-rc)
