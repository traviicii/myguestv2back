from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.errors import AppError
from app.models import Client, ColorChart, User
from app.schemas.color_chart import ColorChartListResponse, ColorChartRead, ColorChartUpsert

router = APIRouter(tags=["color-charts"])


def _get_owned_client(db: Session, user_id: int, client_id: int) -> Client:
    client = db.scalar(
        select(Client).where(Client.id == client_id, Client.owner_user_id == user_id)
    )
    if not client:
        raise AppError(404, "client_not_found", "Client not found.")
    return client


@router.get("/color-charts", response_model=ColorChartListResponse)
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


@router.get("/clients/{client_id}/color-chart", response_model=ColorChartRead)
def get_client_color_chart(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ColorChartRead:
    client = _get_owned_client(db, current_user.id, client_id)
    color_chart = db.scalar(select(ColorChart).where(ColorChart.client_id == client.id))
    if not color_chart:
        raise AppError(404, "color_chart_not_found", "Color chart not found.")
    return ColorChartRead.model_validate(color_chart)


@router.patch("/clients/{client_id}/color-chart", response_model=ColorChartRead)
def upsert_client_color_chart(
    client_id: int,
    payload: ColorChartUpsert,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ColorChartRead:
    client = _get_owned_client(db, current_user.id, client_id)
    color_chart = db.scalar(select(ColorChart).where(ColorChart.client_id == client.id))

    if not color_chart:
        color_chart = ColorChart(client_id=client.id)
        db.add(color_chart)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(color_chart, field, value)

    db.commit()
    db.refresh(color_chart)
    return ColorChartRead.model_validate(color_chart)
