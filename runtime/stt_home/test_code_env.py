from pathlib import Path
from tempfile import TemporaryDirectory
from runtime.stt_home.code_env import CodeEnvironment, CodeEnvironmentError

with TemporaryDirectory() as d:
    c=CodeEnvironment(Path(d))
    assert c.write('x.py','print(42)')['bytes']>0
    assert c.read('x.py')['content']=='print(42)'
    assert c.run_python('x.py')['status']=='COMPLETED'
    assert c.run_python('x.py')['stdout'].strip()=='42'
    assert c.git_status()['status'] in {'COMPLETED','FAILED'}
    try: c.read('../escape')
    except CodeEnvironmentError as e: assert str(e)=='workspace_path_outside_root'
    else: raise AssertionError('path traversal not blocked')
print('CODE_ENV_TEST PASS')
