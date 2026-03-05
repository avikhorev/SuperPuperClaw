import wikipedia as wiki

def search_wikipedia(query: str) -> str:
    """Search Wikipedia and return a summary."""
    try:
        results = wiki.search(query)
        if not results:
            return f"No Wikipedia results for '{query}'."
        page = wiki.page(results[0])
        return page.summary[:3000]
    except Exception as e:
        return f"Wikipedia unavailable: {e}"
