"""Singleton loader for ML models.

All heavy models (classifier, NER, sentence-transformer) are loaded once
at application startup and reused for every request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelRegistry:
    """Holds references to loaded ML models."""

    classifier: Any = field(default=None)
    ner: Any = field(default=None)
    embedder: Any = field(default=None)

    @property
    def is_loaded(self) -> bool:
        return self.classifier is not None


# Global singleton — populated on startup via `load_models()`.
registry = ModelRegistry()


async def load_models(cache_dir: str = "./model_cache") -> None:
    """Load all ML models into the global registry.

    Called once from FastAPI lifespan.  Implementation will be filled in
    during the hackathon once the exact model names are finalised.
    """
    # TODO: load classifier pipeline (zero-shot or fine-tuned)
    # from transformers import pipeline
    # registry.classifier = pipeline(
    #     "zero-shot-classification",
    #     model="cointegrated/rubert-tiny2",
    #     device=-1,
    # )

    # TODO: load NER model
    # TODO: load sentence-transformer for KB embeddings
    pass


async def unload_models() -> None:
    """Release model references on shutdown."""
    registry.classifier = None
    registry.ner = None
    registry.embedder = None
