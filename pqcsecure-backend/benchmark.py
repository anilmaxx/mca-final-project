import time
import numpy as np
import os
import io
import hashlib
from PIL import Image
from Crypto.PublicKey import RSA, ECC
from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes
from kyber_py.ml_kem import ML_KEM_768
import steganography
import crypto

def run_kem_benchmark(iterations=100):
    """
    Benchmarks ML-KEM-768, RSA-2048, and X25519 (ECDH) key exchanges.
    If iterations is large (e.g., 1000), we cap RSA KeyGen iterations at 10
    to avoid extremely long execution times (as RSA KeyGen takes ~2.6 seconds per run),
    but still run Encaps/Decaps for the full iteration count.
    """
    results = {}
    
    # ─── ML-KEM-768 ───
    mlkem_keygen = []
    mlkem_encaps = []
    mlkem_decaps = []
    
    # Warmup
    pk, sk = ML_KEM_768.keygen()
    ss, ct = ML_KEM_768.encaps(pk)
    _ = ML_KEM_768.decaps(sk, ct)
    
    for _ in range(iterations):
        t0 = time.perf_counter()
        pk, sk = ML_KEM_768.keygen()
        mlkem_keygen.append((time.perf_counter() - t0) * 1000) # ms
        
        t0 = time.perf_counter()
        ss, ct = ML_KEM_768.encaps(pk)
        mlkem_encaps.append((time.perf_counter() - t0) * 1000)
        
        t0 = time.perf_counter()
        _ = ML_KEM_768.decaps(sk, ct)
        mlkem_decaps.append((time.perf_counter() - t0) * 1000)
        
    results["ML-KEM-768"] = {
        "keygen": {
            "mean": float(np.mean(mlkem_keygen)),
            "median": float(np.median(mlkem_keygen)),
            "std": float(np.std(mlkem_keygen)),
        },
        "encaps": {
            "mean": float(np.mean(mlkem_encaps)),
            "median": float(np.median(mlkem_encaps)),
            "std": float(np.std(mlkem_encaps)),
        },
        "decaps": {
            "mean": float(np.mean(mlkem_decaps)),
            "median": float(np.median(mlkem_decaps)),
            "std": float(np.std(mlkem_decaps)),
        },
        "ciphertext_size": len(ct),
        "public_key_size": len(pk),
        "security_level": "Post-Quantum (Lattice-Based, Category 3 / FIPS 203)",
    }
    
    # ─── X25519 (ECDH) ───
    ecdh_keygen = []
    ecdh_encaps = []
    ecdh_decaps = []
    
    # Warmup
    rec_key = ECC.generate(curve='curve25519')
    rec_pub = rec_key.public_key().export_key(format='DER')
    
    rec_pub_key = ECC.import_key(rec_pub)
    eph_key = ECC.generate(curve='curve25519')
    shared_point = rec_pub_key.pointQ * eph_key.d
    ss = hashlib.sha256(int(shared_point.x).to_bytes(32, byteorder='big')).digest()
    ct_ecdh = eph_key.public_key().export_key(format='DER')
    _ = rec_key.pointQ * rec_key.d # dummy
    
    for _ in range(iterations):
        t0 = time.perf_counter()
        rec_key = ECC.generate(curve='curve25519')
        ecdh_keygen.append((time.perf_counter() - t0) * 1000)
        
        rec_pub_bytes = rec_key.public_key().export_key(format='DER')
        
        t0 = time.perf_counter()
        rec_pub_key = ECC.import_key(rec_pub_bytes)
        eph_key = ECC.generate(curve='curve25519')
        shared_point = rec_pub_key.pointQ * eph_key.d
        ss_sender = hashlib.sha256(int(shared_point.x).to_bytes(32, byteorder='big')).digest()
        ct_ecdh = eph_key.public_key().export_key(format='DER')
        ecdh_encaps.append((time.perf_counter() - t0) * 1000)
        
        t0 = time.perf_counter()
        eph_pub_key = ECC.import_key(ct_ecdh)
        shared_point_rec = eph_pub_key.pointQ * rec_key.d
        ss_receiver = hashlib.sha256(int(shared_point_rec.x).to_bytes(32, byteorder='big')).digest()
        ecdh_decaps.append((time.perf_counter() - t0) * 1000)
        
    results["X25519"] = {
        "keygen": {
            "mean": float(np.mean(ecdh_keygen)),
            "median": float(np.median(ecdh_keygen)),
            "std": float(np.std(ecdh_keygen)),
        },
        "encaps": {
            "mean": float(np.mean(ecdh_encaps)),
            "median": float(np.median(ecdh_encaps)),
            "std": float(np.std(ecdh_encaps)),
        },
        "decaps": {
            "mean": float(np.mean(ecdh_decaps)),
            "median": float(np.median(ecdh_decaps)),
            "std": float(np.std(ecdh_decaps)),
        },
        "ciphertext_size": len(ct_ecdh),
        "public_key_size": len(rec_pub_bytes),
        "security_level": "Classical (Elliptic Curve, 128-bit equivalent)",
    }
    
    # ─── RSA-2048 ───
    rsa_keygen = []
    rsa_encaps = []
    rsa_decaps = []
    
    # Generate one key pair for the encaps/decaps loop to avoid generate() inside encaps loop
    warmup_key = RSA.generate(2048)
    warmup_pub = warmup_key.publickey()
    
    # Cap RSA KeyGen iterations at 10 to prevent hanging
    keygen_iterations = min(iterations, 10)
    for _ in range(keygen_iterations):
        t0 = time.perf_counter()
        key = RSA.generate(2048)
        rsa_keygen.append((time.perf_counter() - t0) * 1000)
        
    # Encaps and decaps 1000 times
    cipher_rsa_enc = PKCS1_OAEP.new(warmup_pub, hashAlgo=SHA256)
    cipher_rsa_dec = PKCS1_OAEP.new(warmup_key, hashAlgo=SHA256)
    session_key = get_random_bytes(32)
    
    for _ in range(iterations):
        t0 = time.perf_counter()
        ct_rsa = cipher_rsa_enc.encrypt(session_key)
        rsa_encaps.append((time.perf_counter() - t0) * 1000)
        
        t0 = time.perf_counter()
        _ = cipher_rsa_dec.decrypt(ct_rsa)
        rsa_decaps.append((time.perf_counter() - t0) * 1000)
        
    results["RSA-2048"] = {
        "keygen": {
            "mean": float(np.mean(rsa_keygen)),
            "median": float(np.median(rsa_keygen)),
            "std": float(np.std(rsa_keygen)),
            "note": f"Sample size limited to {keygen_iterations} due to high CPU latency" if keygen_iterations < iterations else ""
        },
        "encaps": {
            "mean": float(np.mean(rsa_encaps)),
            "median": float(np.median(rsa_encaps)),
            "std": float(np.std(rsa_encaps)),
        },
        "decaps": {
            "mean": float(np.mean(rsa_decaps)),
            "median": float(np.median(rsa_decaps)),
            "std": float(np.std(rsa_decaps)),
        },
        "ciphertext_size": 256, # 2048 bits
        "public_key_size": len(warmup_pub.export_key(format='DER')),
        "security_level": "Classical (Factorization, 112-bit equivalent)",
    }
    
    return results

