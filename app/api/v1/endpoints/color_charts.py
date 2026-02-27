from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.models import Client, ColorChart, User
from app.schemas.color_chart import ColorChartListResponse, ColorChartRead

router = APIRouter(prefix="/color-charts", tags=["color-charts"])


@router.get("", response_model=ColorChartListResponse)
def list_color_charts(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ColorChartListResponse:
    owner_filter = Client.owner_user_id == current_user.id

    total_stmt = (
        select(func.count(ColorChart.id))
        .select_from(ColorChart)
        .join(Client, Client.id == ColorChart.client_id)
        .where(owner_filter)
    )
    total = db.scalar(total_stmt) or 0

    items_stmt = (
        select(ColorChart)
        .join(Client, Client.id == ColorChart.client_id)
        .where(owner_filter)
        .order_by(ColorChart.client_id.asc())
        .offset(offset)
        .limit(limit)
    )
    items = list(db.scalars(items_stmt).all())

    return ColorChartListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[ColorChartRead.model_validate(item) for item in items],
    )
