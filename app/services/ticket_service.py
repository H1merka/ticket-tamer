from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket
from app.schemas.ticket import TicketCreate, TicketUpdate


async def get_tickets(
    db: AsyncSession,
    *,
    status: str | None = None,
    category: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Ticket]:
    """Return a filtered, paginated list of tickets."""
    query = select(Ticket).order_by(Ticket.created_at.desc())
    if status:
        query = query.where(Ticket.status == status)
    if category:
        query = query.where(Ticket.category == category)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_ticket_by_id(db: AsyncSession, ticket_id: int) -> Ticket | None:
    return await db.get(Ticket, ticket_id)


async def create_ticket(db: AsyncSession, data: TicketCreate) -> Ticket:
    ticket = Ticket(**data.model_dump())
    db.add(ticket)
    await db.flush()
    await db.refresh(ticket)
    return ticket


async def update_ticket(
    db: AsyncSession, ticket_id: int, data: TicketUpdate
) -> Ticket | None:
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)
    await db.flush()
    await db.refresh(ticket)
    return ticket