def run_symmetric_benchmark():
    """
    Measures AES-GCM throughput for payload sizes of 1 KB, 1 MB, and 10 MB.
    """
    sizes = {
        "1KB": 1024,
        "1MB": 1024 * 1024,
        "10MB": 1024 * 1024 * 10
    }
    
    results = {}
    key = get_random_bytes(32)
    
    for size_name, num_bytes in sizes.items():
        data = get_random_bytes(num_bytes)
        
        # Encrypt
        t0 = time.perf_counter()
        iv = get_random_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        ciphertext, auth_tag = cipher.encrypt_and_digest(data)
        enc_time = time.perf_counter() - t0
        
        # Decrypt
        t0 = time.perf_counter()
        cipher_dec = AES.new(key, AES.MODE_GCM, nonce=iv)
        _ = cipher_dec.decrypt_and_verify(ciphertext, auth_tag)
        dec_time = time.perf_counter() - t0
        
        results[size_name] = {
            "bytes": num_bytes,
            "encrypt_time_ms": enc_time * 1000,
            "decrypt_time_ms": dec_time * 1000,
            "throughput_encrypt_mbs": (num_bytes / (1024 * 1024)) / enc_time,
            "throughput_decrypt_mbs": (num_bytes / (1024 * 1024)) / dec_time,
        }
        
    return results

