import asyncio
import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from aiohttp import web

from rig.domain.intent_defs import Intent, IntentHandler
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
        # Check if this is a manual path attempt from the browser UI
        target = intent.target or {}
        workspace_path = target.get("workspace_path")
        
        if workspace_path:
            logger.debug(f"Manual path received for {intent.kind}: {workspace_path}")
            return {
                "accepted": False,
                "reason": f"Manual path entry requires backend workspace initialization. Path: {workspace_path}. This will be implemented in the next phase.",
                "status": "path_received",
                "workspace_path": workspace_path,
            }
        
        # For open_workspace and initialize_current_folder, provide actionable guidance
        if intent.kind == "rig.intent.open_workspace":
            return {
                "accepted": False,
                "reason": "Native file dialog is not available in browser mode. Use the manual path entry field to enter a Rig repository path, or run 'rig window open' from the command line.",
                "status": "browser_mode_limitation",
            }
        if intent.kind == "rig.intent.initialize_current_folder":
            return {
                "accepted": False,
                "reason": "Current folder initialization requires terminal access. Use the manual path entry field, or initialize from command line with 'rig workspace init'.",
                "status": "browser_mode_limitation",
            }
        
        return {
            "accepted": False,
            "reason": f"Intent '{intent.kind}' not implemented in this phase.",
            "status": "not_implemented",
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
        
        # Dispatch through IntentDispatcher for governed execution
        from rig.domain.intents.dispatcher import get_intent_dispatcher
        from rig.domain.receipts import get_receipt_store, ValidatorReceipt
        from rig.domain.execution.models import ExecutionRequest
        from datetime import datetime, timezone
        
        dispatcher = get_intent_dispatcher(self.repo_root)
        receipt_store = get_receipt_store(self.repo_root)
        executor = dispatcher.executor
        
        # Generate a stream ID for this validation run
        run_stream_id = f"val-run-{ws_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        
        # Get validator configs from domain
        from rig.domain.workspace import WorkspaceDomain
        domain = WorkspaceDomain(self.repo_root)
        validator_configs = domain.read_validator_config()
        
        if not validator_configs:
            # No validators configured - emit event and broadcast
            self._schedule_send({
                "kind": "event",
                "data": {"type": "validator_config_empty", "workspace_id": ws_id}
            })
            self.revision += 1
            asyncio.create_task(self.broadcast_projection())
            return {"accepted": False, "reason": "No validators configured for workspace"}
        
        total_validators = len(validator_configs)
        passed_count = 0
        failed_count = 0
        overall_status = "passed"
        validator_receipt_ids = []
        
        # Create a ValidatorStreamSink that bridges to WebSocket
        from rig.domain.execution.models import ExecutionStreamEvent, CollectingStreamSink
        
        class WSSStreamSink(CollectingStreamSink):
            """Stream sink that forwards ExecutionStreamEvents to WebSocket clients."""
            def __init__(self, outer_server, validator_stream_id):
                super().__init__()
                self.outer = outer_server
                self.validator_stream_id = validator_stream_id
            
            def on_stream_event(self, event: ExecutionStreamEvent):
                super().on_stream_event(event)
                seq = self.outer._get_next_sequence(self.validator_stream_id)
                chunk_data = {
                    "stream_id": self.validator_stream_id,
                    "sequence": seq,
                    "content": event.content,
                    "channel": event.channel,
                    "timestamp": event.timestamp,
                }
                self.outer._schedule_send({
                    "kind": "stream_chunk",
                    "data": chunk_data
                })
        
        # Process each validator sequentially
        for v_idx, v_conf in enumerate(validator_configs):
            v_id = v_conf.get("id", v_conf.get("argv", [""])[0])
            argv = [str(part) for part in v_conf.get("argv", [])]
            timeout = v_conf.get("timeout", 60)
            required = v_conf.get("required", False)
            validator_stream_id = f"{run_stream_id}-v{v_idx}-{v_id}"
            
            # Send validator started event
            self._schedule_send({
                "kind": "event",
                "data": {
                    "type": "validator_started",
                    "validator_id": v_id,
                    "validator_index": v_idx,
                    "total_validators": total_validators,
                    "workspace_id": ws_id,
                    "stream_id": validator_stream_id
                }
            })
            
            # Create execution request
            request = ExecutionRequest(
                argv=argv,
                cwd=self.repo_root,
                timeout_seconds=min(timeout, 300),  # Cap at 5 minutes
                workspace_id=ws_id,
                purpose=f"validator:{v_id}",
                client_id="ui_server",
                actor_id="intent_dispatcher",
                stream_id=validator_stream_id
            )
            
            # Acquire lease and execute
            lease = executor.acquire_lease(request)
            stream_sink = WSSStreamSink(self, validator_stream_id)
            
            try:
                result_or_failure = executor.execute(lease, stream_sink=stream_sink)
                
                # Check result
                if hasattr(result_or_failure, 'succeeded') and result_or_failure.succeeded:
                    passed_count += 1
                    v_status = "passed"
                    exit_code = 0
                else:
                    failed_count += 1
                    v_status = "failed"
                    overall_status = "failed"
                    exit_code = getattr(result_or_failure, 'exit_code', 1) or 1
                
                # Create validator receipt
                receipt = ValidatorReceipt(
                    receipt_id=f"val-{v_id}-{ws_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
                    kind="validator_run",
                    workspace_id=ws_id,
                    actor_id="ui_server",
                    status=v_status,
                    summary=f"Validator {v_id} exited with code {exit_code}",
                    validator_id=v_id,
                    validated_path=str(self.repo_root),
                    exit_code=exit_code,
                )
                receipt_id = receipt_store.append(receipt)
                validator_receipt_ids.append(receipt_id)
                
                # Send validator finished event (with receipt_id for correlation)
                self._schedule_send({
                    "kind": "event",
                    "data": {
                        "type": "validator_finished",
                        "validator_id": v_id,
                        "validator_index": v_idx,
                        "exit_code": exit_code,
                        "status": v_status,
                        "receipt_id": receipt_id,
                        "workspace_id": ws_id,
                        "stream_id": validator_stream_id
                    }
                })
                
            except Exception as ex:
                failed_count += 1
                overall_status = "failed"
                error_summary = str(ex)[:200]
                
                receipt = ValidatorReceipt(
                    receipt_id=f"val-{v_id}-err-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
                    kind="validator_run",
                    workspace_id=ws_id,
                    actor_id="ui_server",
                    status="error",
                    summary=f"Validator {v_id} error: {error_summary}",
                    validator_id=v_id,
                    exit_code=None,
                )
                receipt_id = receipt_store.append(receipt)
                validator_receipt_ids.append(receipt_id)
                
                self._schedule_send({
                    "kind": "event",
                    "data": {
                        "type": "validator_error",
                        "validator_id": v_id,
                        "validator_index": v_idx,
                        "error": error_summary,
                        "receipt_id": receipt_id,
                        "workspace_id": ws_id,
                        "stream_id": validator_stream_id
                    }
                })
            finally:
                executor.release_lease(lease)
        
        # Create summary receipt for the entire validation run
        summary_receipt = ValidatorReceipt(
            receipt_id=f"val_run_{ws_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            kind="validator_run",
            workspace_id=ws_id,
            actor_id="ui_server",
            status=overall_status,
            summary=f"Validators: {passed_count} passed, {failed_count} failed out of {total_validators}",
            validator_id=f"validation_run_{ws_id}",
            exit_code=0 if overall_status == "passed" else 1,
        )
        summary_receipt_id = receipt_store.append(summary_receipt)
        logger.info(f"Validator run receipt created: {summary_receipt_id}")
        
        # Send final summary event
        self._schedule_send({
            "kind": "event",
            "data": {
                "type": "validator_run_complete",
                "workspace_id": ws_id,
                "receipt_id": summary_receipt_id,
                "validator_receipt_ids": validator_receipt_ids,
                "status": overall_status,
                "passed": passed_count,
                "failed": failed_count,
                "total": total_validators
            }
        })
        
        # Update workspace domain validation result
        try:
            domain.generate_validation_result(ws_id)
        except Exception:
            pass
        
        # Update projection
        self.revision += 1
        asyncio.create_task(self.broadcast_projection())
        
        return {"accepted": True}

    def _get_next_sequence(self, stream_id: str) -> int:
        self._next_stream_sequence[stream_id] = self._next_stream_sequence.get(stream_id, 0) + 1
        return self._next_stream_sequence[stream_id]

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
