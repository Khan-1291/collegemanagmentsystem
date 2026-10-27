"""Initialize a new database before applying Alembic migrations."""

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import Base, engine
import app.models.models  # noqa: F401
from app.models.models import Department


def bootstrap_empty_database() -> None:
    """Create the initial schema only when no application tables exist."""
    inspector = inspect(engine)
    application_tables = set(inspector.get_table_names()) - {"alembic_version"}
    if application_tables:
        return

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        if connection.execute(
            Department.__table__.select().where(Department.code == "CS")
        ).first() is None:
            connection.execute(
                Department.__table__.insert().values(
                    name="Computer Science",
                    code="CS",
                    description="Computer Science Department",
                )
            )
    config = Config("alembic.ini")
    command.stamp(config, "head")


if __name__ == "__main__":
    bootstrap_empty_database()
