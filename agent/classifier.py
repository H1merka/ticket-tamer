"""Email classifier — determines category, priority, and sentiment via LLM.

Uses a single RouterAI Chat Completion call with JSON-mode to return
category, sentiment and confidence in one round-trip.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from agent.llm_client import chat_completion_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Ты — AI-ассистент службы технической поддержки компании ЭРИС \
(производство газоанализаторов).

Проанализируй письмо клиента и определи:
1. Категорию обращения — ОДНУ из:
   - "неисправность" — поломка, отказ, ошибка, некорректные показания
   - "калибровка" — поверка, настройка, периодическое ТО
   - "запрос_документации" — руководства, сертификаты, спецификации
   - "запрос_доступа" — пароли, лицензии, firmware, ПО (DGS BLE и т.д.)
   - "прочее" — коммерческие запросы, отзывы, прочее

2. Эмоциональный окрас — ОДИН из:
   - "позитив" — благодарность, удовлетворение
   - "нейтраль" — стандартный деловой запрос
   - "негатив" — жалоба, претензия, раздражение

3. Уверенность (confidence) — число от 0.0 до 1.0

Верни ТОЛЬКО JSON без пояснений:
{"category": "...", "sentiment": "...", "confidence": 0.95}
"""

VALID_CATEGORIES = {
    "неисправность",
    "калибровка",
    "запрос_документации",
    "запрос_доступа",
    "прочее",
}

VALID_SENTIMENTS = {"позитив", "нейтраль", "негатив"}

PRIORITY_MAP: dict[str, str] = {
    "неисправность": "high",
    "калибровка": "medium",
    "запрос_документации": "low",
    "запрос_доступа": "medium",
    "прочее": "low",
}


@dataclass
class ClassificationResult:
    category: str          # ERIS category
    priority: str          # low / medium / high / critical
    sentiment: str         # позитив / нейтраль / негатив
    confidence: float      # 0.0 – 1.0


async def classify_email(subject: str, body: str) -> ClassificationResult:
    """Classify an incoming email using LLM JSON-mode.

    Returns category, priority (derived), sentiment and confidence.
    """
    user_content = f"Тема: {subject}\n\nТекст письма:\n{body}"

    try:
        data = await chat_completion_json([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ])

        category = data.get("category", "прочее")
        sentiment = data.get("sentiment", "нейтраль")
        confidence = float(data.get("confidence", 0.0))

        # Validate
        if category not in VALID_CATEGORIES:
            logger.warning("Unknown category '%s', defaulting to 'прочее'", category)
            category = "прочее"
        if sentiment not in VALID_SENTIMENTS:
            logger.warning("Unknown sentiment '%s', defaulting to 'нейтраль'", sentiment)
            sentiment = "нейтраль"
        confidence = max(0.0, min(1.0, confidence))

        # Derive priority
        priority = PRIORITY_MAP.get(category, "low")

        # Escalate on strong negative sentiment
        if sentiment == "негатив" and confidence >= 0.85:
            priority = "high"

        return ClassificationResult(
            category=category,
            priority=priority,
            sentiment=sentiment,
            confidence=confidence,
        )

    except Exception as exc:
        logger.error("Classification failed: %s", exc, exc_info=True)
        return ClassificationResult(
            category="прочее",
            priority="medium",
            sentiment="нейтраль",
            confidence=0.0,
        )
