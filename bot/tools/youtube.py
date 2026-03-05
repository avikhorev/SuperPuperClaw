import re
from youtube_transcript_api import YouTubeTranscriptApi

def get_youtube_transcript(url: str) -> str:
    """Get the transcript of a YouTube video."""
    try:
        video_id = re.search(r"(?:v=|youtu\.be/)([^&\n?#]+)", url)
        if not video_id:
            return "Could not extract video ID from URL."
        transcript = YouTubeTranscriptApi.get_transcript(video_id.group(1))
        text = " ".join(t["text"] for t in transcript)
        return text[:6000]
    except Exception as e:
        return f"Transcript unavailable: {e}"
