import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services import ticket_service
from app.services.auth_service import decode_access_token, get_user_by_username

router = APIRouter(prefix="/api/v1/export", tags=["export"])

_bearer_scheme = HTTPBearer(auto_error=False)


async def _get_export_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        _bearer_scheme,
    ),
    token: str | None = Query(
        None, description="JWT token for download links",
    ),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Accept auth via header OR query-param for downloads."""
    raw_token = (
        credentials.credentials if credentials else token
    )
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    payload = decode_access_token(raw_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
        )
    username: str | None = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
        )
    user = await get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )
    return user

TICKET_COLUMNS = [
    "id", "created_at", "fio", "organization", "phone", "email_from",
    "serial_numbers", "device_type", "sentiment", "confidence",
    "description", "category", "priority", "status", "is_auto",
    "response", "responded_at",
]


@router.get("/csv")
async def export_csv(
    status: str | None = Query(None),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(_get_export_user),
):
    """Export tickets as CSV with optional filters."""
    tickets = await ticket_service.get_tickets(
        db, status=status, category=category, limit=10_000
    )

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TICKET_COLUMNS)
    writer.writeheader()
    for t in tickets:
        row = {}
        for col in TICKET_COLUMNS:
            val = getattr(t, col)
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            row[col] = val
        writer.writerow(row)

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
    _current_user: User = Depends(_get_export_user),
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
        row = []
        for col in TICKET_COLUMNS:
            val = getattr(t, col)
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            row.append(val)
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"tickets_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
