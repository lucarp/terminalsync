import hashlib

import nacl.utils
from nacl.bindings import crypto_scalarmult, crypto_scalarmult_base
from nacl.secret import SecretBox
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


def generate_keypair() -> tuple[bytes, bytes]:
    """Return (private_key, public_key), each 32 bytes."""
    privkey = nacl.utils.random(32)
    pubkey = crypto_scalarmult_base(privkey)
    return privkey, bytes(pubkey)


def generate_psk() -> bytes:
    return nacl.utils.random(32)


def derive_session_key(our_privkey: bytes, their_pubkey: bytes, psk: bytes) -> bytes:
    """Derive 32-byte session key: HKDF-SHA256(X25519(priv, pub) || psk)."""
    dh_secret = bytes(crypto_scalarmult(our_privkey, their_pubkey))
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"terminalsync-v2-session-key",
    )
    return kdf.derive(dh_secret + psk)


def encrypt_frame(key: bytes, plaintext: bytes) -> bytes:
    """Encrypt with XSalsa20-Poly1305. Returns nonce+ciphertext+tag."""
    box = SecretBox(key)
    return bytes(box.encrypt(plaintext))


def decrypt_frame(key: bytes, data: bytes) -> bytes:
    """Decrypt XSalsa20-Poly1305 frame. Raises nacl.exceptions.CryptoError on auth failure."""
    box = SecretBox(key)
    return bytes(box.decrypt(data))


def generate_sas(session_key: bytes) -> str:
    """Return 4-group numeric SAS for out-of-band verification, e.g. '042-187-603-921'."""
    digest = hashlib.sha256(b"terminalsync-sas-v2" + session_key).digest()
    groups = []
    for i in range(4):
        val = int.from_bytes(digest[i * 4 : (i + 1) * 4], "big") % 1000
        groups.append(f"{val:03d}")
    return "-".join(groups)
