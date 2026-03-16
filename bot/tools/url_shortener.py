import httpx

def shorten_url(url: str) -> str:
    """Shorten a URL using TinyURL."""
    try:
        resp = httpx.get(f"https://tinyurl.com/api-create.php?url={url}", timeout=10)
        return resp.text.strip()
    except Exception as e:
        return f"URL shortener unavailable: {e}"
