"""
crypto.py — Cryptographic helpers

Encapsulates Phase 2, 3, and 7 logic so app.py stays clean.

Algorithms
----------
- Phase 2 / 7 : ML-KEM-768 (CRYSTALS-Kyber) via kyber-py
                RSA-2048 via pycryptodome (Classical Baseline)
                X25519 (ECDH) via pycryptodome (Classical Ephemeral Baseline)
- Phase 3 / 7 : AES-256-GCM (authenticated encryption)
"""

import struct
import hashlib
from kyber_py.ml_kem import ML_KEM_768
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.PublicKey import RSA, ECC
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256


# ─── Key Generation ───────────────────────────────────────────────────────────

def generate_keypair(algorithm: str = "ML-KEM-768") -> tuple[bytes, bytes]:
    """
    Generate keypair for the specified algorithm.

    Returns
    -------
    (encapsulation_key, decapsulation_key)
    """
    if algorithm == "ML-KEM-768":
        ek, dk = ML_KEM_768.keygen()
        return ek, dk
    elif algorithm == "RSA-2048":
        key = RSA.generate(2048)
        ek = key.publickey().export_key(format='DER')
        dk = key.export_key(format='DER')
        return ek, dk
    elif algorithm == "X25519":
        key = ECC.generate(curve='curve25519')
        ek = key.public_key().export_key(format='DER')
        dk = key.export_key(format='DER')
        return ek, dk
    else:
        raise ValueError(f"Unsupported KEM algorithm: {algorithm}")


# ─── Encapsulation (Sender) ───────────────────────────────────────────────────

def encapsulate(ek: bytes, algorithm: str = "ML-KEM-768") -> tuple[bytes, bytes]:
    """
    Encapsulate a shared secret using the recipient's public key.

    Returns
    -------
    (shared_secret, ciphertext)
        shared_secret : 32 bytes
        ciphertext    : algorithm-dependent bytes
    """
    if algorithm == "ML-KEM-768":
        return ML_KEM_768.encaps(ek)
    elif algorithm == "RSA-2048":
        pub_key = RSA.import_key(ek)
        shared_secret = get_random_bytes(32)
        cipher = PKCS1_OAEP.new(pub_key, hashAlgo=SHA256)
        ciphertext = cipher.encrypt(shared_secret)
        return shared_secret, ciphertext
    elif algorithm == "X25519":
        pub_key = ECC.import_key(ek)
        eph_key = ECC.generate(curve='curve25519')
        shared_point = pub_key.pointQ * eph_key.d
        shared_secret = hashlib.sha256(int(shared_point.x).to_bytes(32, byteorder='big')).digest()
        ciphertext = eph_key.public_key().export_key(format='DER')
        return shared_secret, ciphertext
    else:
        raise ValueError(f"Unsupported KEM algorithm: {algorithm}")


# ─── Decapsulation (Receiver) ─────────────────────────────────────────────────

def decapsulate(dk: bytes, ciphertext: bytes, algorithm: str = "ML-KEM-768") -> bytes:
    """
    Recover the shared secret from ciphertext.

    Returns
    -------
    shared_secret : 32 bytes
    """
    if algorithm == "ML-KEM-768":
        return ML_KEM_768.decaps(dk, ciphertext)
    elif algorithm == "RSA-2048":
        priv_key = RSA.import_key(dk)
        cipher = PKCS1_OAEP.new(priv_key, hashAlgo=SHA256)
        return cipher.decrypt(ciphertext)
    elif algorithm == "X25519":
        priv_key = ECC.import_key(dk)
        eph_pub_key = ECC.import_key(ciphertext)
        shared_point = eph_pub_key.pointQ * priv_key.d
        return hashlib.sha256(int(shared_point.x).to_bytes(32, byteorder='big')).digest()
    else:
        raise ValueError(f"Unsupported KEM algorithm: {algorithm}")


# ─── AES-256 Encrypt ──────────────────────────────────────────────────────────

def aes_encrypt(key: bytes, plaintext: bytes, mode: str = "AES-256-GCM") -> tuple[bytes, bytes, bytes]:
    """
    Encrypt plaintext with AES-256-GCM.

    Returns
    -------
    (iv, auth_tag, ciphertext)
        iv        : IV bytes (12 bytes)
        auth_tag  : Tag bytes (16 bytes)
        ciphertext: Encrypted message bytes
    """
    if mode == "AES-256-GCM":
        iv = get_random_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        ciphertext, auth_tag = cipher.encrypt_and_digest(plaintext)
        return iv, auth_tag, ciphertext
    else:
        raise ValueError(f"Unsupported symmetric mode: {mode}")


# ─── AES-256 Decrypt ──────────────────────────────────────────────────────────

def aes_decrypt(key: bytes, iv: bytes, auth_tag: bytes, ciphertext: bytes, mode: str = "AES-256-GCM") -> bytes:
    """
    Decrypt and verify ciphertext.
    """
    if mode == "AES-256-GCM":
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        return cipher.decrypt_and_verify(ciphertext, auth_tag)
    else:
        raise ValueError(f"Unsupported symmetric mode: {mode}")


# ─── Payload Construction / Parsing ──────────────────────────────────────────

def build_payload(kem_ct: bytes, iv: bytes, auth_tag: bytes, ciphertext: bytes) -> bytes:
    """
    Pack components into a single binary payload using a dynamic header.

    Layout (bytes):
    ┌──────────────┬──────────────┬────────┬─────────┬───────────┬────────┬────────┬──────────┐
    │  kem_ct_len  │ enc_msg_len  │ iv_len │ tag_len │  kem_ct   │   IV   │  Tag   │  EncMsg  │
    │   4 bytes    │   4 bytes    │ 1 byte │ 1 byte  │ variable  │ var    │ var    │ variable │
    └──────────────┴──────────────┴────────┴─────────┴───────────┴────────┴────────┴──────────┘
    """
    header = struct.pack(">IIBB", len(kem_ct), len(ciphertext), len(iv), len(auth_tag))
    return header + kem_ct + iv + auth_tag + ciphertext


def parse_payload(payload: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    """
    Parse binary payload back into components.

    Returns
    -------
    (kem_ct, iv, auth_tag, ciphertext)
    """
    kem_ct_len, enc_msg_len, iv_len, tag_len = struct.unpack(">IIBB", payload[:10])
    offset = 10
    kem_ct = payload[offset : offset + kem_ct_len]
    offset += kem_ct_len
    iv = payload[offset : offset + iv_len]
    offset += iv_len
    auth_tag = payload[offset : offset + tag_len]
    offset += tag_len
    ciphertext = payload[offset : offset + enc_msg_len]
    return kem_ct, iv, auth_tag, ciphertext


def header_size() -> int:
    """Return byte size of the dynamic payload header (2x uint32 + 2x uint8 = 10)."""
    return 10


def export_private_key_display(dk: bytes, algorithm: str) -> str:
    """Return a displayable private key string (PEM or base64)."""
    if algorithm == "ML-KEM-768":
        import base64
        b64 = base64.b64encode(dk).decode('utf-8')
        return "-----BEGIN ML-KEM-768 PRIVATE KEY-----\n" + \
               "\n".join(b64[i:i+64] for i in range(0, len(b64), 64)) + \
               "\n-----END ML-KEM-768 PRIVATE KEY-----"
    elif algorithm == "RSA-2048":
        key = RSA.import_key(dk)
        return key.export_key(format='PEM').decode('utf-8')
    elif algorithm == "X25519":
        key = ECC.import_key(dk)
        pem = key.export_key(format='PEM')
        return pem.decode('utf-8') if isinstance(pem, bytes) else pem
    return ""
