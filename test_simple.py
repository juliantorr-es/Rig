#!/usr/bin/env python
import sys
import tempfile
import subprocess
import time
import shutil
from pathlib import Path

# Create temp dir
temp_dir = Path(tempfile.mkdtemp())
src_path = '/Users/user/Developer/GitHub/Rig/src'

# Create app module - embed the src path directly
module_code = f'''import sys
sys.path.insert(0, "{src_path}")
sys.path.insert(0, "{temp_dir}")
from pathlib import Path
from rig_tools.tui_grid import GridlineApp

class RigWindowApp(GridlineApp):
    def __init__(self):
        super().__init__(Path("/Users/user/Developer/GitHub/Rig"), chat_enabled=False)

if __name__ == "__main__":
    app = RigWindowApp()
    app.run()
'''
module_path = temp_dir / 'rig_window_app.py'
module_path.write_text(module_code)

# Create server script - NO PYTHONPATH, just python -m module
server_code = f'''
import sys
from textual_serve.server import Server
server = Server(
    command="python -m rig_window_app",
    host="127.0.0.1",
    port=20007,
    title="Rig"
)
server.serve()
'''
server_path = temp_dir / 'server.py'
server_path.write_text(server_code)

print(f'Temp dir: {temp_dir}')
print(f'Module: {module_path}')

# Run from temp dir so Python can find the module
proc = subprocess.Popen([sys.executable, str(server_path)], cwd=temp_dir)
time.sleep(3)

if proc.poll() is None:
    print('Server running, testing...')
    import subprocess as sp
    result = sp.run(['curl', '-s', '-N', '-H', 'Connection: close', 'http://127.0.0.1:20007'],
                   capture_output=True, text=True, timeout=2)
    html = result.stdout[:400] if result.stdout else ''
    if 'RIG' in html or 'GRIDLINE' in html or 'COMMAND CENTER' in html:
        print('SUCCESS: Got our app content!')
        print(f'HTML snippet: {html[:200]}')
    elif 'intro' in html:
        print('FAIL: Got Textual intro page')
    else:
        print(f'Got: {html[:200]}')
    proc.terminate()
    proc.wait(timeout=3)
else:
    print('Server failed')

shutil.rmtree(temp_dir)
