import csv
import io
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.models import Client, ColorChart, Formula, Service, User

router = APIRouter(prefix="/exports", tags=["exports"])


def _write_csv(headers: list[str], rows: list[list[str | int | float | None]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


@router.get("/data")
def export_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> StreamingResponse:
    clients = list(
        db.scalars(
            select(Client).where(Client.owner_user_id == current_user.id).order_by(Client.id.asc())
        ).all()
    )
    services = list(
        db.scalars(
            select(Service).where(Service.owner_user_id == current_user.id).order_by(Service.sort_order.asc())
        ).all()
    )
    formulas = list(
        db.scalars(
            select(Formula)
            .join(Client, Client.id == Formula.client_id)
            .where(Client.owner_user_id == current_user.id)
            .order_by(Formula.service_at.desc())
        ).all()
    )
    color_charts = list(
        db.scalars(
            select(ColorChart)
            .join(Client, Client.id == ColorChart.client_id)
            .where(Client.owner_user_id == current_user.id)
            .order_by(ColorChart.client_id.asc())
        ).all()
    )

    client_rows = [
        [
            client.id,
            client.first_name,
            client.last_name,
            client.email,
            client.phone,
            client.birthday.isoformat() if client.birthday else None,
            client.client_type,
            client.notes,
            client.created_at.isoformat() if client.created_at else None,
            client.updated_at.isoformat() if client.updated_at else None,
        ]
        for client in clients
    ]

    service_rows = [
        [
            service.id,
            service.name,
            service.normalized_name,
            service.sort_order,
            service.is_active,
            service.created_at.isoformat() if service.created_at else None,
            service.updated_at.isoformat() if service.updated_at else None,
        ]
        for service in services
    ]

    formula_rows = [
        [
            formula.id,
            formula.client_id,
            formula.service_type,
            formula.price_cents,
            formula.notes,
            formula.service_at.isoformat() if formula.service_at else None,
            formula.created_at.isoformat() if formula.created_at else None,
            formula.updated_at.isoformat() if formula.updated_at else None,
        ]
        for formula in formulas
    ]

    chart_rows = [
        [
            chart.client_id,
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
            chart.created_at.isoformat() if chart.created_at else None,
            chart.updated_at.isoformat() if chart.updated_at else None,
        ]
        for chart in color_charts
    ]

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(
            "clients.csv",
            _write_csv(
                [
                    "id",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "birthday",
                    "client_type",
                    "notes",
                    "created_at",
                    "updated_at",
                ],
                client_rows,
            ),
        )
        zip_file.writestr(
            "services.csv",
            _write_csv(
                [
                    "id",
                    "name",
                    "normalized_name",
                    "sort_order",
                    "is_active",
                    "created_at",
                    "updated_at",
                ],
                service_rows,
            ),
        )
        zip_file.writestr(
            "appointment_logs.csv",
            _write_csv(
                [
                    "id",
                    "client_id",
                    "service_type",
                    "price_cents",
                    "notes",
                    "service_at",
                    "created_at",
                    "updated_at",
                ],
                formula_rows,
            ),
        )
        zip_file.writestr(
            "color_charts.csv",
            _write_csv(
                [
                    "client_id",
                    "porosity",
                    "hair_texture",
                    "elasticity",
                    "scalp_condition",
                    "natural_level",
                    "desired_level",
                    "contributing_pigment",
                    "gray_front",
                    "gray_sides",
                    "gray_back",
                    "skin_depth",
                    "skin_tone",
                    "eye_color",
                    "created_at",
                    "updated_at",
                ],
                chart_rows,
            ),
        )

    zip_buffer.seek(0)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"myguest_export_{timestamp}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
