from sqlmodel import Session, desc, select

from database import Analysis
from models import Article
from services.ai import analyse_article


def get_or_create_analysis(session: Session, article: Article) -> tuple[Analysis, bool]:
    """Return (analysis, created). Reuses a stored analysis if the URL was seen before."""
    existing = session.exec(select(Analysis).where(Analysis.url == article.url)).first()
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
    session.commit()
    session.refresh(analysis)
    return analysis, True


def list_analyses(session: Session, limit: int = 20) -> list[Analysis]:
    statement = select(Analysis).order_by(desc(Analysis.created_at)).limit(limit)
    return list(session.exec(statement).all())


def get_analysis(session: Session, analysis_id: int) -> Analysis | None:
    return session.get(Analysis, analysis_id)
