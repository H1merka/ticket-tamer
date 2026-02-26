"""Named-entity extraction from email text."""

from __future__ import annotations


async def extract_entities(text: str) -> dict:
    """Extract structured entities (order id, product, contacts, etc.).

    Returns a dict with entity_type → value mappings.
    Placeholder implementation — to be filled with NER model on hackathon.
    """
    # TODO: use agent.models.loader.registry.ner
    return {}
