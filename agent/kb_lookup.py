"""Knowledge-base lookup — two-phase vector search + priority boost + LLM reranking.

Pipeline:
  1. Build query from description + device_type
  2. Embed query via RouterAI
  3. Phase A: vector search official_docs (top-10)
  4. Phase B: vector search support_history (top-10, respect expiry)
  5. Merge with priority boost (official_docs × 1.5)
  6. Filter cosine < 0.3, deduplicate by article_id
  7. LLM reranking (pointwise 0-10) → top-3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agent.llm_client import chat_completion_json, embed_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

COSINE_THRESHOLD = 0.3
PRIORITY_WEIGHTS = {"official_docs": 1.5, "support_history": 1.0}


@dataclass
class KBMatch:
    article_id: int
    content: str
    score: float
    source_type: str = "official_docs"
    chunk_id: int = 0
    priority: int = 1
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Step 1-2: query → embedding
# ---------------------------------------------------------------------------

def build_query(description: str | None, device_type: str | None) -> str:
    """Combine NER fields into a single search query string."""
    parts = [p for p in (description, device_type) if p]
    return " ".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Step 3: two-phase vector search
# ---------------------------------------------------------------------------

_VECTOR_SQL = """
SELECT
    kc.id          AS chunk_id,
    kc.article_id,
    kc.content,
    kc.source_type,
    kc.priority,
    kc.metadata    AS meta,
    1 - (kc.embedding <=> :qvec ::vector) AS cosine_score
FROM kb_chunks kc
WHERE kc.source_type = :src
  {expiry_filter}
ORDER BY kc.embedding <=> :qvec ::vector
LIMIT :lim
"""


async def _phase_search(
    db: AsyncSession,
    query_vector: list[float],
    source_type: str,
    limit: int = 10,
) -> list[KBMatch]:
    """Run a single-phase cosine search against kb_chunks."""
    expiry = ""
    if source_type == "support_history":
        expiry = "AND (kc.expires_at IS NULL OR kc.expires_at > now())"

    sql = _VECTOR_SQL.format(expiry_filter=expiry)
    vec_literal = "[" + ",".join(str(v) for v in query_vector) + "]"

    result = await db.execute(
        text(sql),
        {"qvec": vec_literal, "src": source_type, "lim": limit},
    )
    rows = result.fetchall()

    matches: list[KBMatch] = []
    for r in rows:
        matches.append(
            KBMatch(
                chunk_id=r.chunk_id,
                article_id=r.article_id,
                content=r.content,
                source_type=r.source_type,
                priority=r.priority,
                score=float(r.cosine_score),
                metadata=r.meta or {},
            )
        )
    return matches


# ---------------------------------------------------------------------------
# Step 4-5: merge, boost, filter, dedup
# ---------------------------------------------------------------------------

def _merge_and_boost(
    official: list[KBMatch],
    history: list[KBMatch],
) -> list[KBMatch]:
    """Merge two phases, apply priority weights, filter, deduplicate."""
    combined: list[KBMatch] = []
    for m in official + history:
        weight = PRIORITY_WEIGHTS.get(m.source_type, 1.0)
        m.score = m.score * weight
        if m.score >= COSINE_THRESHOLD:
            combined.append(m)

    # Sort descending by boosted score
    combined.sort(key=lambda m: m.score, reverse=True)

    # Deduplicate by article_id — keep highest score per article.
    # Chunks without an article_id (standalone) are kept individually.
    seen_articles: set[int] = set()
    deduped: list[KBMatch] = []
    for m in combined:
        if m.article_id is None:
            deduped.append(m)
        elif m.article_id not in seen_articles:
            seen_articles.add(m.article_id)
            deduped.append(m)

    return deduped[:10]


# ---------------------------------------------------------------------------
# Step 6: LLM reranking
# ---------------------------------------------------------------------------

_RERANK_SYSTEM = """\
Ты — эксперт по оценке релевантности документов.
Оцени каждый фрагмент по шкале от 0 до 10, где:
  10 = идеально релевантен запросу
  0 = абсолютно нерелевантен

Учитывай source_type:
  - official_docs = официальная документация (более авторитетная)
  - support_history = история обращений (менее авторитетная)

Верни ТОЛЬКО JSON-массив:
[{"chunk_id": 1, "score": 9.2}, ...]
"""


async def _llm_rerank(query: str, candidates: list[KBMatch]) -> list[KBMatch]:
    """Use LLM to pointwise-score each candidate, return top-3."""
    if not candidates:
        return []

    # Build user prompt
    fragments: list[str] = []
    for i, m in enumerate(candidates):
        truncated = m.content[:200]
        fragments.append(
            f"[{m.chunk_id}] source={m.source_type}, priority={m.priority}\n{truncated}"
        )

    user_prompt = f"Запрос: {query}\n\nФрагменты:\n" + "\n\n".join(fragments)

    try:
        scores = await chat_completion_json([
            {"role": "system", "content": _RERANK_SYSTEM},
            {"role": "user", "content": user_prompt},
        ])
        # Expect list[{"chunk_id": int, "score": float}]
        if not isinstance(scores, list):
            logger.warning("LLM rerank returned non-list; skipping rerank")
            return candidates[:3]

        score_map: dict[int, float] = {}
        for item in scores:
            cid = item.get("chunk_id")
            sc = item.get("score", 0)
            if cid is not None:
                score_map[int(cid)] = float(sc)

        for m in candidates:
            if m.chunk_id in score_map:
                m.score = score_map[m.chunk_id]

        candidates.sort(key=lambda m: m.score, reverse=True)
        return candidates[:3]

    except Exception:
        logger.exception("LLM rerank failed; returning top-3 by vector score")
        return candidates[:3]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def find_best_matches(
    db: AsyncSession,
    description: str | None = None,
    device_type: str | None = None,
    body: str | None = None,
) -> list[KBMatch]:
    """Full RAG retrieval pipeline. Returns up to 3 KBMatch objects.

    Parameters
    ----------
    description : extracted description from NER
    device_type : extracted device type from NER
    body : raw email body (fallback if description is empty)
    """
    query = build_query(description, device_type) or (body or "")
    if not query.strip():
        return []

    # Embed query
    query_vector = await embed_text(query)

    # Two-phase search
    official = await _phase_search(db, query_vector, "official_docs", limit=10)
    history = await _phase_search(db, query_vector, "support_history", limit=10)

    logger.info("Vector search: %d official, %d history hits", len(official), len(history))

    # Merge + boost + filter + dedup
    candidates = _merge_and_boost(official, history)
    if not candidates:
        return []

    # LLM reranking → top 3
    top3 = await _llm_rerank(query, candidates)
    return top3
