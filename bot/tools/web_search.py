import urllib.parse
import urllib.request
import json


def _ddgs_search(query: str, max_results: int) -> list:
    from duckduckgo_search import DDGS
    return DDGS().text(query, max_results=max_results) or []


def _brave_search(query: str, max_results: int) -> list:
    url = "https://search.brave.com/api/search?" + urllib.parse.urlencode({
        "q": query, "count": max_results, "format": "json"
    })
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read())
    return [
        {"title": item.get("title", ""), "href": item.get("url", ""), "body": item.get("description", "")}
        for item in data.get("web", {}).get("results", [])[:max_results]
    ]


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo (Brave as fallback)."""
    errors = []

    try:
        results = _ddgs_search(query, max_results)
        if results:
            return "\n\n".join(f"**{r['title']}**\n{r['href']}\n{r['body']}" for r in results)
    except Exception as e:
        errors.append(f"DuckDuckGo: {e}")

    try:
        results = _brave_search(query, max_results)
        if results:
            return "\n\n".join(f"**{r['title']}**\n{r['href']}\n{r['body']}" for r in results)
    except Exception as e:
        errors.append(f"Brave: {e}")

    return f"Web search unavailable: {'; '.join(errors)}"
