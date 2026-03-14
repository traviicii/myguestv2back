from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.core.errors import AppError
from app.models import Client, Formula, User
from app.schemas.formula import FormulaCreate, FormulaListResponse, FormulaRead, FormulaUpdate
from app.services.formulas import (
    apply_legacy_service_type,
    apply_service_assignment_by_ids,
    build_formula_list_shape,
    formula_load_options,
    replace_formula_images,
    serialize_formula,
)

router = APIRouter(tags=["formulas"])


def _get_owned_client(db: Session, user_id: int, client_id: int) -> Client:
    client = db.scalar(select(Client).where(Client.id == client_id, Client.owner_user_id == user_id))
    if not client:
        raise AppError(404, "client_not_found", "Client not found.")
    return client


def _get_owned_formula(db: Session, user_id: int, formula_id: int) -> Formula:
    stmt = (
        select(Formula)
        .options(*formula_load_options())
        .join(Client, Client.id == Formula.client_id)
        .where(Formula.id == formula_id, Client.owner_user_id == user_id)
    )
    formula = db.scalar(stmt)
    if not formula:
        raise AppError(404, "formula_not_found", "Formula not found.")
    return formula


@router.get("/clients/{client_id}/formulas", response_model=FormulaListResponse)
def list_client_formulas(
    client_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include: str | None = Query(default=None),
    fields: Literal["full", "lite"] = Query(default="full"),
    image_limit: int | None = Query(default=None, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaListResponse:
    _get_owned_client(db, current_user.id, client_id)
    shape = build_formula_list_shape(include, fields)
    total = db.scalar(select(func.count(Formula.id)).where(Formula.client_id == client_id)) or 0
    stmt = (
        select(Formula)
        .options(*shape.options)
        .where(Formula.client_id == client_id)
        .order_by(desc(Formula.service_at))
        .offset(offset)
        .limit(limit)
    )
    formulas = list(db.scalars(stmt).all())
    return FormulaListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            FormulaRead.model_validate(
                serialize_formula(
                    formula,
                    include_images=shape.include_images,
                    include_services=shape.include_services,
                    include_notes=shape.include_notes,
                    image_limit=image_limit,
                )
            )
            for formula in formulas
        ],
    )


@router.get("/formulas", response_model=FormulaListResponse)
def list_formulas(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    include: str | None = Query(default=None),
    fields: Literal["full", "lite"] = Query(default="full"),
    image_limit: int | None = Query(default=None, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaListResponse:
    shape = build_formula_list_shape(include, fields)
    filters = Client.owner_user_id == current_user.id
    total = (
        db.scalar(
            select(func.count(Formula.id))
            .join(Client, Client.id == Formula.client_id)
            .where(filters)
        )
        or 0
    )
    stmt = (
        select(Formula)
        .options(*shape.options)
        .join(Client, Client.id == Formula.client_id)
        .where(filters)
        .order_by(desc(Formula.service_at))
        .offset(offset)
        .limit(limit)
    )
    formulas = list(db.scalars(stmt).all())
    return FormulaListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            FormulaRead.model_validate(
                serialize_formula(
                    formula,
                    include_images=shape.include_images,
                    include_services=shape.include_services,
                    include_notes=shape.include_notes,
                    image_limit=image_limit,
                )
            )
            for formula in formulas
        ],
    )


@router.post("/clients/{client_id}/formulas", response_model=FormulaRead, status_code=201)
def create_formula(
    client_id: int,
    payload: FormulaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaRead:
    client = _get_owned_client(db, current_user.id, client_id)
    formula = Formula(
        client_id=client_id,
        notes=payload.notes,
        price_cents=payload.price_cents,
        service_at=payload.service_at,
    )
    db.add(formula)

    if payload.service_ids is not None:
        apply_service_assignment_by_ids(db, formula, client.owner_user_id, payload.service_ids)
    else:
        apply_legacy_service_type(db, formula, client.owner_user_id, payload.service_type)
    if payload.images is not None:
        replace_formula_images(formula, payload.images)

    db.commit()
    formula = _get_owned_formula(db, current_user.id, formula.id)
    return FormulaRead.model_validate(formula)


@router.get("/formulas/{formula_id}", response_model=FormulaRead)
def get_formula(
    formula_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaRead:
    formula = _get_owned_formula(db, current_user.id, formula_id)
    return FormulaRead.model_validate(formula)


@router.patch("/formulas/{formula_id}", response_model=FormulaRead)
def update_formula(
    formula_id: int,
    payload: FormulaUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaRead:
    formula = _get_owned_formula(db, current_user.id, formula_id)
    payload_values = payload.model_dump(exclude_unset=True)

    if "notes" in payload_values:
        formula.notes = payload_values["notes"]
    if "price_cents" in payload_values:
        formula.price_cents = payload_values["price_cents"]
    if "service_at" in payload_values:
        formula.service_at = payload_values["service_at"]

    owner_user_id = formula.client.owner_user_id
    if "service_ids" in payload_values:
        apply_service_assignment_by_ids(
            db, formula, owner_user_id, payload_values.get("service_ids")
        )
    elif "service_type" in payload_values:
        apply_legacy_service_type(
            db, formula, owner_user_id, payload_values.get("service_type")
        )
    if "images" in payload_values:
        replace_formula_images(formula, payload.images or [])

    db.commit()
    formula = _get_owned_formula(db, current_user.id, formula.id)
    return FormulaRead.model_validate(formula)


@router.delete("/formulas/{formula_id}", status_code=204)
def delete_formula(
    formula_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> Response:
    formula = _get_owned_formula(db, current_user.id, formula_id)
    db.delete(formula)
    db.commit()
    return Response(status_code=204)
