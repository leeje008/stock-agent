import feedparser
from datetime import datetime
from urllib.parse import quote

from utils.helpers import read_cache, write_cache

# 한국 주요 종목 티커-이름 매핑
KR_TICKER_NAMES = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스",
    "005380": "현대자동차",
    "000270": "기아",
    "068270": "셀트리온",
    "035420": "NAVER",
    "035720": "카카오",
    "051910": "LG화학",
    "006400": "삼성SDI",
    "105560": "KB금융",
    "055550": "신한지주",
    "003670": "포스코퓨처엠",
    "066570": "LG전자",
    "028260": "삼성물산",
    "012330": "현대모비스",
    "096770": "SK이노베이션",
    "034730": "SK",
    "003550": "LG",
}

GOOGLE_NEWS_RSS_URL = (
    "https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}"
)


class NewsFetcher:
    """Google News RSS를 활용한 주식 뉴스 수집기"""

    def get_ticker_news(
        self, ticker: str, market: str, limit: int = 5
    ) -> list[dict]:
        """특정 종목의 뉴스를 가져옵니다.

        Args:
            ticker: 종목 코드 (예: "005930", "AAPL")
            market: 시장 구분 ("KR" 또는 "US")
            limit: 가져올 뉴스 수

        Returns:
            뉴스 목록 (dict 리스트)
        """
        cache_key = f"news_{market}_{ticker}"
        cached = read_cache(cache_key)
        if cached is not None:
            return cached

        try:
            if market == "KR":
                query = self._build_kr_query(ticker)
                feed_url = self._build_rss_url(query, lang="ko")
            else:
                query = f"{ticker} stock"
                feed_url = self._build_rss_url(query, lang="en")

            articles = self._parse_feed(feed_url, limit)
            write_cache(cache_key, articles)
            return articles
        except Exception:
            return []

    def get_market_news(
        self, market: str = "US", limit: int = 5
    ) -> list[dict]:
        """시장 전반의 뉴스를 가져옵니다.

        Args:
            market: 시장 구분 ("KR" 또는 "US")
            limit: 가져올 뉴스 수

        Returns:
            뉴스 목록 (dict 리스트)
        """
        cache_key = f"news_{market}_market"
        cached = read_cache(cache_key)
        if cached is not None:
            return cached

        try:
            if market == "KR":
                query = "한국 주식시장"
                feed_url = self._build_rss_url(query, lang="ko")
            else:
                query = "US stock market"
                feed_url = self._build_rss_url(query, lang="en")

            articles = self._parse_feed(feed_url, limit)
            write_cache(cache_key, articles)
            return articles
        except Exception:
            return []

    def _build_kr_query(self, ticker: str) -> str:
        """한국 종목 코드를 검색 쿼리로 변환합니다."""
        name = KR_TICKER_NAMES.get(ticker, ticker)
        return f"{name} 주식"

    def _build_rss_url(self, query: str, lang: str = "en") -> str:
        """Google News RSS URL을 생성합니다."""
        encoded_query = quote(query)
        if lang == "ko":
            return GOOGLE_NEWS_RSS_URL.format(
                query=encoded_query, hl="ko", gl="KR", ceid="KR:ko"
            )
        return GOOGLE_NEWS_RSS_URL.format(
            query=encoded_query, hl="en", gl="US", ceid="US:en"
        )

    def _parse_feed(self, url: str, limit: int) -> list[dict]:
        """RSS 피드를 파싱하여 뉴스 목록으로 변환합니다."""
        feed = feedparser.parse(url)
        articles = []

        for entry in feed.entries[:limit]:
            published = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(
                        *entry.published_parsed[:6]
                    ).strftime("%Y-%m-%d")
                except Exception:
                    published = ""

            source = ""
            if hasattr(entry, "source") and hasattr(entry.source, "title"):
                source = entry.source.title
            elif " - " in entry.get("title", ""):
                source = entry.title.rsplit(" - ", 1)[-1]

            articles.append(
                {
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "source": source,
                    "date": published,
                    "url": entry.get("link", ""),
                }
            )

        return articles
