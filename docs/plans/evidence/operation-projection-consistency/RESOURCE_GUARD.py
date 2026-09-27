import fcntl,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
root=Path('/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2')
records=root/'docs/plans/evidence/operation-projection-consistency'
label=sys.argv[1]; command=sys.argv[2:]
lock=open('/tmp/scid-contract-check.lock','w'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
env=dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',MALLOC_ARENA_MAX='2',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
env['PYTHONPATH']=os.pathsep.join(str(root/p) for p in ('src','.','plugins/curve_score','plugins/tcad_artifact','plugins/curve_figure_evidence','tests/fixtures/plugins/architecture_operation_plugin'))
limit=512*1024*1024; stop=448*1024*1024
start=time.monotonic(); peak=0; killed=False
with (records/(label+'.log')).open('w') as output:
 def limits(): resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
 proc=subprocess.Popen(command,cwd=root,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
 while proc.poll() is None:
  table={}
  for entry in Path('/proc').iterdir():
   if not entry.name.isdigit():continue
   try:
    stat=(entry/'stat').read_text().rsplit(')',1)[1].split()
    table[int(entry.name)]=(int(stat[1]),int(stat[2]),int(stat[21])*os.sysconf('SC_PAGE_SIZE'))
   except (OSError,ValueError,IndexError):continue
  ids={proc.pid,os.getpid()}
  while True:
   found=ids|{pid for pid,(ppid,pgid,rss) in table.items() if ppid in ids or pgid==proc.pid}
   if found==ids:break
   ids=found
  rss=sum(table[pid][2] for pid in ids if pid in table); peak=max(peak,rss)
  if rss>stop:
   killed=True
   os.killpg(proc.pid,signal.SIGKILL)
   break
  time.sleep(.025)
 code=proc.wait()
record={'command':command,'exit_code':code,'seconds':round(time.monotonic()-start,3),'peak_tree_rss_bytes':peak,'budget_bytes':limit,'early_stop_bytes':stop,'memory_terminated':killed}
(records/(label+'.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record)); print((records/(label+'.log')).read_text()[-14000:])
sys.exit(code if code>=0 else 128-code)
