"""Compress recipe covers before they land on the VPS."""
from utils.image_store import compress_image_bytes


def test_compress_empty_passthrough():
    assert compress_image_bytes(b"") == b""


def test_compress_shrinks_large_rgb():
    try:
        from PIL import Image
    except ImportError:
        data = b"not-an-image"
        assert compress_image_bytes(data) == data
        return
    import io

    img = Image.new("RGB", (2000, 1500), color=(40, 80, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    out = compress_image_bytes(raw)
    assert out.startswith(b"\xff\xd8")
    assert len(out) < len(raw)
