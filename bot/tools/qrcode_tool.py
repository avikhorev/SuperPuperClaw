import io
import qrcode

def generate_qr(url: str) -> bytes:
    """Generate a QR code PNG image for a URL. Returns PNG bytes."""
    try:
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        return f"Could not generate QR code: {e}".encode()
