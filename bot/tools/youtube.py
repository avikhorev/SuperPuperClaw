import os
import re
from youtube_transcript_api import YouTubeTranscriptApi


def _extract_video_id(url: str):
    m = re.search(r"(?:v=|youtu\.be/)([^&\n?#]+)", url)
    return m.group(1) if m else None


_COOKIES_PATH = "/app/youtube_cookies.txt"


def _parse_vtt(content: str) -> str:
    lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or "-->" in line:
            continue
        if re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line:
            lines.append(line)
    deduped = [lines[i] for i in range(len(lines)) if i == 0 or lines[i] != lines[i-1]]
    return " ".join(deduped)


def _transcript_via_ytdlp(video_id: str) -> str:
    """Fetch transcript using yt-dlp info extraction + direct subtitle URL fetch."""
    import http.cookiejar
    import urllib.request
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    # Don't pass cookiefile to yt-dlp — it tries to write back on exit and
    # the mounted file is not writable by the bot user. We use the cookie jar
    # separately for fetching subtitle URLs below.
    ydl_opts = {"quiet": True, "no_warnings": True}
    p = _proxy_url()
    if p:
        ydl_opts["proxy"] = p

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    subtitles = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}
    # Prefer manual subtitles, fall back to auto
    all_subs = {**auto_subs, **subtitles}

    # Build cookie jar for fetching subtitle URLs
    jar = http.cookiejar.MozillaCookieJar()
    if os.path.exists(_COOKIES_PATH):
        try:
            jar.load(_COOKIES_PATH, ignore_discard=True, ignore_expires=True)
        except Exception:
            pass
    handlers = [urllib.request.HTTPCookieProcessor(jar)]
    p = _proxy_url()
    if p:
        handlers.append(urllib.request.ProxyHandler({"http": p, "https": p}))
    opener = urllib.request.build_opener(*handlers)

    try:
        for lang in ["en", "ru"] + list(all_subs.keys()):
            if lang not in all_subs:
                continue
            for fmt in all_subs[lang]:
                if fmt.get("ext") in ("vtt", "srv1", "ttml"):
                    try:
                        req = urllib.request.Request(fmt["url"], headers={"User-Agent": "Mozilla/5.0"})
                        with opener.open(req, timeout=10) as r:
                            content = r.read().decode("utf-8")
                        text = _parse_vtt(content)
                        if text:
                            return text[:8000]
                    except Exception:
                        continue
        return ""


def _proxy_url() -> str:
    """Build proxy URL from env vars. Returns empty string if not configured."""
    ws_user = os.getenv("WEBSHARE_PROXY_USERNAME")
    ws_pass = os.getenv("WEBSHARE_PROXY_PASSWORD")
    ws_host = os.getenv("WEBSHARE_PROXY_HOST", "")
    ws_port = os.getenv("WEBSHARE_PROXY_PORT", "")
    if ws_user and ws_pass and ws_host and ws_port:
        return f"http://{ws_user}:{ws_pass}@{ws_host}:{ws_port}"
    return os.getenv("YOUTUBE_PROXY_URL", "")


def _make_api():
    url = _proxy_url()
    if url:
        from youtube_transcript_api.proxies import GenericProxyConfig
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(http_url=url, https_url=url)
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
