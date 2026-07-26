from enum import Enum
from openai import OpenAI
from pydantic import BaseModel

from config import settings

client = OpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = (
    "You are a news analyst. Given a news article, write a concise 2-sentence summary, "
    "classify the overall sentiment of the coverage as positive, neutral, or negative, "
    "give a sentiment_score from -1.0 (very negative) to 1.0 (very positive), and a "
    "one-sentence rationale for the sentiment."
)


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
    completion = client.chat.completions.parse(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": article_text},
        ],
        response_format=ArticleAnalysis,
    )
    return completion.choices[0].message.parsed
