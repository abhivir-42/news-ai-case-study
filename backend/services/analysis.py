"""Orchestration: dedup, call the model, store the result, read it back.

The only module that knows the order of operations. Takes a session rather than
opening one, and returns (analysis, created) rather than a status code, so the
route decides what 201 vs 200 means. Knows nothing about HTTP.
"""

import logging
import time

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, desc, select

from database import Analysis
from models import AnalysisOutcome, Article
from services.ai import AIProviderError, analyse_article

logger = logging.getLogger(__name__)


def _find_by_url(session: Session, url: str) -> Analysis | None:
    return session.exec(select(Analysis).where(Analysis.url == url)).first()


def get_or_create_analysis(session: Session, article: Article) -> tuple[Analysis, bool]:
    """Return (analysis, created). Reuses a stored analysis if the URL was seen before."""
    existing = _find_by_url(session, article.url)
    if existing:
        # The number that justifies the whole get-or-create design. Without it the
        # dedup hit rate is unanswerable in production.
        logger.info("event=analysis.cache_hit analysis_id=%s", existing.id)
        return existing, False

    logger.info("event=analysis.cache_miss url=%s", article.url)
    started = time.monotonic()
    result = analyse_article(article.title, article.description, article.content)
    logger.info("event=ai.completed duration_ms=%d", (time.monotonic() - started) * 1000)
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
        logger.info("event=analysis.race_lost analysis_id=%s", winner.id)
        return winner, False
    session.refresh(analysis)
    return analysis, True


def dedupe_by_url(articles: list[Article]) -> list[Article]:
    """Drop repeated URLs, keeping the first. Order is preserved.

    The same URL twice in one payload is never deliberate, and left alone it would
    be priced twice by the rate limiter and returned twice to the caller.
    """
    seen: set[str] = set()
    unique = []
    for article in articles:
        if article.url in seen:
            continue
        seen.add(article.url)
        unique.append(article)
    return unique


def analyse_many(session: Session, articles: list[Article]) -> list[AnalysisOutcome]:
    """Analyse each article independently and report a verdict for each.

    One article's failure must not lose the batch. By the time the fifth model call
    fails, four analyses are committed and paid for; raising here would discard them
    and bill the caller for nothing. Expects `dedupe_by_url` to have run already.
    """
    outcomes: list[AnalysisOutcome] = []
    for article in articles:
        try:
            analysis, created = get_or_create_analysis(session, article)
        except AIProviderError as exc:
            logger.warning("event=analysis.item_failed url=%s error=%s", article.url, exc)
            outcomes.append(
                AnalysisOutcome(url=article.url, status="failed", error="AI provider error")
            )
            continue
        outcomes.append(
            AnalysisOutcome(
                url=article.url,
                status="created" if created else "reused",
                analysis=analysis,
            )
        )

    # Each commit above expired every row handed back before it, and an expired row
    # serialises as {} rather than raising. Reload them now the last commit is done.
    for outcome in outcomes:
        if outcome.analysis is not None:
            session.refresh(outcome.analysis)
    return outcomes


def list_analyses(session: Session, limit: int = 20) -> list[Analysis]:
    statement = select(Analysis).order_by(desc(Analysis.created_at)).limit(limit)
    return list(session.exec(statement).all())


def get_analysis(session: Session, analysis_id: int) -> Analysis | None:
    return session.get(Analysis, analysis_id)
