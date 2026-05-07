import asyncio
import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from aiohttp import web

from rig.domain.intents import Intent, IntentHandler
from rig.domain.projection_builder import build_projection
from rig.domain.projections import ChatMessage, UIProjection

logger = logging.getLogger(__name__)

# Safe intents that can be accepted even with stale projection revisions
SAFE_INTENTS = {"rig.intent.refresh_projection"}


class UIServer:
    def __init__(self, repo_root: Path, session_token: str):
        self.repo_root = repo_root
        self.session_token = session_token
        self.app = web.Application()
        self.app.add_routes([
            web.get("/ui/ws", self.websocket_handler),
            web.static("/static", Path(__file__).parent / "static")
        ])
        self.app.router.add_get("/", self.index_handler)
        
        self.clients: Set[web.WebSocketResponse] = set()
        self.intent_handler = IntentHandler()
        self.revision = 1
        self.chat_history: List[ChatMessage] = []
        self._next_stream_sequence: Dict[str, int] = {}
        
        # Register handlers
        self.intent_handler.register("rig.intent.open_workspace", self._stub_handler)
        self.intent_handler.register("rig.intent.initialize_current_folder", self._stub_handler)
        self.intent_handler.register("rig.intent.refresh_projection", self.handle_refresh)
        self.intent_handler.register("rig.intent.chat.submit", self.handle_chat_submit)
        self.intent_handler.register("rig.intent.run_validators", self.handle_run_validators)

    def _stub_handler(self, intent: Intent) -> Dict[str, Any]:
        return {
            "accepted": False,
            "reason": f"Intent '{intent.kind}' not implemented in this phase.",
            "status": "not_implemented"
        }

    def handle_refresh(self, intent: Intent) -> Dict[str, Any]:
        return {"accepted": True}

    def handle_run_validators(self, intent: Intent) -> Dict[str, Any]:
        # Re-check if intent is enabled by looking at current projection
        current_projection = build_projection(self.repo_root, revision=self.revision, chat_history=self.chat_history)
        intent_key = None
        for key, ip in current_projection.intents.items():
            if ip.kind == intent.kind:
                intent_key = key
                break
        
        if intent_key is None:
            return {"accepted": False, "reason": f"Unknown intent kind: {intent.kind}"}
        
        intent_proj = current_projection.intents[intent_key]
        if not intent_proj.enabled:
            return {
                "accepted": False,
                "reason": intent_proj.disabled_reason or f"Intent '{intent.kind}' is currently disabled."
            }
        
        ws_id = intent.target.get("workspace_id") if intent.target else None
        if not ws_id:
            return {"accepted": False, "reason": "Missing workspace_id"}
        
        asyncio.create_task(self._run_validators_task(ws_id))
        return {"accepted": True}

    def _get_next_sequence(self, stream_id: str) -> int:
        self._next_stream_sequence[stream_id] = self._next_stream_sequence.get(stream_id, 0) + 1
        return self._next_stream_sequence[stream_id]

    async def _run_validators_task(self, ws_id: str):
        from rig.domain.workspace import WorkspaceDomain
        domain = WorkspaceDomain(self.repo_root)
        
        def progress(p):
            # Map domain progress to UI messages
            # Use thread-safe scheduling
            if p["kind"] == "validator_start":
                self._schedule_send({"kind": "event", "data": {"type": "validator_started", "id": p["validator_id"]}})
            elif p["kind"] == "validator_output":
                stream_id = f"val-{p['validator_id']}"
                self._schedule_send({"kind": "stream_chunk", "data": {
                    "stream_id": stream_id,
                    "sequence": self._get_next_sequence(stream_id),
                    "content": p["content"],
                    "channel": p["channel"]
                }})
            elif p["kind"] == "validator_end":
                self._schedule_send({"kind": "event", "data": {"type": "validator_finished", "id": p["validator_id"], "exit_code": p["exit_code"]}})
        
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: domain.generate_validation_result(ws_id, progress_callback=progress))
        
        self.revision += 1
        await self.broadcast_projection()

    def _schedule_send(self, msg: Dict[str, Any]):
        """Thread-safe method to schedule sending a message to all clients."""
        msg["schema_version"] = "rig.ui.message.v1"
        async def _do_send():
            for ws in self.clients.copy():
                try:
                    await ws.send_json(msg)
                except Exception:
                    pass  # Client already disconnected
        
        # Use asyncio.run_coroutine_threadsafe to safely schedule from executor thread
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop - create task directly (shouldn't happen in normal operation)
            asyncio.create_task(_do_send())
            return
        
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_do_send(), loop)
        else:
            asyncio.create_task(_do_send())

    def handle_chat_submit(self, intent: Intent) -> Dict[str, Any]:
        from rig.domain.projection_builder import build_projection
        
        # Re-check if chat.submit is enabled in current projection
        current_projection = build_projection(self.repo_root, revision=self.revision, chat_history=self.chat_history)
        chat_intent_key = None
        for key, ip in current_projection.intents.items():
            if ip.kind == "rig.intent.chat.submit":
                chat_intent_key = key
                break
        
        if chat_intent_key is None:
            return {"accepted": False, "reason": "Chat intent not found in projection."}
        
        chat_intent_proj = current_projection.intents[chat_intent_key]
        if not chat_intent_proj.enabled:
            return {
                "accepted": False,
                "reason": chat_intent_proj.disabled_reason or "Chat is currently disabled."
            }
        
        text = intent.target.get("text", "") if intent.target else ""
        if not text:
            return {"accepted": False, "reason": "Empty message"}
        
        # 1. Record user message
        user_msg = ChatMessage(role="user", content=text, at=datetime.now(timezone.utc).isoformat())
        self.chat_history.append(user_msg)
        
        response = self._get_deterministic_response(text)
        asyncio.create_task(self._stream_assistant_response(response))
        
        return {"accepted": True}

    async def _stream_assistant_response(self, response: str):
        """Stream assistant response and append final message to chat history."""
        stream_id = f"chat-{len(self.chat_history)}"
        
        # Split response into chunks for streaming
        # Simple line-based streaming for deterministic responses
        lines = response.split('. ')
        
        loop = asyncio.get_running_loop()
        
        for i, line in enumerate(lines):
            chunk = line.strip() + '. ' if line.strip() else ''
            if not chunk:
                continue
            
            seq = self._get_next_sequence(stream_id)
            msg = {
                "schema_version": "rig.ui.message.v1",
                "kind": "stream_chunk",
                "data": {
                    "stream_id": stream_id,
                    "sequence": seq,
                    "content": chunk,
                    "channel": "assistant"
                }
            }
            
            for ws in self.clients.copy():
                try:
                    await ws.send_json(msg)
                except Exception:
                    pass
            
            # Small delay to simulate streaming
            await loop.run_in_executor(None, lambda: None)  # Yield control
        
        # Append final assistant message to chat history
        assistant_msg = ChatMessage(
            role="assistant",
            content=response,
            at=datetime.now(timezone.utc).isoformat()
        )
        self.chat_history.append(assistant_msg)
        
        # Increment revision and broadcast updated projection
        self.revision += 1
        await self.broadcast_projection()

    def _get_deterministic_response(self, text: str) -> str:
        text = text.lower()
        if "what can i do" in text or "next" in text:
            return "Based on the current projection, you should run validators on the active workspace. If they pass, you can then proceed to review."
        if "why is apply disabled" in text or "apply" in text:
            return "The 'Apply Patch' action is gated by validation success and human approval. Ensure validators are green first."
        if "status" in text or "what happened" in text:
            return f"Current revision is {self.revision}. I am monitoring the workspace for state transitions."
        return f"I am a local governance agent. I've recorded your message: '{text}'. Currently, I am optimized for coordinating workspace validations and state projections."

    async def index_handler(self, request: web.Request):
        token = request.query.get("rig_session")
        if token != self.session_token:
            return web.Response(text="Unauthorized: Invalid session token", status=401)
        
        index_path = Path(__file__).parent / "static" / "index.html"
        if not index_path.exists():
            return web.Response(text="Frontend not found", status=404)
        
        return web.FileResponse(index_path)

    async def websocket_handler(self, request: web.Request):
        token = request.query.get("rig_session")
        if token != self.session_token:
            return web.Response(status=401)

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.clients.add(ws)
        logger.info(f"UI client connected. Total: {len(self.clients)}")
        
        try:
            # Send initial projection
            await self.broadcast_projection(ws)
            
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self.handle_message(ws, data)
                    except json.JSONDecodeError:
                        await ws.send_json({"kind": "error", "message": "Invalid JSON"})
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket closed with error: {ws.exception()}")
        finally:
            self.clients.remove(ws)
            logger.info(f"UI client disconnected. Total: {len(self.clients)}")
        
        return ws

    async def handle_message(self, ws: web.WebSocketResponse, data: Dict[str, Any]):
        kind = data.get("kind")
        schema = data.get("schema_version")
        
        if kind == "hello":
            await self.broadcast_projection(ws)
        elif kind == "intent":
            # New protocol: intent message has rig.ui.message.v1 envelope with nested intent
            # Validate envelope schema
            if schema != "rig.ui.message.v1":
                await ws.send_json({
                    "schema_version": "rig.ui.message.v1",
                    "kind": "error",
                    "message": f"Unsupported message schema: {schema}. Expected rig.ui.message.v1."
                })
                return
            
            # Extract and validate nested intent
            nested_intent = data.get("intent")
            if not nested_intent:
                await ws.send_json({
                    "schema_version": "rig.ui.message.v1",
                    "kind": "error",
                    "message": "Missing nested intent in message envelope."
                })
                return
            
            intent_schema = nested_intent.get("schema_version")
            if intent_schema != "rig.ui.intent.v1":
                await ws.send_json({
                    "schema_version": "rig.ui.message.v1",
                    "kind": "error",
                    "message": f"Unsupported intent schema: {intent_schema}. Expected rig.ui.intent.v1."
                })
                return
            
            # Build Intent object from nested intent
            intent = Intent(
                intent_id=nested_intent.get("intent_id", ""),
                kind=nested_intent.get("kind", ""),
                target=nested_intent.get("target"),
                observed_projection_revision=nested_intent.get("observed_projection_revision", 0),
                idempotency_key=nested_intent.get("idempotency_key"),
                submitted_at=nested_intent.get("submitted_at", ""),
                client=nested_intent.get("client", {"kind": "pywebview"})
            )
            
            # Validate intent kind
            if not intent.kind:
                await ws.send_json({
                    "schema_version": "rig.ui.message.v1",
                    "kind": "error",
                    "message": "Intent kind is required."
                })
                return
            
            # Check for stale projection revision
            # Build current projection to check intent enabled status
            current_projection = build_projection(self.repo_root, revision=self.revision, chat_history=self.chat_history)
            
            # Find matching intent in projection
            intent_key = None
            for key, ip in current_projection.intents.items():
                if ip.kind == intent.kind:
                    intent_key = key
                    break
            
            # Reject if intent not found in projection
            if intent_key is None:
                await ws.send_json({
                    "schema_version": "rig.ui.message.v1",
                    "kind": "error",
                    "message": f"Unknown intent kind: {intent.kind}"
                })
                return
            
            intent_proj = current_projection.intents[intent_key]
            
            # Reject if intent is disabled
            if not intent_proj.enabled:
                await ws.send_json({
                    "schema_version": "rig.ui.message.v1",
                    "kind": "error",
                    "message": intent_proj.disabled_reason or f"Intent '{intent.kind}' is currently disabled."
                })
                return
            
            # Check for stale projection revision (unless it's a safe intent)
            if intent.observed_projection_revision < self.revision and intent.kind not in SAFE_INTENTS:
                await ws.send_json({
                    "schema_version": "rig.ui.message.v1",
                    "kind": "error",
                    "message": f"Stale projection revision {intent.observed_projection_revision}. Current revision is {self.revision}. Please refresh."
                })
                return
            
            # dispatch to handler
            result = self.intent_handler.handle(intent)
            
            await ws.send_json({
                "schema_version": "rig.ui.message.v1",
                "kind": "intent_result",
                "correlation_id": intent.intent_id,
                "data": result
            })
            
            if result.get("accepted"):
                self.revision += 1
                await self.broadcast_projection()
        else:
            await ws.send_json({
                "schema_version": "rig.ui.message.v1",
                "kind": "error",
                "message": f"Unknown message kind: {kind}"
            })

    async def broadcast_projection(self, target_ws: Optional[web.WebSocketResponse] = None):
        projection = build_projection(self.repo_root, revision=self.revision, chat_history=self.chat_history)
        msg = {
            "schema_version": "rig.ui.message.v1",
            "kind": "projection",
            "data": asdict(projection)
        }
        
        if target_ws:
            await target_ws.send_json(msg)
        else:
            for ws in self.clients:
                await ws.send_json(msg)

    async def start(self, host: str = "127.0.0.1", port: int = 0):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        actual_port = runner.addresses[0][1]
        logger.info(f"UI Server started at http://{host}:{actual_port}")
        return actual_port
