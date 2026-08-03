import io
from PIL import Image
import importlib


def test_ai_compare_endpoint_basic(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("REQUIRE_HTTPS", raising=False)
    import app as backend_app
    importlib.reload(backend_app)

    client = backend_app.app.test_client()

    cover = Image.new('RGB', (128, 128), color=(120, 120, 120))
    stego = Image.new('RGB', (128, 128), color=(120, 120, 120))

    # try to embed a small payload
    try:
        import steganography
        stego = steganography.embed(cover, b'X'*1024, bit_depth=1)
    except Exception:
        pass

    buf1 = io.BytesIO(); cover.save(buf1, format='PNG'); buf1.seek(0)
    buf2 = io.BytesIO(); stego.save(buf2, format='PNG'); buf2.seek(0)

    resp = client.post('/api/ai-compare', data={'cover_image': (buf1, 'cover.png'), 'stego_image': (buf2, 'stego.png')}, content_type='multipart/form-data')
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert 'cover' in data and 'stego' in data
