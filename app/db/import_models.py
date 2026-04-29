# Importing models registers them on SQLAlchemy metadata for Alembic/autogenerate.
from app.models import (  # noqa: F401
    Client,
    ColorChart,
    Formula,
    FormulaImage,
    FormulaService,
    Service,
    User,
)
