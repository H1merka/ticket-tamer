"""Analytics service — aggregate ticket data for the dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket
from app.schemas.analytics import AnalyticsSummary, DeviceCount, TimelinePoint


async def get_summary(db: AsyncSession) -> AnalyticsSummary:
    """Return aggregated ticket statistics."""
    # Total
    total_q = select(func.count(Ticket.id))
    total = (await db.execute(total_q)).scalar() or 0

    # By category
    cat_q = select(Ticket.category, func.count(Ticket.id)).group_by(Ticket.category)
    cat_rows = (await db.execute(cat_q)).all()
    by_category = {r[0] or "прочее": r[1] for r in cat_rows}

    # By sentiment
    sent_q = select(Ticket.sentiment, func.count(Ticket.id)).group_by(Ticket.sentiment)
    sent_rows = (await db.execute(sent_q)).all()
    by_sentiment = {r[0] or "нейтраль": r[1] for r in sent_rows}

    # By status
    stat_q = select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
    stat_rows = (await db.execute(stat_q)).all()
    by_status = {r[0] or "new": r[1] for r in stat_rows}

    # Average response time (responded tickets only)
    # Approximation: use (updated_at - created_at) if updated_at exists
    avg_rt = None
    try:
        avg_q = select(
            func.avg(
                func.extract("epoch", Ticket.updated_at) - func.extract("epoch", Ticket.created_at)
            )
        ).where(Ticket.status == "responded")
        result = (await db.execute(avg_q)).scalar()
        if result is not None:
            avg_rt = round(result / 60, 1)
    except Exception:
        pass

    # Auto-response rate: is_auto=True / total
    auto_q = select(func.count(Ticket.id)).where(
        Ticket.is_auto.is_(True),
        Ticket.status == "responded",
    )
    auto_count = (await db.execute(auto_q)).scalar() or 0
    auto_rate = round(auto_count / total, 2) if total > 0 else 0.0

    # Top devices
    dev_q = (
        select(Ticket.device_type, func.count(Ticket.id).label("cnt"))
        .where(Ticket.device_type.isnot(None), Ticket.device_type != "")
        .group_by(Ticket.device_type)
        .order_by(func.count(Ticket.id).desc())
        .limit(5)
    )
    dev_rows = (await db.execute(dev_q)).all()
    top_devices = [DeviceCount(device=r[0], count=r[1]) for r in dev_rows]

    return AnalyticsSummary(
        total_tickets=total,
        by_category=by_category,
        by_sentiment=by_sentiment,
        by_status=by_status,
        avg_response_time_minutes=avg_rt,
        auto_response_rate=auto_rate,
        top_devices=top_devices,
    )


async def get_timeline(db: AsyncSession, days: int = 30) -> list[TimelinePoint]:
    """Return daily ticket counts for the last *days* days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    q = (
        select(
            cast(Ticket.created_at, Date).label("day"),
            func.count(Ticket.id).label("total"),
            func.sum(case((Ticket.is_auto.is_(True), 1), else_=0)).label("auto"),
            func.sum(case((Ticket.is_auto.is_(False), 1), else_=0)).label("manual"),
        )
        .where(Ticket.created_at >= cutoff)
        .group_by(cast(Ticket.created_at, Date))
        .order_by(cast(Ticket.created_at, Date))
    )
    rows = (await db.execute(q)).all()
    return [
        TimelinePoint(
            date=r.day.isoformat() if r.day else "",
            count=r.total,
            auto=r.auto,
            manual=r.manual,
        )
        for r in rows
    ]
