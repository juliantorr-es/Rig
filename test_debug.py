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

# Create app module with debug output
module_code = f'''import sys
sys.path.insert(0, "{src_path}")
print("DEBUG: App module loaded, sys.path[0] = " + sys.path[0], flush=True)
from pathlib import Path
from rig_tools.tui_grid import GridlineApp

class RigWindowApp(GridlineApp):
    def __init__(self):
        print("DEBUG: RigWindowApp.__init__ called", flush=True)
        super().__init__(Path("/Users/user/Developer/GitHub/Rig"), chat_enabled=False)
    
    def on_ready(self):
        print("DEBUG: App ready", flush=True)

if __name__ == "__main__":
    print("DEBUG: Starting app run", flush=True)
    app = RigWindowApp()
    app.run()
'''
module_path = temp_dir / 'rig_window_app.py'
module_path.write_text(module_code)

# Create server script
server_code = f'''
import sys
from textual_serve.server import Server
server = Server(
    command="python -m rig_window_app",
    host="127.0.0.1",
    port=20008,
    title="Rig"
)
print("DEBUG: Starting server.serve()", flush=True)
server.serve()
'''
server_path = temp_dir / 'server.py'
server_path.write_text(server_code)

# Capture stderr from server
proc = subprocess.Popen(
    [sys.executable, str(server_path)],
    cwd=temp_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Wait a bit and check output
time.sleep(3)

# Check if we got any stderr output (from the app subprocess)
if proc.poll() is None:
    # Try to peek at stderr
    proc.terminate()
    stdout, stderr = proc.communicate(timeout=3)
    print('Server stdout:', stdout[:500] if stdout else 'None')
    print('Server stderr:', stderr[:500] if stderr else 'None')
else:
    stdout, stderr = proc.communicate()
    print('Server stdout:', stdout[:500] if stdout else 'None')
    print('Server stderr:', stderr[:500] if stderr else 'None')

shutil.rmtree(temp_dir)
