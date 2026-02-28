"""Named-entity extraction from email text via LLM JSON-mode.

Extracts ERIS-specific fields: FIO, organization, phone, serial numbers,
device type and a brief description.
"""

from __future__ import annotations

import logging
import re

from agent.llm_client import chat_completion_json

logger = logging.getLogger(__name__)

NER_SYSTEM_PROMPT = """\
Извлеки из текста письма следующую информацию.
Если какое-то поле не найдено — поставь null.

Верни ТОЛЬКО JSON:
{
  "fio": "Фамилия Имя Отчество",
  "organization": "Название организации",
  "phone": "+7 (XXX) XXX-XX-XX",
  "serial_numbers": ["12345", "67890"],
  "device_type": "Модель прибора",
  "description": "Краткое описание проблемы (1-2 предложения)"
}

Правила:
- ФИО: ищи в подписи, теле письма, обращении
- Телефон: нормализуй в формат +7 (XXX) XXX-XX-XX
- Заводские номера: могут быть в формате «зав.№», «s/n», «серийный»
- Тип прибора: ищи названия из каталога ЭРИС \
(СЕНСОН, ДГС, Газконтроль, СОВА и т.д.)
- Описание: суть проблемы кратко, без пересказа всего письма
"""

PHONE_PATTERN = re.compile(
    r"^\+7\s?\(\d{3}\)\s?\d{3}-\d{2}-\d{2}$"
)

# Known ERIS device families for normalisation
DEVICE_FAMILIES = [
    "СЕНСОН", "ДГС", "Газконтроль", "СОВА", "ЭРИС",
]


def _validate_phone(phone: str | None) -> str | None:
    """Return phone if it matches the canonical format, else None."""
    if not phone:
        return None
    phone = phone.strip()
    if PHONE_PATTERN.match(phone):
        return phone
    # Try basic normalisation: digits only → format
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        d = digits if digits[0] == "7" else "7" + digits[1:]
        return f"+{d[0]} ({d[1:4]}) {d[4:7]}-{d[7:9]}-{d[9:11]}"
    return phone  # return as-is if can't normalise


def _validate_fio(fio: str | None) -> str | None:
    if not fio:
        return None
    parts = fio.strip().split()
    if len(parts) < 2:
        return None
    return fio.strip()


def _dedupe_serials(serials: list | None) -> list[str]:
    if not serials:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for s in serials:
        upper = str(s).strip().upper()
        if upper and upper not in seen:
            seen.add(upper)
            result.append(upper)
    return result


async def extract_entities(text: str) -> dict:
    """Extract structured entities from email body text using LLM.

    Returns a dict with keys: fio, organization, phone, serial_numbers,
    device_type, description.
    """
    try:
        data = await chat_completion_json([
            {"role": "system", "content": NER_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ])

        return {
            "fio": _validate_fio(data.get("fio")),
            "organization": data.get("organization") or None,
            "phone": _validate_phone(data.get("phone")),
            "serial_numbers": _dedupe_serials(data.get("serial_numbers")),
            "device_type": data.get("device_type") or None,
            "description": data.get("description") or None,
        }

    except Exception as exc:
        logger.error("Entity extraction failed: %s", exc, exc_info=True)
        return {
            "fio": None,
            "organization": None,
            "phone": None,
            "serial_numbers": [],
            "device_type": None,
            "description": None,
        }
