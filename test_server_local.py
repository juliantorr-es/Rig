import sys
from pathlib import Path
sys.path.insert(0, str(Path('./src').resolve()))

from rig_tools.ui_server import RigUIServer
import asyncio

async def main():
    repo_root = Path('.').resolve()
    server = RigUIServer(repo_root=repo_root, host="127.0.0.1", port=65372, session_token="test_token")
    print("Starting server...")
    runner = await server.start()
    print("Server started. Try curling http://127.0.0.1:65372/?rig_session=test_token")
    await asyncio.sleep(5)
    await server.stop()
    print("Server stopped.")

if __name__ == '__main__':
    asyncio.run(main())