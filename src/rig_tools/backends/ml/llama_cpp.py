"""
LlamaCpp Backend implementation for rig_tools.

Provides ML operations using the llama-cpp-python library for
cross-platform LLM inference.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from rig_tools.core import get_tracer, trace_context, add_breadcrumbs
from rig_tools.backends.ml.base import MLBackendImpl, MLBackendError

logger = logging.getLogger(__name__)


class LlamaCppBackend(MLBackendImpl):
    """
    LlamaCpp-based ML backend.
    
    This backend uses the llama-cpp-python library for LLM inference,
    supporting GGUF model format on CPU and GPU across platforms.
    """
    
    backend_id = "llama_cpp"
    display_name = "LlamaCpp"
    priority = 5  # Fallback backend when MLX is not available
    
    def __init__(self, **config: Any):
        """
        Initialize LlamaCpp backend.
        
        Args:
            model_path: Default model path
            n_gpu_layers: Number of layers to offload to GPU
            **config: Additional llama-cpp configuration
        """
        super().__init__(**config)
        self._model_path = config.get("model_path")
        self._n_gpu_layers = config.get("n_gpu_layers", -1)  # -1 = auto
        self._llama = None
    
    def _check_available(self) -> bool:
        """Check if llama-cpp-python is available."""
        try:
            import llama_cpp
            return True
        except ImportError:
            return False
    
    def _configure(self, **config: Any) -> None:
        """Configure LlamaCpp backend."""
        self._model_path = config.get("model_path", self._model_path)
        self._n_gpu_layers = config.get("n_gpu_layers", self._n_gpu_layers)
    
    def status(self) -> dict[str, Any]:
        """Get LlamaCpp backend status."""
        try:
            import llama_cpp
            
            return {
                "backend": self.backend_id,
                "available": True,
                "library_version": llama_cpp.__version__,
                "loaded_model": self._llama is not None,
                "n_gpu_layers": self._n_gpu_layers,
            }
        except ImportError:
            return {
                "backend": self.backend_id,
                "available": False,
                "error": "llama-cpp-python not installed",
            }
        except Exception as e:
            return {
                "backend": self.backend_id,
                "available": False,
                "error": str(e),
            }
    
    def _ensure_model_loaded(
        self,
        model: str | None = None,
        model_path: Path | str | None = None,
    ) -> None:
        """Ensure the required model is loaded."""
        if self._llama is not None:
            return
        
        load_path = model_path or self._model_path or model
        if not load_path:
            raise MLBackendError(
                "No model specified and no default model configured",
                code="LLAMA_CPP_NO_MODEL",
            )
        
        with trace_context("llama_cpp.load_model", category="ml", model=str(load_path)):
            self._load_model_internal(load_path)
            add_breadcrumbs("Model loaded successfully", model=str(load_path))
    
    def _load_model_internal(self, model_path: str | Path) -> None:
        """Internal model loading logic."""
        try:
            import llama_cpp
            
            model_path = Path(model_path)
            logger.info(f"Loading LlamaCpp model from {model_path}")
            
            start_time = time.time()
            
            # Load model
            self._llama = llama_cpp.Llama(
                model_path=str(model_path),
                n_gpu_layers=self._n_gpu_layers,
                n_ctx=4096,  # Context size
                verbose=False,
            )
            
            load_time = time.time() - start_time
            logger.info(f"LlamaCpp model loaded in {load_time:.2f}s")
            
        except ImportError as e:
            raise MLBackendError(
                f"llama-cpp-python not installed: {e}",
                code="LLAMA_CPP_IMPORT_ERROR",
            ) from e
        except Exception as e:
            raise MLBackendError(
                f"Failed to load LlamaCpp model: {e}",
                code="LLAMA_CPP_LOAD_ERROR",
                context={"model_path": str(model_path)},
            ) from e
    
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
        """Generate text using LlamaCpp."""
        with trace_context(
            "llama_cpp.generate",
            category="ml",
            backend=self.backend_id,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            self._ensure_model_loaded(model=model, model_path=model_path)
            
            if self._llama is None:
                raise MLBackendError("Model not loaded", code="LLAMA_CPP_MODEL_NOT_LOADED")
            
            try:
                # Prepare generation parameters
                params = {
                    "temperature": temperature,
                    "max_tokens": max_tokens or 512,
                    "stop": ["\n"],
                    **generate_kwargs,
                }
                
                start_time = time.time()
                response = self._llama(prompt, **params)
                generation_time = time.time() - start_time
                
                add_breadcrumbs(
                    "Generation completed",
                    tokens_generated=len(response.get("choices", [[]])[0] or []),
                    time_seconds=generation_time,
                )
                
                # Extract text from response
                choices = response.get("choices", [[]])
                if choices and choices[0]:
                    return choices[0].get("text", "")
                return ""
                
            except Exception as e:
                raise MLBackendError(
                    f"LlamaCpp generation failed: {e}",
                    code="LLAMA_CPP_GENERATE_ERROR",
                ) from e
    
    def embed(
        self,
        text: str,
        *,
        model: str | None = None,
        model_path: Path | str | None = None,
        **kwargs: Any,
    ) -> list[float]:
        """Generate embeddings using LlamaCpp."""
        with trace_context("llama_cpp.embed", category="ml"):
            self._ensure_model_loaded(model=model, model_path=model_path)
            
            if self._llama is None:
                raise MLBackendError("Model not loaded", code="LLAMA_CPP_MODEL_NOT_LOADED")
            
            try:
                # Use the backend's embedding capability if available
                if hasattr(self._llama, "embed"):
                    embedding = self._llama.embed(text)
                    return embedding.tolist()
                else:
                    # Fallback: use a dedicated embedding model
                    raise MLBackendError(
                        "Embedding not supported by this LlamaCpp model",
                        code="LLAMA_CPP_EMBEDDINGS_UNSUPPORTED",
                    )
            except Exception as e:
                raise MLBackendError(
                    f"LlamaCpp embedding failed: {e}",
                    code="LLAMA_CPP_EMBEDDINGS_ERROR",
                ) from e
    
    def list_models(self) -> list[dict[str, Any]]:
        """List available LlamaCpp models."""
        models = []
        
        # Check for common model paths
        for model_dir in [
            Path.home() / ".llama" / "models",
            Path("/usr/local/share/llama/models"),
            Path("./models"),
        ]:
            if model_dir.exists():
                for model_path in model_dir.glob("*.gguf"):
                    models.append({
                        "name": model_path.name,
                        "path": str(model_path),
                        "type": "gguf",
                    })
        
        return models
    
    def load_model(
        self,
        model: str | None = None,
        model_path: Path | str | None = None,
        **kwargs: Any,
    ) -> None:
        """Load a specific model."""
        self._ensure_model_loaded(model=model, model_path=model_path)
    
    def unload_model(self, model: str | None = None) -> None:
        """Unload the current model."""
        self._llama = None
        logger.info("LlamaCpp model unloaded")
