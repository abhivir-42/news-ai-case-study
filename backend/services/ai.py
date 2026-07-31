from enum import Enum
from openai import OpenAI, OpenAIError
from pydantic import BaseModel

from config import settings

# The call sits in the request path, so it must be bounded. The SDK retries
# connection errors, 429s and 5xx with exponential backoff and jitter; 4xx such as
# a bad key fail immediately, because retrying those never helps.
OPENAI_TIMEOUT_SECONDS = 20.0
OPENAI_MAX_RETRIES = 2

client = OpenAI(
    api_key=settings.openai_api_key.get_secret_value(),
    timeout=OPENAI_TIMEOUT_SECONDS,
    max_retries=OPENAI_MAX_RETRIES,
)

SYSTEM_PROMPT = (
    "You are a news analyst. Given a news article, write a concise 2-sentence summary, "
    "classify the overall sentiment of the coverage as positive, neutral, or negative, "
    "give a sentiment_score from -1.0 (very negative) to 1.0 (very positive), and a "
    "one-sentence rationale for the sentiment."
)


class AIProviderError(Exception):
    """Raised when the AI provider returns no usable structured output."""


class Sentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class ArticleAnalysis(BaseModel):
    summary: str
    sentiment: Sentiment
    sentiment_score: float
    rationale: str


def analyse_article(title: str, description: str | None, content: str | None) -> ArticleAnalysis:
    article_text = f"Title: {title}\n\nDescription: {description or ''}\n\nContent: {content or ''}"
    try:
        completion = client.chat.completions.parse(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": article_text},
            ],
            response_format=ArticleAnalysis,
        )
    except OpenAIError as exc:
        # Timeouts, rate limits and API errors are all upstream failures once the
        # SDK has exhausted its retries.
        raise AIProviderError(f"OpenAI request failed: {exc}") from exc
    choice = completion.choices[0]
    if choice.message.parsed is None:
        # The SDK returns None when the model refused or stopped early, so the
        # annotation on this function is only true because of this check.
        raise AIProviderError(
            f"model returned no parsed output (finish_reason={choice.finish_reason})"
        )
    return choice.message.parsed
