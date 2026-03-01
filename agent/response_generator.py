"""Response generator — LLM-based reply drafting with KB context.

Uses multi-message prompt: system (ERIS guidelines) + user (KB chunks + ticket data).
Post-processing: disclaimer for low-confidence, greeting/signature enforcement.
"""

from __future__ import annotations

import logging
from typing import Any

from agent.kb_lookup import KBMatch
from agent.llm_client import chat_completion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

RESPONSE_SYSTEM_PROMPT = """\
Ты — сотрудник службы технической поддержки компании ЭРИС \
(https://eriskip.com). Компания производит газоанализаторы, \
датчики газа и системы газового контроля.

Правила ответа:
1. Обращайся на «Вы», будь вежлив и профессионален
2. Используй информацию ТОЛЬКО из предоставленного контекста
3. Если контекста недостаточно — предложи позвонить в техподдержку: \
   +7 (3412) 56-12-52 или написать на support@eriskip.com
4. Упоминай конкретные модели приборов из запроса клиента
5. При упоминании документации давай ссылку на https://eriskip.com
6. НЕ выдумывай технические характеристики
7. Структурируй ответ: приветствие → основная часть → подпись
8. Подпись: «С уважением, Служба технической поддержки ЭРИС»
9. При негативной тональности — выразить сочувствие/извинение
10. Ответ на русском языке
"""


def _build_user_prompt(
    kb_matches: list[KBMatch],
    *,
    email_from: str,
    subject: str,
    body: str,
    category: str,
    sentiment: str,
    fio: str | None = None,
    organization: str | None = None,
    device_type: str | None = None,
    serial_numbers: list[str] | None = None,
) -> str:
    """Compose the user prompt with KB context and ticket data."""
    # KB context block
    kb_lines: list[str] = []
    for i, m in enumerate(kb_matches, 1):
        kb_lines.append(
            f"[{i}] (source: {m.source_type}, score: {m.score:.2f})\n{m.content}"
        )
    kb_block = "\n\n".join(kb_lines) if kb_lines else "(база знаний не содержит релевантной информации)"

    serials_str = ", ".join(serial_numbers) if serial_numbers else "не указаны"

    return (
        f"Контекст из базы знаний:\n{kb_block}\n\n"
        f"Данные письма:\n"
        f"- От: {fio or 'Не указано'} ({email_from})\n"
        f"- Организация: {organization or 'Не указано'}\n"
        f"- Категория: {category}\n"
        f"- Тональность: {sentiment}\n"
        f"- Приборы: {device_type or 'Не указано'}, зав.№ {serials_str}\n"
        f"- Тема: {subject}\n\n"
        f"Текст обращения:\n{body}\n\n"
        f"Составь ответ на это обращение."
    )


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

_DISCLAIMER = (
    "\n\n⚠️ Данный ответ подготовлен автоматически и может "
    "потребовать проверки специалистом."
)

_SIGNATURE = "\n\nС уважением,\nСлужба технической поддержки ЭРИС"


def _postprocess(text: str, max_kb_score: float) -> str:
    """Ensure greeting, signature, and add disclaimer if KB score is low."""
    # Strip leading/trailing whitespace
    text = text.strip()

    # Add disclaimer if confidence is low
    if max_kb_score < 0.5:
        if "автоматически" not in text:
            text += _DISCLAIMER

    # Ensure signature
    if "С уважением" not in text:
        text += _SIGNATURE

    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_response(
    email_from: str,
    subject: str,
    category: str,
    entities: dict[str, Any],
    kb_matches: list[KBMatch] | None = None,
    body: str = "",
    sentiment: str = "нейтраль",
) -> str:
    """Generate a response email body using LLM + KB context.

    Parameters
    ----------
    kb_matches : list of top-3 KBMatch from RAG pipeline
    """
    if kb_matches is None:
        kb_matches = []

    max_score = max((m.score for m in kb_matches), default=0.0)

    user_prompt = _build_user_prompt(
        kb_matches,
        email_from=email_from,
        subject=subject,
        body=body,
        category=category,
        sentiment=sentiment,
        fio=entities.get("fio"),
        organization=entities.get("organization"),
        device_type=entities.get("device_type"),
        serial_numbers=entities.get("serial_numbers"),
    )

    logger.debug("Response prompt:\n%s", user_prompt)

    try:
        result = await chat_completion([
            {"role": "system", "content": RESPONSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        raw = result.choices[0].message.content
        response = _postprocess(raw, max_score)
        logger.info(
            "Generated response: %d chars, max_kb_score=%.2f, kb_chunks=%d",
            len(response), max_score, len(kb_matches),
        )
        return response

    except Exception:
        logger.exception("Response generation failed")
        fallback = (
            "Здравствуйте!\n\n"
            "Спасибо за ваше обращение. Мы получили ваш запрос и работаем над ним. "
            "Наш специалист свяжется с вами в ближайшее время.\n\n"
            "Вы также можете связаться с нами по телефону: +7 (3412) 56-12-52 "
            "или по электронной почте: support@eriskip.com"
        )
        return fallback + _DISCLAIMER + _SIGNATURE
