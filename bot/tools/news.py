import feedparser

FEEDS = [
    # International
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    # Russian
    "https://lenta.ru/rss/news",
    "https://www.rbc.ru/arc/outgoing/rss.rbc.ru/rbcnews.release.rss",
    # Germany
    "https://www.spiegel.de/schlagzeilen/index.rss",
    "https://rss.dw.com/rdf/rss-de-all",
]

# Generic words that mean "give me everything" — don't filter by these
_GENERIC = {"news", "новости", "nachrichten", ""}


def get_news(topic: str = "") -> str:
    """Get recent news headlines, optionally filtered by topic."""
    topic = topic.strip()
    filter_topic = topic.lower() not in _GENERIC

    try:
        items = []
        for feed_url in FEEDS:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                if filter_topic and topic.lower() not in (title + summary).lower():
                    continue
                items.append(f"**{title}**\n{entry.get('link', '')}")
        if not items and filter_topic:
            # Topic-filtered search found nothing — fall back to general headlines
            all_items = []
            for feed_url in FEEDS:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    title = entry.get("title", "")
                    all_items.append(f"**{title}**\n{entry.get('link', '')}")
            if all_items:
                return f"No headlines specifically about '{topic}'. Here are the latest general headlines:\n\n" + "\n\n".join(all_items[:12])
        if not items:
            return "NEWS_FEEDS_EMPTY: No articles retrieved from any feed. Do NOT invent or summarize news from memory. Tell the user the feeds are currently unavailable and suggest checking a news site directly."
        return "\n\n".join(items[:12])
    except Exception as e:
        return f"News unavailable: {e}"
