"""
steganography.py — LSB (Least Significant Bit) Image Steganography

Phase 5 & 7 helper module.

Each byte of the payload is spread across pixel channels by replacing
the least significant bits of each channel value based on the selected bit depth (1 to 3 BPP).
"""

import numpy as np
from PIL import Image
import skimage.metrics


# ─── Adaptive Steganography Helper ──────────────────────────────────────────

def get_adaptive_pixel_indices(arr: np.ndarray, bit_depth: int) -> list[int]:
    """
    Sort 32x32 image blocks by Laplacian variance (texture density) descending,
    and return the flat channel indices in that sorted order.
    The variance is calculated after clearing the payload bits (LSBs) to ensure
    the block ordering is identical for both cover and stego images.
    """
    h, w, c = arr.shape
    block_size = 32
    blocks_y = h // block_size
    blocks_x = w // block_size

    # Clear payload bits to make variance calculation independent of the payload
    mask_val = (1 << bit_depth) - 1
    arr_clean = arr & (255 - mask_val)

    # Convert to grayscale using luminance formula
    r, g, b = arr_clean[:, :, 0], arr_clean[:, :, 1], arr_clean[:, :, 2]
    gray_arr = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.int16)

    block_scores = []
    for y in range(blocks_y):
        for x in range(blocks_x):
            ys = y * block_size
            ye = ys + block_size
            xs = x * block_size
            xe = xs + block_size

            block_gray = gray_arr[ys:ye, xs:xe]

            if block_gray.shape[0] > 2 and block_gray.shape[1] > 2:
                local_lap = (
                    block_gray[1:-1, 1:-1] * 4
                    - block_gray[:-2, 1:-1]
                    - block_gray[2:, 1:-1]
                    - block_gray[1:-1, :-2]
                    - block_gray[1:-1, 2:]
                )
                local_var = float(np.var(local_lap))
            else:
                local_var = 0.0

            block_scores.append((local_var, y, x))

    # Sort blocks by texture complexity descending
    block_scores.sort(key=lambda item: item[0], reverse=True)

    # Collect flat channel indices for the sorted blocks
    indices = []
    for _, by, bx in block_scores:
        ys = by * block_size
        ye = ys + block_size
        xs = bx * block_size
        xe = xs + block_size

        for r in range(ys, ye):
            row_offset = r * w * 3
            for col in range(xs, xe):
                pixel_offset = row_offset + col * 3
                for ch in range(3):
                    indices.append(pixel_offset + ch)

    return indices


# ─── Embed ────────────────────────────────────────────────────────────────────

def embed(image: Image.Image, payload: bytes, bit_depth: int = 1) -> Image.Image:
    """
    Embed *payload* bytes into *image* using `bit_depth` LSBs per channel.
    Fills pixels in high-texture complexity blocks first.
    """
    if bit_depth not in (1, 2, 3):
        raise ValueError("Bit depth must be 1, 2, or 3.")

    img = image.convert("RGB")
    arr = np.array(img, dtype=np.uint8)

    indices = get_adaptive_pixel_indices(arr, bit_depth)
    capacity_bits = len(indices) * bit_depth
    required_bits = len(payload) * 8

    if required_bits > capacity_bits:
        raise ValueError(
            f"Adaptive capacity {capacity_bits} bits is smaller than "
            f"payload {required_bits} bits at depth {bit_depth}. Use a larger image or increase depth."
        )

    flat = arr.flatten().copy()
    
    # Unpack payload bytes to bits (MSB first per byte)
    payload_bits = []
    for byte in payload:
        for shift in range(7, -1, -1):
            payload_bits.append((byte >> shift) & 1)
            
    num_bits = len(payload_bits)
    mask = (1 << bit_depth) - 1
    inv_mask = ~mask & 0xFF
    
    bit_pos = 0
    idx = 0
    
    while bit_pos < num_bits:
        chunk_size = min(bit_depth, num_bits - bit_pos)
        val = 0
        for b in range(chunk_size):
            val = (val << 1) | payload_bits[bit_pos + b]
            
        if chunk_size < bit_depth:
            # Pad with 0s if chunk is incomplete
            val = val << (bit_depth - chunk_size)
            
        pixel_idx = indices[idx]
        flat[pixel_idx] = (flat[pixel_idx] & inv_mask) | val
        bit_pos += chunk_size
        idx += 1
        
    stego_arr = flat.reshape(arr.shape)
    return Image.fromarray(stego_arr, mode="RGB")


# ─── Extract ─────────────────────────────────────────────────────────────────

