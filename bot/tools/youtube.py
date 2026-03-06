import os
import re
from youtube_transcript_api import YouTubeTranscriptApi


def _make_api():
    proxy_url = os.getenv("YOUTUBE_PROXY_URL")  # e.g. http://user:pass@host:port
    if proxy_url:
        from youtube_transcript_api.proxies import GenericProxyConfig
        proxy_config = GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)
        return YouTubeTranscriptApi(proxy_config=proxy_config)
    return YouTubeTranscriptApi()


def get_youtube_transcript(url: str) -> str:
    """Get the transcript of a YouTube video and return it for summarization."""
    try:
        video_id = re.search(r"(?:v=|youtu\.be/)([^&\n?#]+)", url)
        if not video_id:
            return "Could not extract video ID from URL."
        vid = video_id.group(1)

        api = _make_api()
        transcript_list = api.list(vid)

        # Prefer manual captions over auto-generated
        transcript = None
        for t in transcript_list:
            if not t.is_generated:
                transcript = t
                break
        if transcript is None:
            for t in transcript_list:
                transcript = t
                break

        if transcript is None:
            return "No transcript available for this video."

        snippets = transcript.fetch()
        text = " ".join(s.text for s in snippets)
        return text[:8000]
    except Exception as e:
        return f"Transcript unavailable: {e}"
