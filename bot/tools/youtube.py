import os
import re
from youtube_transcript_api import YouTubeTranscriptApi


def _extract_video_id(url: str):
    m = re.search(r"(?:v=|youtu\.be/)([^&\n?#]+)", url)
    return m.group(1) if m else None


_COOKIES_PATH = "/app/youtube_cookies.txt"


def _transcript_via_ytdlp(video_id: str) -> str:
    """Fetch transcript using yt-dlp with cookies."""
    import tempfile
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "ru"],
            "subtitlesformat": "vtt",
            "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        if os.path.exists(_COOKIES_PATH):
            ydl_opts["cookiefile"] = _COOKIES_PATH

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the downloaded .vtt file
        for fname in os.listdir(tmpdir):
            if fname.endswith(".vtt"):
                with open(os.path.join(tmpdir, fname), encoding="utf-8") as f:
                    content = f.read()
                # Strip VTT headers, timecodes, and tags
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
                # Deduplicate consecutive identical lines
                deduped = [lines[i] for i in range(len(lines))
                           if i == 0 or lines[i] != lines[i-1]]
                return " ".join(deduped)[:8000]
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
