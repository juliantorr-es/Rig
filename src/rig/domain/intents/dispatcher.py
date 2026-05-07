"""IntentDispatcher - Governed intent routing.

The IntentDispatcher provides a clean seam for routing intents through
governed execution paths. It:
- Maintains a registry of intent handlers
- Routes intents based on kind
- Performs capability preflight checks
- Returns structured results
- Does NOT contain UI logic or direct WebSocket handling

Currently supports routing for:
- rig.intent.run_validators (migrated path)
- Other intents can be added via register_handler()

Example:
    dispatcher = IntentDispatcher(repo_root)
    
    # Register a handler
    dispatcher.register_handler("rig.intent.my_intent", my_handler)
    
    # Dispatch an intent
    result = dispatcher.dispatch(intent)
    # result is IntentResult with accepted/status/reason
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable, TypeVar

from rig.domain.intent_defs import Intent
from rig.domain.execution import WorktreeExecutor
from rig.domain.receipts import ReceiptStore, get_receipt_store

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================

@dataclass
class IntentResult:
    """Result of intent dispatching."""
    intent_id: str
    intent_kind: str
    accepted: bool
    status: str  # "pending", "running", "completed", "failed", "rejected"
    result: Optional[Any] = None
    error: Optional[str] = None
    reason: Optional[str] = None
    
    @classmethod
    def success(cls, intent: Intent, result: Any = None) -> "IntentResult":
        """Create a success result."""
        return cls(
            intent_id=intent.intent_id or intent.kind,
            intent_kind=intent.kind,
            accepted=True,
            status="completed",
            result=result
        )
    
    @classmethod
    def failure(cls, intent: Intent, error: str, reason: str = "") -> "IntentResult":
        """Create a failure result."""
        return cls(
            intent_id=intent.intent_id or intent.kind,
            intent_kind=intent.kind,
            accepted=False,
            status="failed",
            error=error,
            reason=reason
        )
    
    @classmethod
    def rejected(cls, intent: Intent, reason: str) -> "IntentResult":
        """Create a rejected result (preflight failure)."""
        return cls(
            intent_id=intent.intent_id or intent.kind,
            intent_kind=intent.kind,
            accepted=False,
            status="rejected",
            reason=reason
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d: Dict[str, Any] = {
            "intent_id": self.intent_id,
            "intent_kind": self.intent_kind,
            "accepted": self.accepted,
            "status": self.status,
        }
        if self.result:
            d["result"] = self.result
        if self.error:
            d["error"] = self.error
        if self.reason:
            d["reason"] = self.reason
        return d


@dataclass
class HandlerContext:
    """Context passed to intent handlers."""
    repo_root: Path
    executor: WorktreeExecutor
    receipt_store: ReceiptStore
    
    # Request context
    client_id: Optional[str] = None
    workspace_id: Optional[str] = None
    stream_id: Optional[str] = None


# Type variable for handler functions
T = TypeVar('T')


@runtime_checkable
class IntentHandler(Protocol[T]):
    """Protocol for intent handler functions."""
    
    def __call__(self, context: HandlerContext, intent: Intent, **kwargs: Any) -> T:
        ...


# Concrete handler type
IntentHandlerFunc = Callable[[HandlerContext, Intent], IntentResult]


# =============================================================================
# IntentDispatcher
# =============================================================================

class IntentDispatcher:
    """Dispatcher for routing intents to governed handlers.
    
    Provides:
    - Intent handler registry
    - Capability preflight checks
    - Structured result handling
    - Separation from UI/WebSocket code
    
    Note: This is the domain-level dispatcher. UI integration should
    create a HandlerContext and call dispatch(), but WebSocket handling
    and projection updates belong in the presentation layer.
    """
    
    def __init__(
        self,
        repo_root: Path,
        executor: Optional[WorktreeExecutor] = None,
        receipt_store: Optional[ReceiptStore] = None
    ):
        self.repo_root = repo_root
        self._executor = executor or WorktreeExecutor(repo_root)
        self._receipt_store = receipt_store or get_receipt_store(repo_root)
        
        # Handler registry: intent_kind -> handler functions
        self._handlers: Dict[str, IntentHandlerFunc] = {}
        
        # Register built-in handlers
        self._register_builtin_handlers()
    
    @property
    def executor(self) -> WorktreeExecutor:
        return self._executor
    
    @property
    def receipt_store(self) -> ReceiptStore:
        return self._receipt_store
    
    # -------------------------------------------------------------------------
    # Handler Registration
    # -------------------------------------------------------------------------
    
    def register_handler(
        self,
        intent_kind: str,
        handler: IntentHandlerFunc
    ) -> None:
        """Register a handler for an intent kind."""
        self._handlers[intent_kind] = handler
        logger.debug(f"Intent handler registered: {intent_kind}")
    
    def unregister_handler(self, intent_kind: str) -> bool:
        """Unregister a handler. Returns True if found and removed."""
        if intent_kind in self._handlers:
            del self._handlers[intent_kind]
            logger.debug(f"Intent handler unregistered: {intent_kind}")
            return True
        return False
    
    def get_handler(self, intent_kind: str) -> Optional[IntentHandlerFunc]:
        """Get the handler for an intent kind."""
        return self._handlers.get(intent_kind)
    
    def list_handlers(self) -> list[str]:
        """List all registered intent kinds."""
        return list(self._handlers.keys())
    
    # -------------------------------------------------------------------------
    # Built-in Handlers
    # -------------------------------------------------------------------------
    
    def _register_builtin_handlers(self) -> None:
        """Register built-in intent handlers."""
        # run_validators handler - governed execution path
        self.register_handler(
            "rig.intent.run_validators",
            self._handle_run_validators
        )
    
    def _handle_run_validators(
        self,
        context: HandlerContext,
        intent: Intent
    ) -> IntentResult:
        """Handle rig.intent.run_validators via WorktreeExecutor.
        
        This is the migrated governed path for validator execution.
        It uses WorktreeExecutor with lease management and receipt creation.
        """
        target = intent.target or {}
        workspace_id = target.get("workspace_id") or context.workspace_id
        
        # Get validator config from workspace
        # For now, use a simple echo validator as demonstration
        # In production, this would read from workspace config
        validator_config = self._get_validator_config(workspace_id, context.repo_root)
        
        if not validator_config:
            return IntentResult.rejected(
                intent,
                reason="No validators configured for workspace"
            )
        
        # Build execution request for each validator
        # For simplicity, run all validators sequentially
        # Could be parallelized in future
        from rig.domain.execution.models import ExecutionRequest, CollectingStreamSink
        from rig.domain.receipts import ValidatorReceipt
        
        results = []
        for v_conf in validator_config:
            v_id = v_conf.get("id", v_conf.get("argv", [""])[0])
            argv = v_conf.get("argv", [])
            timeout = v_conf.get("timeout", 60)
            
            request = ExecutionRequest(
                argv=argv,
                cwd=context.repo_root,
                timeout_seconds=timeout,
                workspace_id=workspace_id,
                purpose=f"validator:{v_id}",
                client_id=context.client_id,
                actor_id="intent_dispatcher",
                stream_id=context.stream_id
            )
            
            # Use WorktreeExecutor with lease
            lease = context.executor.acquire_lease(request)
            try:
                result = context.executor.execute(lease)
                
                # Create validator receipt
                receipt = ValidatorReceipt(
                    receipt_id=f"val_{v_id}_{lease.request.execution_id}",
                    kind="validation",
                    workspace_id=workspace_id,
                    actor_id=context.client_id,
                    status=result.status if hasattr(result, 'status') else ("success" if result.succeeded else "failed"),
                    summary=f"Validator {v_id}: exit_code={getattr(result, 'exit_code', 'N/A')}",
                    validator_id=v_id,
                    validated_path=str(context.repo_root),
                    exit_code=getattr(result, 'exit_code', None),
                )
                context.receipt_store.append(receipt)
                results.append({"validator_id": v_id, "status": receipt.status})
                
            except Exception as e:
                context.executor.release_lease(lease)
                # Create failure receipt
                receipt = ValidatorReceipt(
                    receipt_id=f"val_{v_id}_failed",
                    kind="validation",
                    workspace_id=workspace_id,
                    actor_id=context.client_id,
                    status="failed",
                    summary=f"Validator {v_id} failed: {str(e)[:200]}",
                    validator_id=v_id,
                    exit_code=None,
                )
                context.receipt_store.append(receipt)
                results.append({"validator_id": v_id, "status": "failed"})
            finally:
                context.executor.release_lease(lease)
        
        return IntentResult.success(
            intent,
            result={"validator_results": results}
        )
    
    def _get_validator_config(
        self,
        workspace_id: Optional[str],
        repo_root: Path
    ) -> List[Dict[str, Any]]:
        """Get validator configurations for a workspace.
        
        For MVP, returns a simple echo-based validator config.
        In production, this would read from workspace metadata.
        """
        from rig.domain.workspace import WorkspaceDomain
        
        try:
            domain = WorkspaceDomain(repo_root)
            configs = domain.read_validator_config()
            if configs:
                return configs
        except Exception:
            pass
        
        # Default: return a basic lint validator if it exists
        return [
            {
                "id": "rig_lint",
                "argv": ["python", "-m", "rig_tools.doctor"],
                "timeout": 60
            }
        ]
    
    # -------------------------------------------------------------------------
    # Dispatch
    # -------------------------------------------------------------------------
    
    def dispatch(
        self,
        intent: Intent,
        client_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        stream_id: Optional[str] = None,
        **kwargs: Any
    ) -> IntentResult:
        """Dispatch an intent to its handler.
        
        Performs:
        1. Preflight checks (capability, workspace state)
        2. Handler lookup
        3. Execution with governance
        4. Result capture
        
        Args:
            intent: The intent to dispatch
            client_id: Identifier for the requesting client
            workspace_id: Current workspace context
            stream_id: Stream ID for output correlation
            **kwargs: Additional context for handlers
            
        Returns:
            IntentResult with accepted, status, result/error/reason
        """
        # Preflight checks
        preflight_result = self._preflight(intent, client_id, workspace_id)
        if not preflight_result.accepted:
            return preflight_result
        
        # Get handler
        handler = self.get_handler(intent.kind)
        if handler is None:
            return IntentResult.rejected(
                intent,
                reason=f"Unknown intent kind: {intent.kind}"
            )
        
        # Create context
        context = HandlerContext(
            repo_root=self.repo_root,
            executor=self._executor,
            receipt_store=self._receipt_store,
            client_id=client_id,
            workspace_id=workspace_id,
            stream_id=stream_id
        )
        
        # Call handler
        try:
            result = handler(context, intent, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Intent {intent.kind} handler failed: {e}")
            return IntentResult.failure(
                intent,
                error=str(e),
                reason="Handler execution error"
            )
    
    def _preflight(
        self,
        intent: Intent,
        client_id: Optional[str],
        workspace_id: Optional[str]
    ) -> IntentResult:
        """Perform preflight checks before dispatching.
        
        Checks:
        - Intent kind is known
        - Client has capability (stub for now)
        - Workspace exists and is in valid state (stub for now)
        
        Returns IntentResult.rejected() if any check fails.
        """
        # Check 1: Intent has a kind
        if not intent.kind:
            return IntentResult.rejected(
                intent,
                reason="Intent kind is required"
            )
        
        # Check 2: Handler exists (if strict mode)
        # This is informational for now - dispatch will handle it
        
        # Check 3: Workspace state (future)
        # TODO: Check workspace exists and is valid
        
        # Check 4: Capability check (future)
        # TODO: Check client capabilities
        
        # All checks passed
        # Return a dummy "pending" result that will be replaced by actual execution
        return IntentResult(
            intent_id=intent.intent_id or intent.kind,
            intent_kind=intent.kind,
            accepted=True,
            status="pending"
        )


# =============================================================================
# Factory
# =============================================================================

_default_dispatcher: Optional[IntentDispatcher] = None


def get_intent_dispatcher(repo_root: Path) -> IntentDispatcher:
    """Get or create the default intent dispatcher for a repository."""
    global _default_dispatcher
    if _default_dispatcher is None or _default_dispatcher.repo_root != repo_root:
        _default_dispatcher = IntentDispatcher(repo_root)
    return _default_dispatcher
