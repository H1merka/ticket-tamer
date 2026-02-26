from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ticket import TicketCreate, TicketRead, TicketUpdate
from app.services import ticket_service

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


@router.get("/", response_model=list[TicketRead])
async def list_tickets(
    status: str | None = Query(None),
    category: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await ticket_service.get_tickets(
        db, status=status, category=category, skip=skip, limit=limit
    )


@router.get("/{ticket_id}", response_model=TicketRead)
async def get_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)):
    ticket = await ticket_service.get_ticket_by_id(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/", response_model=TicketRead, status_code=201)
async def create_ticket(data: TicketCreate, db: AsyncSession = Depends(get_db)):
    return await ticket_service.create_ticket(db, data)


@router.patch("/{ticket_id}", response_model=TicketRead)
async def update_ticket(
    ticket_id: int, data: TicketUpdate, db: AsyncSession = Depends(get_db)
):
    ticket = await ticket_service.update_ticket(db, ticket_id, data)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket
