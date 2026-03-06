import os
import tempfile
import urllib.request
from urllib.parse import quote


def generate_qr(url: str) -> str:
    """Generate a QR code for a URL. Returns a PHOTO_FILE path to send as an image."""
    image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(url, safe='')}"
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        with urllib.request.urlopen(image_url, timeout=10) as r:
            tmp.write(r.read())
        tmp.close()
        return f"PHOTO_FILE:{tmp.name}"
    except Exception as e:
        tmp.close()
        os.unlink(tmp.name)
        return f"Could not generate QR code: {e}"
