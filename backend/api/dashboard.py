from __future__ import annotations

from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import DailyActivity, UserStats
from backend.schemas import DashboardOut, HeatmapEntry

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

HEATMAP_DAYS = 180


@router.get("/", response_model=DashboardOut)
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> DashboardOut:
    # Fetch UserStats
    stats_result = await db.execute(select(UserStats).where(UserStats.id == 1))
    stats = stats_result.scalar_one_or_none()

    current_streak = 0
    longest_streak = 0
    total_attempts = 0
    estimated_band = None

    if stats is not None:
        current_streak = stats.current_streak
        longest_streak = stats.longest_streak
        total_attempts = stats.total_attempts
        estimated_band = stats.estimated_band

    # Build heatmap for the last HEATMAP_DAYS days
    today = date.today()
    start_date = today - timedelta(days=HEATMAP_DAYS - 1)

    # Fetch all DailyActivity entries in the date range
    activity_result = await db.execute(
        select(DailyActivity).where(
            DailyActivity.date >= start_date,
            DailyActivity.date <= today,
        )
    )
    activities = activity_result.scalars().all()
    activity_by_date = {a.date: a for a in activities}

    heatmap: List[HeatmapEntry] = []
    current = start_date
    while current <= today:
        activity = activity_by_date.get(current)
        if activity:
            heatmap.append(
                HeatmapEntry(
                    date=current.isoformat(),
                    count=activity.attempts_count,
                    intensity=activity.intensity,
                )
            )
        else:
            heatmap.append(
                HeatmapEntry(
                    date=current.isoformat(),
                    count=0,
                    intensity=0,
                )
            )
        current += timedelta(days=1)

    return DashboardOut(
        current_streak=current_streak,
        longest_streak=longest_streak,
        total_attempts=total_attempts,
        estimated_band=estimated_band,
        heatmap=heatmap,
    )
