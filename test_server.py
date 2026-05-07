#!/usr/bin/env python
import sys
sys.path.insert(0, '/Users/user/Developer/GitHub/Rig/src')

from pathlib import Path
from rig_tools.window_launcher import _create_textual_app_module, _create_server_script, _get_server_command
import subprocess
import time
import shutil

repo_root = Path('.')
src_path = str((repo_root / 'src').resolve())
module_name = 'rig_window_app'
port = 20003

temp_module_path = _create_textual_app_module(repo_root, chat_enabled=False, module_name=module_name)
temp_module_dir = temp_module_path.parent
server_cmd = _get_server_command(temp_module_dir, module_name, src_path, '127.0.0.1', port)

print(f'Starting server with command: {server_cmd}')
proc = subprocess.Popen(server_cmd, cwd=temp_module_dir)
time.sleep(3)

if proc.poll() is None:
    print('Server running, testing with curl...')
    import subprocess as sp
    result = sp.run(['curl', '-s', '-N', '-H', 'Connection: close', f'http://127.0.0.1:{port}'], 
                   capture_output=True, text=True, timeout=3)
    print('Response (first 200 chars):', result.stdout[:200] if result.stdout else 'None')
    proc.terminate()
    proc.wait(timeout=5)
else:
    print('Server failed')

shutil.rmtree(temp_module_dir)
