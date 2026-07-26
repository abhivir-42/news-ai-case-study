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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
