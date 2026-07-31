"""Database engine, the one table, and the per-request session.

`Analysis` is both a SQLModel table and a Pydantic model, which is why the same
class works as a row and as a route response_model. `get_session` is a generator
dependency: FastAPI opens a session before a handler runs and closes it after the
response is sent, and tests swap it out via app.dependency_overrides.
"""

from datetime import datetime, timezone

from sqlmodel import Field, Session, SQLModel, create_engine

from config import settings

engine = create_engine(settings.database_url.get_secret_value(), echo=False)

class Analysis(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(unique=True, index=True)
    title: str
    source: str
    published_at: str
    summary: str
    sentiment: str
    sentiment_score: float
    # Indexed because list_analyses orders every read by this column.
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