def extract(image: Image.Image, num_bytes: int, bit_depth: int = 1) -> bytes:
    """
    Extract *num_bytes* bytes from the LSBs of *image* with `bit_depth` bits per channel
    using the adaptive block ordering map.
    """
    if bit_depth not in (1, 2, 3):
        raise ValueError("Bit depth must be 1, 2, or 3.")

    img = image.convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    flat = arr.flatten()

    indices = get_adaptive_pixel_indices(arr, bit_depth)
    required_bits = num_bytes * 8
    max_bits = len(indices) * bit_depth
    if required_bits > max_bits:
        raise ValueError(
            f"Required bits ({required_bits}) exceeds maximum image capacity ({max_bits})."
        )
    
    mask = (1 << bit_depth) - 1
    
    bit_list = []
    idx = 0
    
    while len(bit_list) < required_bits:
        pixel_idx = indices[idx]
        val = flat[pixel_idx] & mask
        # Extract bit_depth bits, MSB first
        for b in range(bit_depth - 1, -1, -1):
            bit = (val >> b) & 1
            bit_list.append(bit)
        idx += 1
        
    # Trim to exactly required_bits
    bit_list = bit_list[:required_bits]
    
    # Pack bits back into bytes
    result = bytearray()
    for i in range(0, len(bit_list), 8):
        byte_bits = bit_list[i:i+8]
        byte = 0
        for bit in byte_bits:
            byte = (byte << 1) | bit
        result.append(byte)
        
    return bytes(result)


# ─── Utility ──────────────────────────────────────────────────────────────────

def max_payload_bytes(image: Image.Image, bit_depth: int = 1) -> int:
    """Return the maximum number of bytes that can be hidden in *image* at the specified bit depth."""
    img = image.convert("RGB")
    arr = np.array(img)
    indices = get_adaptive_pixel_indices(arr, bit_depth)
    return (len(indices) * bit_depth) // 8


def calculate_image_metrics(cover_img: Image.Image, stego_img: Image.Image) -> tuple[float, float, float]:
    """Calculate MSE, PSNR and SSIM between the cover and stego images, protecting against infinite values."""
    cover_arr = np.array(cover_img.convert("RGB"))
    stego_arr = np.array(stego_img.convert("RGB"))
    
    # Calculate MSE
    try:
        mse = float(np.mean((cover_arr.astype(np.float64) - stego_arr.astype(np.float64)) ** 2))
    except Exception:
        mse = 0.0

    # If they are exactly identical (e.g. clean cover and no payload changed, or perfect match)
    if np.array_equal(cover_arr, stego_arr):
        return 0.0, 999.0, 1.0
        
    try:
        psnr = float(skimage.metrics.peak_signal_noise_ratio(cover_arr, stego_arr))
        if np.isinf(psnr) or np.isnan(psnr):
            psnr = 999.0
    except Exception:
        psnr = 999.0
        
    try:
        ssim = float(skimage.metrics.structural_similarity(cover_arr, stego_arr, channel_axis=2))
        if np.isnan(ssim):
            ssim = 1.0
    except Exception:
        ssim = 1.0
        
    return mse, psnr, ssim


def calculate_chi_square_detector(image: Image.Image) -> float:
    """
    Performs Chi-Square steganalysis to detect LSB embedding.
    Returns a probability (0.0 to 1.0) of stego presence.
    """
    import math
    
    # Convert image to grayscale array
    arr = np.array(image.convert("L")).flatten()
    
    # Calculate histogram for values 0..255
    counts, _ = np.histogram(arr, bins=256, range=(0, 256))
    
    chi_sq = 0.0
    k = 0
    
    for i in range(128):
        y1 = float(counts[2 * i])
        y2 = float(counts[2 * i + 1])
        expected = (y1 + y2) / 2.0
        
        if expected > 5.0:  # Only evaluate categories with sufficient samples
            chi_sq += ((y1 - expected) ** 2) / expected
            chi_sq += ((y2 - expected) ** 2) / expected
            k += 1
            
    if k <= 1:
        return 0.0
        
    df = k - 1
    
    # Wilson-Hilferty approximation of Chi-Square CDF
    try:
        ratio = chi_sq / df
        if ratio <= 0:
            return 1.0  # Perfect symmetry => 100% stego probability
            
        z = ((ratio ** (1.0/3.0)) - (1.0 - 2.0/(9.0 * df))) / math.sqrt(2.0/(9.0 * df))
        # Standard normal CDF
        p_val = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        # Stego probability is high when p_val is close to 0 (PoVs are highly symmetric)
        stego_prob = 1.0 - p_val
        return float(max(0.0, min(1.0, stego_prob)))
    except Exception:
        return 0.0


def get_grayscale_histogram(image: Image.Image) -> list[int]:
    """Calculate the 256-bin grayscale intensity histogram of the image."""
    arr = np.array(image.convert("L")).flatten()
    counts, _ = np.histogram(arr, bins=256, range=(0, 256))
    return counts.tolist()

