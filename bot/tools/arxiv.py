import arxiv

def search_arxiv(query: str, max_results: int = 5) -> str:
    """Search academic papers on arXiv."""
    try:
        results = list(arxiv.Client().results(arxiv.Search(query=query, max_results=max_results)))
        if not results:
            return "No papers found."
        return "\n\n".join(
            f"**{r.title}**\n{r.entry_id}\n{r.summary[:300]}" for r in results
        )
    except Exception as e:
        return f"arXiv search unavailable: {e}"
