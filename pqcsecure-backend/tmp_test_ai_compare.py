import io
from PIL import Image
import importlib
import app as backend_app
importlib.reload(backend_app)
client = backend_app.app.test_client()
# create small cover and stego images
cover = Image.new('RGB', (128,128), color=(120,120,120))
stego = Image.new('RGB', (128,128), color=(120,120,120))
# try embed
import steganography
try:
    stego = steganography.embed(cover, b'X'*1024, bit_depth=1)
except Exception:
    pass
cover_buf = io.BytesIO(); cover.save(cover_buf, format='PNG'); cover_buf.seek(0)
stego_buf = io.BytesIO(); stego.save(stego_buf, format='PNG'); stego_buf.seek(0)
resp = client.post('/api/ai-compare', data={'cover_image': (cover_buf, 'cover.png'), 'stego_image': (stego_buf, 'stego.png')}, content_type='multipart/form-data')
print('status', resp.status_code)
print(resp.get_data(as_text=True))
