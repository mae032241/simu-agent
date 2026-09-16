"""Serial task verification, with bounded process-tree memory and durable logs."""
import json, os, signal, subprocess, sys, time
from pathlib import Path
import psutil
base=Path(__file__).resolve().parent
budget=min(2*1024**3, psutil.virtual_memory().available//4)
log=base/('check-'+str(time.time_ns())+'.log')
start=time.monotonic();peak=0;terminated=None
with log.open('wb',buffering=0) as output:
 p=subprocess.Popen(sys.argv[1:],start_new_session=True,stdout=output,stderr=subprocess.STDOUT)
 while p.poll() is None:
  try:
   processes=[psutil.Process(p.pid)]+psutil.Process(p.pid).children(recursive=True)
   total=0
   for process in processes:
    try: total+=process.memory_info().rss
    except psutil.Error: pass
   peak=max(peak,total)
   if time.monotonic()-start > 180:
    terminated='time_limit';os.killpg(p.pid,signal.SIGKILL);break
   if total>budget or psutil.virtual_memory().available<512*1024**2:
    terminated='memory_limit';os.killpg(p.pid,signal.SIGKILL);break
  except psutil.Error: pass
  time.sleep(.05)
 rc=p.wait();os.fsync(output.fileno())
summary=dict(command=sys.argv[1:],memory_budget_bytes=budget,peak_tree_rss_bytes=peak,exit_code=rc,
 duration_seconds=round(time.monotonic()-start,2),terminated=terminated,log=log.name)
with (base/'checks.jsonl').open('a') as f:
 f.write(json.dumps(summary)+'\n');f.flush();os.fsync(f.fileno())
print(log.read_text(errors='replace')[-12000:]);print(json.dumps(summary),flush=True)
sys.exit(rc if rc>=0 else 128-rc)
