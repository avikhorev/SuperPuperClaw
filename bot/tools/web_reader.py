import httpx
from bs4 import BeautifulSoup

def read_webpage(url: str) -> str:
    """Fetch and extract readable text from a web page."""
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:8000]
    except Exception as e:
        return f"Could not read page: {e}"
