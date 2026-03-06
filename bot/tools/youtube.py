import os
import re
from youtube_transcript_api import YouTubeTranscriptApi


def _extract_video_id(url: str):
    m = re.search(r"(?:v=|youtu\.be/)([^&\n?#]+)", url)
    return m.group(1) if m else None


_COOKIES_PATH = "/app/youtube_cookies.txt"


def _transcript_via_ytdlp(video_id: str) -> str:
    """Fetch transcript using yt-dlp (better at bypassing IP blocks)."""
    import yt_dlp
    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "ru", "all"],
        "quiet": True,
        "no_warnings": True,
    }
    if os.path.exists(_COOKIES_PATH):
        ydl_opts["cookiefile"] = _COOKIES_PATH
    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # Try to get subtitle text from info dict
    subtitles = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}
    all_subs = {**auto_subs, **subtitles}

    for lang in ["en", "ru"] + list(all_subs.keys()):
        if lang not in all_subs:
            continue
        formats = all_subs[lang]
        # Prefer json3 or srv1 formats which have clean text
        for fmt in formats:
            if fmt.get("ext") in ("json3", "srv1", "ttml", "vtt"):
                import urllib.request
                try:
                    with urllib.request.urlopen(fmt["url"], timeout=10) as r:
                        content = r.read().decode("utf-8")
                    # Strip XML/VTT tags
                    text = re.sub(r"<[^>]+>", " ", content)
                    text = re.sub(r"\s+", " ", text).strip()
                    # Remove timecode lines from VTT
                    lines = [l for l in text.splitlines()
                             if not re.match(r"^\d{2}:\d{2}", l) and l.strip()]
                    return " ".join(lines)[:8000]
                except Exception:
                    continue
    return ""


def _make_api():
    ws_user = os.getenv("WEBSHARE_PROXY_USERNAME")
    ws_pass = os.getenv("WEBSHARE_PROXY_PASSWORD")
    if ws_user and ws_pass:
        from youtube_transcript_api.proxies import WebshareProxyConfig
        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(proxy_username=ws_user, proxy_password=ws_pass)
        )
    proxy_url = os.getenv("YOUTUBE_PROXY_URL")
    if proxy_url:
        from youtube_transcript_api.proxies import GenericProxyConfig
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)
        )
    return YouTubeTranscriptApi()


def _transcript_via_api(video_id: str) -> str:
    api = _make_api()
    transcript_list = api.list(video_id)
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
        return ""
    snippets = transcript.fetch()
    return " ".join(s.text for s in snippets)[:8000]


def get_youtube_transcript(url: str) -> str:
    """Get the transcript of a YouTube video and return it for summarization."""
    vid = _extract_video_id(url)
    if not vid:
        return "Could not extract video ID from URL."

    # Try yt-dlp first (better at bypassing cloud IP blocks)
    try:
        text = _transcript_via_ytdlp(vid)
        if text:
            return text
    except Exception:
        pass

    # Fall back to youtube-transcript-api
    try:
        text = _transcript_via_api(vid)
        if text:
            return text
    except Exception as e:
        return f"Transcript unavailable: {e}"

    return "No transcript available for this video."