def run_stego_benchmark(payload_bytes_len=1024):
    """
    Runs LSB steganography benchmarks on a representative set of 30 test images
    of varying types (styles) and resolutions.
    """
    payload = get_random_bytes(payload_bytes_len)
    
    # Define resolutions and styles to generate 30 distinct test images
    resolutions = [128, 256, 512]
    styles = ["Synthetic", "Texture", "Natural"]
    formats = ["PNG", "BMP", "JPEG"]
    
    results = []
    
    for i in range(30):
        res = resolutions[i % len(resolutions)]
        style = styles[(i // 3) % len(styles)]
        fmt = formats[i % len(formats)]
        
        # Generate image based on style
        img_arr = np.zeros((res, res, 3), dtype=np.uint8)
        if style == "Synthetic":
            # Geometric shapes on solid slate background
            img_arr[:, :] = [15, 23, 42]
            img_arr[res//4:3*res//4, res//4:3*res//4] = [59, 130, 246]
        elif style == "Texture":
            # Sinusoidal texture pattern
            x = np.linspace(0, (10 + i) * np.pi, res)
            y = np.linspace(0, (10 + i) * np.pi, res)
            xx, yy = np.meshgrid(x, y)
            pattern = (np.sin(xx) * np.cos(yy) + 1) * 127.5
            img_arr[:, :, 0] = pattern.astype(np.uint8)
            img_arr[:, :, 1] = (pattern * 0.7).astype(np.uint8)
            img_arr[:, :, 2] = (255 - pattern * 0.5).astype(np.uint8)
        else:
            # Soft linear gradient representing photographic gradients
            for y in range(res):
                img_arr[y, :, 0] = int(255 * (y / res))
                img_arr[y, :, 1] = int(255 * (1 - y / res))
                img_arr[y, :, 2] = int(128 * (y / res))
                
        cover_img = Image.fromarray(img_arr, mode="RGB")
        
        # Stego LSB embedding
        try:
            stego_img = steganography.embed(cover_img, payload)
            psnr, ssim = steganography.calculate_image_metrics(cover_img, stego_img)
            bpp = (payload_bytes_len * 8) / (res * res)
            
            # Simulated attacks and robustness checking
            # 1. Save and reload stego as PNG (lossless) - recovery should succeed
            buf_png = io.BytesIO()
            stego_img.save(buf_png, format="PNG")
            buf_png.seek(0)
            loaded_png = Image.open(buf_png)
            extracted_png = steganography.extract(loaded_png, payload_bytes_len)
            recovery_png = (extracted_png == payload)
            
            # 2. JPEG recompression attack (simulate lossy compression)
            buf_jpg_95 = io.BytesIO()
            stego_img.save(buf_jpg_95, format="JPEG", quality=95)
            buf_jpg_95.seek(0)
            loaded_jpg_95 = Image.open(buf_jpg_95)
            try:
                extracted_jpg_95 = steganography.extract(loaded_jpg_95, payload_bytes_len)
                recovery_jpeg_95 = (extracted_jpg_95 == payload)
            except Exception:
                recovery_jpeg_95 = False
                
            buf_jpg_75 = io.BytesIO()
            stego_img.save(buf_jpg_75, format="JPEG", quality=75)
            buf_jpg_75.seek(0)
            loaded_jpg_75 = Image.open(buf_jpg_75)
            try:
                extracted_jpg_75 = steganography.extract(loaded_jpg_75, payload_bytes_len)
                recovery_jpeg_75 = (extracted_jpg_75 == payload)
            except Exception:
                recovery_jpeg_75 = False
                
            # 3. Resizing attack (resize down to 90% and back, or check if extract works)
            res_img = stego_img.resize((int(res * 0.9), int(res * 0.9)), Image.Resampling.BILINEAR)
            res_img_back = res_img.resize((res, res), Image.Resampling.BILINEAR)
            try:
                extracted_resized = steganography.extract(res_img_back, payload_bytes_len)
                recovery_resized = (extracted_resized == payload)
            except Exception:
                recovery_resized = False
                
            results.append({
                "id": i + 1,
                "resolution": f"{res}x{res}",
                "style": style,
                "format": fmt,
                "psnr": float(psnr),
                "ssim": float(ssim),
                "bpp": float(bpp),
                "recovery_raw": bool(recovery_png),
                "recovery_jpeg_95": bool(recovery_jpeg_95),
                "recovery_jpeg_75": bool(recovery_jpeg_75),
                "recovery_resized": bool(recovery_resized),
            })
            
        except Exception as e:
            # Payload too large for cover image capacity
            results.append({
                "id": i + 1,
                "resolution": f"{res}x{res}",
                "style": style,
                "format": fmt,
                "error": str(e),
                "psnr": 0,
                "ssim": 0,
                "bpp": 0,
                "recovery_raw": False,
                "recovery_jpeg_95": False,
                "recovery_jpeg_75": False,
                "recovery_resized": False,
            })
            
    return results

def run_end_to_end_benchmark():
    """
    Compares the end-to-end latency of the stego pipeline
    (KEM KeyGen + KEM Encaps + AES GCM Encrypt + LSB Embed)
    vs. the direct ciphertext sending baseline (AES GCM Encrypt + no stego).
    """
    msg = get_random_bytes(100)
    cover_img = Image.new("RGB", (512, 512), color=(15, 23, 42))
    
    # ── Path A: Stego Flow ──
    t_start = time.perf_counter()
    ek, dk = crypto.generate_keypair()
    ss, ct = crypto.encapsulate(ek)
    iv, tag, ciphertext = crypto.aes_encrypt(ss, msg)
    payload = crypto.build_payload(ct, iv, tag, ciphertext)
    stego = steganography.embed(cover_img, payload)
    
    # Extraction/Decryption
    header_bytes = steganography.extract(stego, crypto.header_size())
    import struct
    kyber_ct_len, enc_msg_len, iv_len, tag_len = struct.unpack(">IIBB", header_bytes)
    total_payload = crypto.header_size() + kyber_ct_len + iv_len + tag_len + enc_msg_len
    payload_extracted = steganography.extract(stego, total_payload)
    kyber_ct, iv_ex, tag_ex, ct_ex = crypto.parse_payload(payload_extracted)
    ss_dec = crypto.decapsulate(dk, kyber_ct)
    _ = crypto.aes_decrypt(ss_dec, iv_ex, tag_ex, ct_ex)
    t_stego_flow = (time.perf_counter() - t_start) * 1000
    
    # ── Path B: Direct Ciphertext Flow (No Steganography) ──
    t_start = time.perf_counter()
    ek, dk = crypto.generate_keypair()
    ss, ct = crypto.encapsulate(ek)
    iv, tag, ciphertext = crypto.aes_encrypt(ss, msg)
    payload = crypto.build_payload(ct, iv, tag, ciphertext)
    # Simulate direct network send (no embedding, no extraction)
    kyber_ct, iv_ex, tag_ex, ct_ex = crypto.parse_payload(payload)
    ss_dec = crypto.decapsulate(dk, kyber_ct)
    _ = crypto.aes_decrypt(ss_dec, iv_ex, tag_ex, ct_ex)
    t_direct_flow = (time.perf_counter() - t_start) * 1000
    
    return {
        "stego_flow_ms": float(t_stego_flow),
        "direct_flow_ms": float(t_direct_flow),
        "overhead_ms": float(t_stego_flow - t_direct_flow),
        "overhead_percentage": float(((t_stego_flow - t_direct_flow) / t_direct_flow) * 100) if t_direct_flow > 0 else 0
    }
