import re
import urllib.parse
import urllib.request
import json


def _ddgs_html_search(query: str, max_results: int) -> list:
    """Scrape DDG HTML lite — bypasses geo-routing that returns Chinese results."""
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query, "kl": "us-en"})
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode("utf-8", errors="ignore")

    titles = re.findall(r'class="result__a"[^>]*>([^<]+(?:<[^/][^>]*>[^<]*</[^>]+>[^<]*)*)', html)
    titles = [re.sub(r"<[^>]+>", "", t).strip() for t in titles]
    raw_urls = re.findall(r'uddg=([^&"]+)', html)
    urls = [urllib.parse.unquote(u) for u in raw_urls]
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
    snippets = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets]

    results = []
    for i, (title, url) in enumerate(zip(titles, urls)):
        if not title or not url.startswith("http"):
            continue
        # Skip DDG ad redirect URLs
        if "duckduckgo.com" in url:
            continue
        body = snippets[i] if i < len(snippets) else ""
        results.append({"title": title, "href": url, "body": body})
        if len(results) >= max_results:
            break
    return results


def _ddgs_api_search(query: str, max_results: int) -> list:
    """Fallback: DDG Python library."""
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    from duckduckgo_search import DDGS
    return DDGS().text(query, max_results=max_results) or []


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for current information."""
    errors = []

    try:
        results = _ddgs_html_search(query, max_results)
        if results:
            return "\n\n".join(f"**{r['title']}**\n{r['href']}\n{r['body']}" for r in results)
    except Exception as e:
        errors.append(f"DDG-HTML: {e}")

    try:
        results = _ddgs_api_search(query, max_results)
        if results:
            return "\n\n".join(f"**{r['title']}**\n{r['href']}\n{r['body']}" for r in results)
    except Exception as e:
        errors.append(f"DDG-API: {e}")

    return f"Web search unavailable: {'; '.join(errors)}"
