from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_session
from app.core.errors import AppError
from app.models import (
    Client,
    ClientGroup,
    ClientGroupMembership,
    ColorChart,
    Formula,
    FormulaImage,
    FormulaService,
    User,
)
from app.schemas.metrics import OverviewMetrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _parse_iso_datetime(value: str | None, label: str) -> datetime | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed or trimmed.lower() == "null":
        return None
    try:
        normalized = trimmed.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AppError(422, "invalid_datetime", f"Invalid {label}.") from exc


def _has_color_data(chart: ColorChart) -> bool:
    fields = (
        chart.porosity,
        chart.hair_texture,
        chart.elasticity,
        chart.scalp_condition,
        chart.natural_level,
        chart.desired_level,
        chart.contrib_pigment,
        chart.gray_front,
        chart.gray_sides,
        chart.gray_back,
        chart.skin_depth,
        chart.skin_tone,
        chart.eye_color,
    )
    for value in fields:
        if value is None:
            continue
        trimmed = value.strip()
        if not trimmed:
            continue
        lowered = trimmed.lower()
        if lowered in {"unknown", "n/a", "na", "-"}:
            continue
        return True
    return False


@router.get("/overview", response_model=OverviewMetrics)
def overview_metrics(
    active_cutoff: str = Query(...),
    year_start: str = Query(...),
    avg_ticket_cutoff: str | None = Query(default=None),
    photo_cutoff: str | None = Query(default=None),
    new_clients_cutoff: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> OverviewMetrics:
    active_cutoff_dt = _parse_iso_datetime(active_cutoff, "active_cutoff")
    year_start_dt = _parse_iso_datetime(year_start, "year_start")
    avg_ticket_cutoff_dt = _parse_iso_datetime(avg_ticket_cutoff, "avg_ticket_cutoff")
    photo_cutoff_dt = _parse_iso_datetime(photo_cutoff, "photo_cutoff")
    new_clients_cutoff_dt = _parse_iso_datetime(new_clients_cutoff, "new_clients_cutoff")

    if active_cutoff_dt is None or year_start_dt is None or new_clients_cutoff_dt is None:
        raise AppError(422, "invalid_datetime", "Required cutoff values are missing.")

    total_clients = (
        db.scalar(
            select(func.count(Client.id)).where(Client.owner_user_id == current_user.id)
        )
        or 0
    )

    active_clients = (
        db.scalar(
            select(func.count(func.distinct(Formula.client_id)))
            .join(Client, Client.id == Formula.client_id)
            .where(
                Client.owner_user_id == current_user.id,
                Formula.service_at >= active_cutoff_dt,
            )
        )
        or 0
    )

    inactive_clients = max(total_clients - active_clients, 0)

    revenue_cents = (
        db.scalar(
            select(func.coalesce(func.sum(Formula.price_cents), 0))
            .join(Client, Client.id == Formula.client_id)
            .where(
                Client.owner_user_id == current_user.id,
                Formula.service_at >= year_start_dt,
            )
        )
        or 0
    )
    revenue_ytd = revenue_cents / 100.0

    avg_filters = [Client.owner_user_id == current_user.id]
    if avg_ticket_cutoff_dt is not None:
        avg_filters.append(Formula.service_at >= avg_ticket_cutoff_dt)

    avg_sum_cents = (
        db.scalar(
            select(func.coalesce(func.sum(Formula.price_cents), 0))
            .join(Client, Client.id == Formula.client_id)
            .where(*avg_filters)
        )
        or 0
    )
    avg_count = (
        db.scalar(
            select(func.count(Formula.id))
            .join(Client, Client.id == Formula.client_id)
            .where(*avg_filters)
        )
        or 0
    )
    avg_ticket = (avg_sum_cents / 100.0) / avg_count if avg_count else 0.0

    new_clients_90 = (
        db.scalar(
            select(func.count(Client.id)).where(
                Client.owner_user_id == current_user.id,
                Client.created_at >= new_clients_cutoff_dt,
            )
        )
        or 0
    )

    eligible_client_ids = list(
        db.scalars(
            select(func.distinct(Client.id))
            .outerjoin(ClientGroupMembership, ClientGroupMembership.client_id == Client.id)
            .outerjoin(ClientGroup, ClientGroup.id == ClientGroupMembership.group_id)
            .where(
                Client.owner_user_id == current_user.id,
                (
                    Client.client_type.in_(["Color", "Cut & Color"])
                    | (ClientGroup.normalized_name == "color")
                ),
            )
        ).all()
    )
    eligible_count = len(eligible_client_ids)
    color_coverage_percent = 0
    if eligible_count:
        charts = list(
            db.scalars(
                select(ColorChart).where(ColorChart.client_id.in_(eligible_client_ids))
            ).all()
        )
        with_color = sum(1 for chart in charts if _has_color_data(chart))
        color_coverage_percent = round((with_color / eligible_count) * 100)

    photo_filters = [Client.owner_user_id == current_user.id]
    if photo_cutoff_dt is not None:
        photo_filters.append(Formula.service_at >= photo_cutoff_dt)

    total_formulas = (
        db.scalar(
            select(func.count(Formula.id))
            .join(Client, Client.id == Formula.client_id)
            .where(*photo_filters)
        )
        or 0
    )
    with_photos = (
        db.scalar(
            select(func.count(func.distinct(Formula.id)))
            .select_from(Formula)
            .join(Client, Client.id == Formula.client_id)
            .join(FormulaImage, FormulaImage.formula_id == Formula.id)
            .where(*photo_filters)
        )
        or 0
    )
    photo_coverage_percent = (
        round((with_photos / total_formulas) * 100) if total_formulas else 0
    )

    active_formulas = list(
        db.scalars(
            select(Formula)
            .join(Client, Client.id == Formula.client_id)
            .where(
                Client.owner_user_id == current_user.id,
                Formula.service_at >= active_cutoff_dt,
            )
            .options(
                selectinload(Formula.formula_services).selectinload(FormulaService.service)
            )
        ).all()
    )
    total_active_formulas = len(active_formulas)
    label_counts: dict[str, int] = {}
    for formula in active_formulas:
        if formula.formula_services:
            labels = [service.name for service in formula.formula_services]
        else:
            label = (formula.service_type or "").strip() or "Service"
            labels = [label]
        for label in labels:
            normalized = label.strip() or "Service"
            label_counts[normalized] = label_counts.get(normalized, 0) + 1

    if label_counts and total_active_formulas:
        service_mix_label, service_mix_count = max(
            label_counts.items(), key=lambda item: item[1]
        )
        service_mix_percent = round((service_mix_count / total_active_formulas) * 100)
    else:
        service_mix_label = ""
        service_mix_percent = 0

    return OverviewMetrics(
        revenue_ytd=revenue_ytd,
        avg_ticket=avg_ticket,
        total_clients=total_clients,
        active_clients=active_clients,
        inactive_clients=inactive_clients,
        new_clients_90=new_clients_90,
        service_mix_label=service_mix_label,
        service_mix_percent=service_mix_percent,
        color_coverage_percent=color_coverage_percent,
        photo_coverage_percent=photo_coverage_percent,
    )
