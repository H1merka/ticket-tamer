"""KB cleanup service — rotate expired support_history chunks.

Provides:
  - cleanup_expired_chunks(): delete or count expired chunks
  - extend_chunk_lifetime(): extend expires_at for a specific chunk
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KBChunk

logger = logging.getLogger(__name__)


async def cleanup_expired_chunks(
    db: AsyncSession,
    dry_run: bool = True,
    max_age_days: int | None = None,
) -> int:
    """Delete expired support_history chunks.

    Parameters
    ----------
    dry_run : if True, only count — do not delete.
    max_age_days : if set, delete chunks older than this (by created_at);
                   otherwise use expires_at < now().

    Returns the number of chunks deleted (or would be deleted).
    """
    conditions = [KBChunk.source_type == "support_history", KBChunk.expires_at.isnot(None)]

    if max_age_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        conditions.append(KBChunk.created_at < cutoff)
    else:
        conditions.append(KBChunk.expires_at < func.now())

    if dry_run:
        count_q = select(func.count(KBChunk.id)).where(*conditions)
        result = await db.execute(count_q)
        count = result.scalar() or 0
        logger.info("Cleanup dry-run: %d chunks would be deleted", count)
        return count

    del_q = delete(KBChunk).where(*conditions)
    result = await db.execute(del_q)
    await db.commit()
    deleted = result.rowcount  # type: ignore[union-attr]
    logger.info("Cleanup: deleted %d expired chunks", deleted)
    return deleted


async def extend_chunk_lifetime(
    db: AsyncSession,
    chunk_id: int,
    extend_days: int = 90,
) -> KBChunk | None:
    """Extend the expires_at of a support_history chunk.

    Returns the updated chunk, or None if not found / wrong source_type.
    """
    chunk = await db.get(KBChunk, chunk_id)
    if chunk is None:
        return None
    if chunk.source_type != "support_history":
        return None

    chunk.expires_at = datetime.now(timezone.utc) + timedelta(days=extend_days)
    await db.commit()
    await db.refresh(chunk)
    logger.info("Extended chunk %d lifetime by %d days", chunk_id, extend_days)
    return chunk
