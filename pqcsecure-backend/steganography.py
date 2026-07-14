"""
steganography.py — LSB (Least Significant Bit) Image Steganography

Phase 5 & 7 helper module.

Each byte of the payload is spread across pixel channels by replacing
the least significant bits of each channel value based on the selected bit depth (1 to 3 BPP).
"""

import numpy as np
from PIL import Image
import skimage.metrics


# ─── Embed ────────────────────────────────────────────────────────────────────

def embed(image: Image.Image, payload: bytes, bit_depth: int = 1) -> Image.Image:
    """
    Embed *payload* bytes into *image* using `bit_depth` LSBs per channel.

    Parameters
    ----------
    image     : PIL Image
    payload   : bytes to hide
    bit_depth : int (1, 2, or 3)

    Returns
    -------
    PIL Image with payload hidden in pixel LSBs (PNG-safe, lossless)
    """
    if bit_depth not in (1, 2, 3):
        raise ValueError("Bit depth must be 1, 2, or 3.")

    img = image.convert("RGB")
    arr = np.array(img, dtype=np.uint8)

    capacity_bits = arr.size * bit_depth
    required_bits = len(payload) * 8

    if required_bits > capacity_bits:
        raise ValueError(
            f"Image capacity {capacity_bits} bits is smaller than "
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
    pixel_idx = 0
    
    while bit_pos < num_bits:
        chunk_size = min(bit_depth, num_bits - bit_pos)
        val = 0
        for b in range(chunk_size):
            val = (val << 1) | payload_bits[bit_pos + b]
            
        if chunk_size < bit_depth:
            # Pad with 0s if chunk is incomplete
            val = val << (bit_depth - chunk_size)
            
        flat[pixel_idx] = (flat[pixel_idx] & inv_mask) | val
        bit_pos += chunk_size
        pixel_idx += 1
        
    stego_arr = flat.reshape(arr.shape)
    return Image.fromarray(stego_arr, mode="RGB")


# ─── Extract ─────────────────────────────────────────────────────────────────

def extract(image: Image.Image, num_bytes: int, bit_depth: int = 1) -> bytes:
    """
    Extract *num_bytes* bytes from the LSBs of *image* with `bit_depth` bits per channel.

    Parameters
    ----------
    image     : PIL Image containing a hidden payload
    num_bytes : exact number of bytes to extract
    bit_depth : int (1, 2, or 3)

    Returns
    -------
    bytes of length *num_bytes*
    """
    if bit_depth not in (1, 2, 3):
        raise ValueError("Bit depth must be 1, 2, or 3.")

    img = image.convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    flat = arr.flatten()

    required_bits = num_bytes * 8
    
    mask = (1 << bit_depth) - 1
    
    bit_list = []
    pixel_idx = 0
    
    while len(bit_list) < required_bits:
        val = flat[pixel_idx] & mask
        # Extract bit_depth bits, MSB first
        for b in range(bit_depth - 1, -1, -1):
            bit = (val >> b) & 1
            bit_list.append(bit)
        pixel_idx += 1
        
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
    return (arr.size * bit_depth) // 8


def calculate_image_metrics(cover_img: Image.Image, stego_img: Image.Image) -> tuple[float, float]:
    """Calculate PSNR and SSIM between the cover and stego images, protecting against infinite values."""
    cover_arr = np.array(cover_img.convert("RGB"))
    stego_arr = np.array(stego_img.convert("RGB"))
    
    # If they are exactly identical (e.g. clean cover and no payload changed, or perfect match)
    if np.array_equal(cover_arr, stego_arr):
        return 999.0, 1.0
        
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
        
    return psnr, ssim


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
