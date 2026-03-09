def build_logs_tools(storage):
    def search_logs(query: str) -> str:
        """Search through conversation history logs. Returns matching lines with dates."""
        results = storage.search_logs(query)
        if not results:
            return "No results found."
        return "\n".join(results)

    search_logs._needs_storage = False
    return [search_logs]
