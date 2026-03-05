import feedparser

FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
]

def get_news(topic: str = "") -> str:
    """Get recent news headlines, optionally filtered by topic."""
    try:
        items = []
        for feed_url in FEEDS:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                if not topic or topic.lower() in entry.title.lower():
                    items.append(f"**{entry.title}**\n{entry.link}")
        return "\n\n".join(items[:10]) if items else "No news found."
    except Exception as e:
        return f"News unavailable: {e}"
