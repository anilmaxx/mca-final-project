import numpy as np
from PIL import Image
import stego_ai, steganography

cover_arr = np.full((512, 512, 3), 120, dtype=np.uint8)
cover = Image.fromarray(cover_arr, mode='RGB')
stego = steganography.embed(cover, b'X' * 8000, bit_depth=3)
print('cover_prob', stego_ai.predict_stego(cover))
print('stego_prob', stego_ai.predict_stego(stego))
print('cover_features', stego_ai.extract_stego_features(cover))
print('stego_features', stego_ai.extract_stego_features(stego))
print('chi_cover', steganography.calculate_chi_square_detector(cover))
print('chi_stego', steganography.calculate_chi_square_detector(stego))
