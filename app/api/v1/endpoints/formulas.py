from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_session
from app.core.errors import AppError
from app.models import Client, Formula, User
from app.schemas.formula import FormulaCreate, FormulaListResponse, FormulaRead, FormulaUpdate

router = APIRouter(tags=["formulas"])


def _get_owned_client(db: Session, user_id: int, client_id: int) -> Client:
    client = db.scalar(select(Client).where(Client.id == client_id, Client.owner_user_id == user_id))
    if not client:
        raise AppError(404, "client_not_found", "Client not found.")
    return client


def _get_owned_formula(db: Session, user_id: int, formula_id: int) -> Formula:
    stmt = (
        select(Formula)
        .options(selectinload(Formula.images))
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaListResponse:
    _get_owned_client(db, current_user.id, client_id)
    total = db.scalar(select(func.count(Formula.id)).where(Formula.client_id == client_id)) or 0
    stmt = (
        select(Formula)
        .options(selectinload(Formula.images))
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
        items=[FormulaRead.model_validate(formula) for formula in formulas],
    )


@router.post("/clients/{client_id}/formulas", response_model=FormulaRead, status_code=201)
def create_formula(
    client_id: int,
    payload: FormulaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> FormulaRead:
    _get_owned_client(db, current_user.id, client_id)
    formula = Formula(client_id=client_id, **payload.model_dump())
    db.add(formula)
    db.commit()
    db.refresh(formula)
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
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(formula, field, value)
    db.commit()
    db.refresh(formula)
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
