import pytest
from terminalsync.crypto import (
    generate_keypair,
    generate_psk,
    derive_session_key,
    encrypt_frame,
    decrypt_frame,
    generate_sas,
)


def test_keypair_sizes():
    priv, pub = generate_keypair()
    assert len(priv) == 32
    assert len(pub) == 32


def test_keypair_is_random():
    priv1, pub1 = generate_keypair()
    priv2, pub2 = generate_keypair()
    assert priv1 != priv2
    assert pub1 != pub2


def test_psk_size():
    psk = generate_psk()
    assert len(psk) == 32


def test_psk_is_random():
    assert generate_psk() != generate_psk()


def test_ecdh_session_key_symmetric():
    """Both sides derive the same key."""
    priv_a, pub_a = generate_keypair()
    priv_b, pub_b = generate_keypair()
    psk = generate_psk()

    key_a = derive_session_key(priv_a, pub_b, psk)
    key_b = derive_session_key(priv_b, pub_a, psk)

    assert key_a == key_b
    assert len(key_a) == 32


def test_ecdh_key_changes_with_psk():
    priv_a, pub_a = generate_keypair()
    priv_b, pub_b = generate_keypair()
    psk1 = generate_psk()
    psk2 = generate_psk()

    key1 = derive_session_key(priv_a, pub_b, psk1)
    key2 = derive_session_key(priv_a, pub_b, psk2)

    assert key1 != key2


def test_encrypt_decrypt_roundtrip():
    priv_a, pub_a = generate_keypair()
    priv_b, pub_b = generate_keypair()
    psk = generate_psk()
    key = derive_session_key(priv_a, pub_b, psk)

    plaintext = b"hello, terminal!"
    ciphertext = encrypt_frame(key, plaintext)

    assert ciphertext != plaintext
    assert decrypt_frame(key, ciphertext) == plaintext


def test_decrypt_wrong_key_raises():
    priv_a, pub_a = generate_keypair()
    priv_b, pub_b = generate_keypair()
    psk = generate_psk()
    key = derive_session_key(priv_a, pub_b, psk)
    ciphertext = encrypt_frame(key, b"secret")

    wrong_key = generate_psk()  # random 32 bytes != session key
    with pytest.raises(Exception):
        decrypt_frame(wrong_key, ciphertext)


def test_generate_sas_is_deterministic():
    key = b"\x42" * 32
    sas1 = generate_sas(key)
    sas2 = generate_sas(key)
    assert sas1 == sas2


def test_generate_sas_format():
    key = b"\x00" * 32
    sas = generate_sas(key)
    parts = sas.split("-")
    assert len(parts) == 4
    for p in parts:
        assert len(p) == 3
        assert p.isdigit()


def test_generate_sas_differs_per_key():
    sas1 = generate_sas(b"\x00" * 32)
    sas2 = generate_sas(b"\xff" * 32)
    assert sas1 != sas2
