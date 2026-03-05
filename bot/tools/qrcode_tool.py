import io
import qrcode

def generate_qr(url: str) -> bytes:
    """Generate a QR code PNG image for a URL. Returns PNG bytes."""
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
