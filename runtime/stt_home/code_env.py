from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

class CodeEnvironmentError(ValueError): pass

class CodeEnvironment:
    def __init__(self, root: Path):
        self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
    def _path(self, rel: str)->Path:
        if not rel or rel in {'.','./'}: return self.root
        p=(self.root/rel).resolve()
        if p!=self.root and self.root not in p.parents: raise CodeEnvironmentError('workspace_path_outside_root')
        return p
    def _run(self, argv:list[str], timeout_s:int=30)->dict:
        timeout_s=max(1,min(int(timeout_s),60))
        env={k:os.environ.get(k,'') for k in ('PATH','SystemRoot','TEMP','TMP')}
        env['PYTHONIOENCODING']='utf-8'
        try: p=subprocess.run(argv,cwd=self.root,env=env,shell=False,capture_output=True,text=True,timeout=timeout_s)
        except subprocess.TimeoutExpired as e: return {'status':'TIMED_OUT','returncode':None,'stdout':(e.stdout or '')[:100000],'stderr':(e.stderr or '')[:100000]}
        return {'status':'COMPLETED' if p.returncode==0 else 'FAILED','returncode':p.returncode,'stdout':p.stdout[:100000],'stderr':p.stderr[:100000]}
    def list(self,rel='.')->list[dict]:
        p=self._path(rel)
        if not p.is_dir(): raise CodeEnvironmentError('workspace_directory_required')
        return [{'name':x.name,'type':'directory' if x.is_dir() else 'file','size':x.stat().st_size if x.is_file() else None} for x in sorted(p.iterdir(),key=lambda x:(not x.is_dir(),x.name.lower()))]
    def read(self,rel,max_bytes=256000)->dict:
        p=self._path(rel)
        if not p.is_file(): raise CodeEnvironmentError('workspace_file_required')
        b=p.read_bytes()
        if len(b)>max_bytes: raise CodeEnvironmentError('workspace_file_too_large')
        return {'path':rel,'content':b.decode('utf-8'),'bytes':len(b)}
    def write(self,rel,content)->dict:
        p=self._path(rel); b=content.encode('utf-8')
        if len(b)>512000: raise CodeEnvironmentError('workspace_write_too_large')
        p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b); return {'path':rel,'bytes':len(b)}
    def git_status(self): return self._run(['git','status','--short'],20)
    def git_diff(self,staged=False): return self._run(['git','diff','--cached' if staged else '--'],30)
    def run_python(self,rel,args=None,timeout_s=20):
        p=self._path(rel)
        if not p.is_file(): raise CodeEnvironmentError('workspace_file_required')
        if p.suffix.lower()!='.py': raise CodeEnvironmentError('workspace_run_allows_python_only')
        r=self._run([sys.executable,'-I',str(p),*(args or [])],timeout_s); return r
    def run_tests(self,target='.',timeout_s=60):
        p=self._path(target)
        if not p.exists(): raise CodeEnvironmentError('test_target_not_found')
        return self._run([sys.executable,'-m','pytest',str(p)],timeout_s)
