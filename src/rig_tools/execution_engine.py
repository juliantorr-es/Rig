import subprocess
from pathlib import Path
from typing import List, Dict, Any

class ExecutionEngine:
    def __init__(self, worktree_dir: Path):
        self.worktree_dir = worktree_dir

    def execute_plan(self, commands: List[List[str]]) -> Dict[str, Any]:
        executed_commands = []
        for cmd in commands:
            try:
                subprocess.run(cmd, cwd=self.worktree_dir, check=True, capture_output=True)
                executed_commands.append(" ".join(cmd))
            except subprocess.CalledProcessError as e:
                return {"status": "failed", "commands": executed_commands, "error": str(e)}
        return {"status": "success", "commands": executed_commands}
