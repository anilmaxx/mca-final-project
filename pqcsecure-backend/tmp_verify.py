import io
import sys
import numpy as np
from PIL import Image
import app as backend_app
import pytest

client = backend_app.app.test_client()
cover_arr = np.full((128, 128, 3), 120, dtype=np.uint8)
cover = Image.fromarray(cover_arr, mode='RGB')
buf_cover = io.BytesIO()
cover.save(buf_cover, format='PNG')
buf_cover.seek(0)

resp = client.post('/api/ai-detect', data={'image': (io.BytesIO(buf_cover.getvalue()), 'cover.png')}, content_type='multipart/form-data')
print('detect_status', resp.status_code)
print('detect_payload_keys', sorted(resp.get_json().keys()))
print('feature_count', len(resp.get_json().get('features', {})))

exit_code = pytest.main(['tests/test_ai_compare.py', '-q'])
sys.exit(exit_code)
