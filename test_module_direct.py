#!/usr/bin/env python
import sys
import os
import tempfile
from pathlib import Path

# Create temp dir
temp_dir = Path(tempfile.mkdtemp())

# Create the app module
module_code = '''import sys
sys.path.insert(0, "/Users/user/Developer/GitHub/Rig/src")
from pathlib import Path
from rig_tools.tui_grid import GridlineApp

class RigWindowApp(GridlineApp):
    def __init__(self):
        super().__init__(Path("/Users/user/Developer/GitHub/Rig"), chat_enabled=False)

if __name__ == "__main__":
    print("Starting RigWindowApp...")
    app = RigWindowApp()
    app.run()
'''

module_path = temp_dir / 'rig_window_app.py'
module_path.write_text(module_code)

print(f'Created module at: {module_path}')
print(f'Running: PYTHONPATH={temp_dir} python -m rig_window_app')

import subprocess
proc = subprocess.Popen(
    f'PYTHONPATH={temp_dir} python -m rig_window_app',
    shell=True,
    cwd=temp_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

import time
time.sleep(1)

if proc.poll() is None:
    print('App is running, terminating...')
    proc.terminate()
    proc.wait()
else:
    stdout, stderr = proc.communicate()
    print(f'STDOUT: {stdout[:200] if stdout else None}')
    print(f'STDERR: {stderr[:200] if stderr else None}')

# Cleanup
import shutil
shutil.rmtree(temp_dir)
print('Done')
