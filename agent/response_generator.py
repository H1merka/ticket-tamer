"""Response generator — drafts a reply based on KB match and classification."""

from __future__ import annotations

from agent.kb_lookup import KBMatch


async def generate_response(
    email_from: str,
    subject: str,
    category: str,
    entities: dict,
    kb_match: KBMatch | None,
) -> str:
    """Generate a response email body.

    Current implementation uses simple templates.
    Will be enhanced with LLM-based generation on hackathon if needed.
    """
    greeting = "Здравствуйте!"
    if kb_match:
        body = kb_match.answer
    else:
        body = (
            "Спасибо за ваше обращение. Мы получили ваш запрос и работаем над ним. "
            "Наш специалист свяжется с вами в ближайшее время."
        )

    return f"{greeting}\n\n{body}\n\nС уважением,\nСлужба технической поддержки"
