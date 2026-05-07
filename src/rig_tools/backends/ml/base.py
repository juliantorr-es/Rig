"""
Base ML Backend implementation for rig_tools.

This is the implementation-layer abstract base that concrete ML backends
inherits from. It provides common functionality and enforces the interface
that all ML backends must implement.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from rig_tools.core import get_tracer, trace_context
from rig_tools.core.errors import RigError, RigNotFoundError

logger = logging.getLogger(__name__)


class MLBackendError(RigError):
    """Base error for ML backend operations."""
    pass


class MLBackendNotFoundError(RigNotFoundError):
    """Raised when a requested ML backend is not available."""
    def __init__(self, backend_id: str):
        super().__init__(
            f"ML backend '{backend_id}' not found or not configured",
            code="ML_BACKEND_NOT_FOUND",
            resource_type="ML backend",
            resource_id=backend_id,
        )


class MLBackendConfigError(RigError):
    """Raised when ML backend configuration is invalid."""
    pass


class MLBackendImpl(ABC):
    """
    Abstract base class for ML backend implementations.
    
    All concrete ML backends (MLX, LlamaCpp, etc.) must inherit from
    this class and implement the required methods.
    
    This is the implementation-layer contract, while MLBackend (Protocol)
    in the domain layer is the public interface.
    """
    
    backend_id: str = ""  # Unique identifier for this backend type
    display_name: str = ""  # Human-readable name
    priority: int = 0  # Priority for backend selection (higher = preferred)
    
    def __init__(self, **config: Any):
        """
        Initialize the backend with configuration.
        
        Args:
            **config: Backend-specific configuration options
        """
        self.config = config
        self._tracer = get_tracer("ml_backend")
        self._configure(**config)
    
    def _configure(self, **config: Any) -> None:
        """
        Configure the backend with provided options.
        
        Override this in subclasses to handle backend-specific config.
        """
        pass
    
    @property
    def is_available(self) -> bool:
        """Check if the backend is available (installed and configured)."""
        try:
            return self._check_available()
        except Exception:
            return False
    
    def _check_available(self) -> bool:
        """Internal check for backend availability. Override in subclasses."""
        return True
    
    @abstractmethod
    def status(self) -> dict[str, Any]:
        """
        Get backend status information.
        
        Returns:
            Dictionary containing backend status (version, device, etc.)
        """
        pass
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        model_path: Path | str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **generate_kwargs: Any,
    ) -> str:
        """
        Generate text from a prompt.
        
        Args:
            prompt: The prompt to generate from
            model: Model identifier
            model_path: Path to model file
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **generate_kwargs: Additional backend-specific options
            
        Returns:
            Generated text
            
        Raises:
            MLBackendError: If generation fails
        """
        pass
    
    def summarize(
        self,
        content: str | Path,
        *,
        model: str | None = None,
        model_path: Path | str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Summarize content using the backend.
        
        Args:
            content: Content to summarize (string or file path)
            model: Model identifier
            model_path: Path to model file
            **kwargs: Additional options
            
        Returns:
            Summary text
        """
        if isinstance(content, Path):
            content = self._read_content(content)
        
        prompt = self._build_summarize_prompt(content)
        return self.generate(prompt, model=model, model_path=model_path, **kwargs)
    
    def _read_content(self, path: Path) -> str:
        """Read content from a file path."""
        return path.read_text(encoding="utf-8", errors="replace")
    
    def _build_summarize_prompt(self, content: str) -> str:
        """Build a summarization prompt. Override for custom prompts."""
        # Truncate content if too long
        max_context = self.config.get("max_context_length", 8000)
        if len(content) > max_context:
            content = content[:max_context] + "... [truncated]"
        
        return f"""Summarize the following content in 2-3 sentences:

{content}

Summary:"""
    
    def embed(
        self,
        text: str,
        *,
        model: str | None = None,
        model_path: Path | str | None = None,
        **kwargs: Any,
    ) -> list[float]:
        """
        Generate embeddings for text.
        
        Args:
            text: Text to embed
            model: Model identifier
            model_path: Path to model file
            **kwargs: Additional options
            
        Returns:
            Embedding vector as list of floats
            
        Raises:
            MLBackendError: If embedding fails
        """
        pass
    
    def list_models(self) -> list[dict[str, Any]]:
        """
        List available models for this backend.
        
        Returns:
            List of model info dictionaries
        """
        return []
    
    def load_model(
        self,
        model: str | None = None,
        model_path: Path | str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Load a model into memory.
        
        Args:
            model: Model identifier
            model_path: Path to model file
            **kwargs: Additional options
        """
        pass
    
    def unload_model(self, model: str | None = None) -> None:
        """Unload a model from memory."""
        pass
    
    def ping(self) -> float:
        """
        Ping the backend to check responsiveness.
        
        Returns:
            Response time in seconds
        """
        with trace_context("backend.ping", category="ml", backend=self.backend_id):
            start = __import__("time").time()
            self.status()
            return __import__("time").time() - start
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.backend_id!r}, available={self.is_available})>"
