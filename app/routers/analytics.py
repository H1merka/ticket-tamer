"""Analytics API — summary statistics and timeline for the dashboard."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.analytics import AnalyticsSummary, TimelinePoint
from app.services import analytics_service

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(db: AsyncSession = Depends(get_db), _current_user: User = Depends(get_current_user)):
    """Aggregated ticket statistics for the dashboard."""
    return await analytics_service.get_summary(db)


@router.get("/timeline", response_model=list[TimelinePoint])
async def get_timeline(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Daily ticket counts for the specified number of past days."""
    return await analytics_service.get_timeline(db, days=days)
