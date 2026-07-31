from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, desc, select

from database import Analysis
from models import Article
from services.ai import analyse_article


def _find_by_url(session: Session, url: str) -> Analysis | None:
    return session.exec(select(Analysis).where(Analysis.url == url)).first()


def get_or_create_analysis(session: Session, article: Article) -> tuple[Analysis, bool]:
    """Return (analysis, created). Reuses a stored analysis if the URL was seen before."""
    existing = _find_by_url(session, article.url)
    if existing:
        return existing, False

    result = analyse_article(article.title, article.description, article.content)
    analysis = Analysis(
        url=article.url,
        title=article.title,
        source=article.source_name,
        published_at=article.published_at,
        summary=result.summary,
        sentiment=result.sentiment.value,
        sentiment_score=result.sentiment_score,
    )
    session.add(analysis)
    try:
        session.commit()
    except IntegrityError:
        # A concurrent request inserted this URL between our check and our commit.
        # The unique index rejected us, which is correct — recover by returning theirs.
        session.rollback()
        winner = _find_by_url(session, article.url)
        if winner is None:
            raise  # the violation was not the url constraint; do not swallow it
        return winner, False
    session.refresh(analysis)
    return analysis, True


def list_analyses(session: Session, limit: int = 20) -> list[Analysis]:
    statement = select(Analysis).order_by(desc(Analysis.created_at)).limit(limit)
    return list(session.exec(statement).all())


def get_analysis(session: Session, analysis_id: int) -> Analysis | None:
    return session.get(Analysis, analysis_id)
