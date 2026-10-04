"""Synthetic command canary; no model, benchmark, pickle, or real credentials."""
from pathlib import Path
import errno,json,socket,subprocess,sys

def denied(path):
    try:
        path.read_bytes()
    except OSError as exc:
        return exc.errno in (errno.EPERM,errno.EACCES,errno.ENOENT),exc.errno
    return False,None

def blocked_port(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1):
            return False,None
    except OSError as exc:
        return exc.errno in (errno.EPERM,errno.EACCES,errno.ENETUNREACH,
            errno.ECONNREFUSED,errno.ETIMEDOUT),exc.errno

def main():
    public,private,auth,history=map(Path,sys.argv[2:6]);port=int(sys.argv[6])
    result={'public_read':public.read_text()=='public canary'+chr(10)}
    for name,path in [('private',private),('auth',auth),('history',history)]:
        result[name+'_read_denied'],result[name+'_read_errno']=denied(path)
    result['host_loopback_denied'],result['network_errno']=blocked_port(port)
    if sys.argv[1]=='--parent':
        (public.parent/'write-canary').write_text('written')
        result['workspace_write']=True
        child=subprocess.run([sys.executable,'-I',str(Path(__file__)),
            '--child',*[str(path) for path in (public,private,auth,history)],str(port)],
            capture_output=True,text=True,timeout=5)
        result['native_child_exit_code']=child.returncode
        nested=json.loads(child.stdout) if child.returncode==0 else {}
        for key in ['public_read','private_read_denied','auth_read_denied',
                    'history_read_denied','host_loopback_denied']:
            result['native_child_'+key]=nested.get(key) is True
    print(json.dumps(result))

if __name__=='__main__':
    main()
