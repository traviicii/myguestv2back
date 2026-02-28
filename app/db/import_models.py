# Importing models registers them on SQLAlchemy metadata for Alembic/autogenerate.
from app.models import Client, ColorChart, Formula, FormulaImage, FormulaService, Service, User  # noqa: F401
