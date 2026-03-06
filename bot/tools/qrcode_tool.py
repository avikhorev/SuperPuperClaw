from urllib.parse import quote

def generate_qr(url: str) -> str:
    """Generate a QR code for a URL. Returns a photo URL to send as an image."""
    image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(url, safe='')}"
    return f"PHOTO_URL:{image_url}"
