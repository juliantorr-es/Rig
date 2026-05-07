"""
MLX Backend implementation for rig_tools.

Provides ML operations using the MLX framework on Apple Silicon.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from rig_tools.core import get_tracer, trace_context, add_breadcrumbs
from rig_tools.backends.ml.base import MLBackendImpl, MLBackendError

logger = logging.getLogger(__name__)


class MLXBackend(MLBackendImpl):
    """
    MLX-based ML backend for Apple Silicon.
    
    This backend uses the mlx library for efficient LLM inference
    on Apple M1/M2/M3 chips.
    """
    
    backend_id = "mlx"
    display_name = "MLX (Apple Silicon)"
    priority = 10  # Preferred backend on macOS Apple Silicon
    
    def __init__(self, **config: Any):
        """
        Initialize MLX backend.
        
        Args:
            device: Device to use (auto, cpu, gpu)
            model_path: Default model path
            **config: Additional MLX configuration
        """
        super().__init__(**config)
        self._device = config.get("device", "auto")
        self._model_path = config.get("model_path")
        self._model = None
        self._tokenizer = None
    
    def _check_available(self) -> bool:
        """Check if MLX is available and GPU is accessible."""
        try:
            import mlx
            import mlx.core as mx
            # Try to get device info
            devices = mx.metal().devices
            return len(devices) > 0
        except ImportError:
            return False
        except Exception as e:
            logger.debug(f"MLX availability check failed: {e}")
            return False
    
    def _configure(self, **config: Any) -> None:
        """Configure MLX backend."""
        self._device = config.get("device", self._device)
        self._model_path = config.get("model_path", self._model_path)
    
    def status(self) -> dict[str, Any]:
        """Get MLX backend status."""
        try:
            import mlx
            import mlx.core as mx
            
            devices = mx.metal.get_devices()
            device_info = {
                "device_count": len(devices),
                "devices": [str(d) for d in devices],
            }
            
            return {
                "backend": self.backend_id,
                "available": True,
                "library_version": mlx.__version__,
                "device_info": device_info,
                "loaded_model": self._model is not None,
            }
        except ImportError:
            return {
                "backend": self.backend_id,
                "available": False,
                "error": "MLX not installed",
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
        if self._model is not None:
            return
        
        load_path = model_path or self._model_path or model
        if not load_path:
            raise MLBackendError(
                "No model specified and no default model configured",
                code="MLX_NO_MODEL",
            )
        
        with trace_context("mlx.load_model", category="ml", model=str(load_path)):
            self._load_model_internal(load_path)
            add_breadcrumbs("Model loaded successfully", model=str(load_path))
    
    def _load_model_internal(self, model_path: str | Path) -> None:
        """Internal model loading logic."""
        try:
            import mlx
            import mlx.core as mx
            from mlx_lm import load, generate
            
            model_path = Path(model_path)
            logger.info(f"Loading MLX model from {model_path}")
            
            start_time = time.time()
            
            # Load model and tokenizer
            self._model, self._tokenizer = load(str(model_path))
            
            # Move to GPU if available
            if self._device != "cpu":
                self._model = mx.eval(self._model)
            
            load_time = time.time() - start_time
            logger.info(f"MLX model loaded in {load_time:.2f}s")
            
        except ImportError as e:
            raise MLBackendError(
                f"Required MLX dependencies not installed: {e}",
                code="MLX_IMPORT_ERROR",
            ) from e
        except Exception as e:
            raise MLBackendError(
                f"Failed to load MLX model: {e}",
                code="MLX_LOAD_ERROR",
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
        """Generate text using MLX."""
        with trace_context(
            "mlx.generate",
            category="ml",
            backend=self.backend_id,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            self._ensure_model_loaded(model=model, model_path=model_path)
            
            if self._model is None:
                raise MLBackendError("Model not loaded", code="MLX_MODEL_NOT_LOADED")
            
            try:
                from mlx_lm import generate
                
                # Prepare generation parameters
                params = {
                    "temperature": temperature,
                    "max_tokens": max_tokens or 512,
                    **generate_kwargs,
                }
                
                start_time = time.time()
                response = generate(self._model, self._tokenizer, prompt=prompt, **params)
                generation_time = time.time() - start_time
                
                add_breadcrumbs(
                    "Generation completed",
                    tokens_generated=len(response),
                    time_seconds=generation_time,
                )
                
                return response
                
            except ImportError as e:
                raise MLBackendError(
                    f"MLX generation dependencies missing: {e}",
                    code="MLX_GENERATE_IMPORT_ERROR",
                ) from e
            except Exception as e:
                raise MLBackendError(
                    f"MLX generation failed: {e}",
                    code="MLX_GENERATE_ERROR",
                ) from e
    
    def embed(
        self,
        text: str,
        *,
        model: str | None = None,
        model_path: Path | str | None = None,
        **kwargs: Any,
    ) -> list[float]:
        """Generate embeddings using MLX."""
        raise MLBackendError(
            "MLX backend does not support embeddings yet",
            code="MLX_EMBEDDINGS_UNSUPPORTED",
        )
    
    def list_models(self) -> list[dict[str, Any]]:
        """List available MLX models."""
        # Check for common model paths
        models = []
        
        # Check default model directories
        for model_dir in [
            Path.home() / ".mlx" / "models",
            Path("/usr/local/share/mlx/models"),
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
        self._model = None
        self._tokenizer = None
        logger.info("MLX model unloaded")
