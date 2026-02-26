"""Email classifier — determines category, priority, and sentiment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClassificationResult:
    category: str          # e.g. "technical", "billing", "general", "spam"
    priority: str          # low / medium / high / critical
    sentiment: str         # positive / neutral / negative
    confidence: float      # 0.0 – 1.0


# Candidate labels for zero-shot classification (will be tuned on hackathon data)
CATEGORY_LABELS = [
    "техническая проблема",
    "оплата и биллинг",
    "общий вопрос",
    "спам",
]


async def classify_email(subject: str, body: str) -> ClassificationResult:
    """Classify an incoming email.

    Currently returns a placeholder result.  During the hackathon this will
    use the loaded zero-shot / fine-tuned classifier from model registry.
    """
    # TODO: use agent.models.loader.registry.classifier
    return ClassificationResult(
        category="general",
        priority="medium",
        sentiment="neutral",
        confidence=0.0,
    )
