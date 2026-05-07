#!/usr/bin/env python
import sys
sys.path.insert(0, '/Users/user/Developer/GitHub/Rig/src')

from pathlib import Path
from rig_tools.window_launcher import _create_textual_app_module
import subprocess
import time
import shutil
import tempfile

repo_root = Path('.')
src_path = str((repo_root / 'src').resolve())
module_name = 'rig_window_app'
port = 20005

# Create temp module
temp_dir = Path(tempfile.mkdtemp())
module_code = f'''import sys
sys.path.insert(0, "{src_path}")
from pathlib import Path
from rig_tools.tui_grid import GridlineApp

class RigWindowApp(GridlineApp):
    def __init__(self):
        super().__init__(Path("{repo_root}"), chat_enabled=False)

if __name__ == "__main__":
    app = RigWindowApp()
    app.run()
'''
module_path = temp_dir / f'{module_name}.py'
module_path.write_text(module_code)

print(f'Created module at: {module_path}')

# Try different command formats
commands = [
    f'PYTHONPATH={temp_dir}:{src_path} python -m {module_name}',
    f'PYTHONPATH={temp_dir}:{src_path} python {module_path}',
]

for i, cmd in enumerate(commands):
    print(f'\nTest {i+1}: {cmd[:80]}...')
    
    # Create server script for this command
    server_script = f'''
import sys
from textual_serve.server import Server
server = Server(command="{cmd}", host="127.0.0.1", port={port+i}, title="Rig")
server.serve()
'''
    server_path = temp_dir / f'server_{i}.py'
    server_path.write_text(server_script)
    
    proc = subprocess.Popen([sys.executable, str(server_path)], cwd=temp_dir)
    time.sleep(2)
    
    if proc.poll() is None:
        print(f'  Server running, testing curl...')
        import subprocess as sp
        try:
            result = sp.run(['curl', '-s', '-N', '-H', 'Connection: close', 
                           f'http://127.0.0.1:{port+i}'],
                          capture_output=True, text=True, timeout=2)
            html = result.stdout[:300] if result.stdout else ''
            if '<!DOCTYPE html>' in html and 'intro' in html:
                print(f'  -> Got Textual intro page (app not loaded)')
            elif 'RIG' in html or 'Gridline' in html:
                print(f'  -> Got our app!')
            else:
                print(f'  -> Got something else: {html[:100]}')
        except Exception as e:
            print(f'  -> Curl error: {e}')
        
        proc.terminate()
        proc.wait(timeout=3)
    else:
        print(f'  Server failed')

shutil.rmtree(temp_dir)
print('\nDone')
