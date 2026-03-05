from duckduckgo_search import DDGS

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo."""
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No results found."
        return "\n\n".join(f"**{r['title']}**\n{r['href']}\n{r['body']}" for r in results)
    except Exception as e:
        return f"Web search unavailable: {e}"
