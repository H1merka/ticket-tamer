import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import ticket_service

router = APIRouter(prefix="/api/v1/export", tags=["export"])

TICKET_COLUMNS = [
    "id", "email_from", "subject", "category", "priority",
    "sentiment", "status", "is_auto", "response", "created_at", "responded_at",
]


@router.get("/csv")
async def export_csv(
    status: str | None = Query(None),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Export tickets as CSV with optional filters."""
    tickets = await ticket_service.get_tickets(
        db, status=status, category=category, limit=10_000
    )

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TICKET_COLUMNS)
    writer.writeheader()
    for t in tickets:
        writer.writerow({col: getattr(t, col) for col in TICKET_COLUMNS})

    buf.seek(0)
    filename = f"tickets_{datetime.now():%Y%m%d_%H%M%S}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/xlsx")
async def export_xlsx(
    status: str | None = Query(None),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Export tickets as XLSX with optional filters."""
    from openpyxl import Workbook

    tickets = await ticket_service.get_tickets(
        db, status=status, category=category, limit=10_000
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Tickets"
    ws.append(TICKET_COLUMNS)
    for t in tickets:
        ws.append([getattr(t, col) for col in TICKET_COLUMNS])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"tickets_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
