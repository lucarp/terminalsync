import ssl
import hashlib
import pytest
from terminalsync.tls import generate_ephemeral_tls


def test_returns_ssl_context_and_cert_der():
    ctx, cert_der = generate_ephemeral_tls("127.0.0.1")
    assert isinstance(ctx, ssl.SSLContext)
    assert isinstance(cert_der, bytes)
    assert len(cert_der) > 100  # real DER cert


def test_cert_der_is_x509():
    from cryptography import x509
    _, cert_der = generate_ephemeral_tls("127.0.0.1")
    cert = x509.load_der_x509_certificate(cert_der)
    assert cert.subject is not None


def test_fingerprint_is_sha256_of_cert():
    _, cert_der = generate_ephemeral_tls("127.0.0.1")
    fpr = hashlib.sha256(cert_der).hexdigest()
    assert len(fpr) == 64  # 256 bits as hex


def test_different_invocations_produce_different_certs():
    _, cert1 = generate_ephemeral_tls("127.0.0.1")
    _, cert2 = generate_ephemeral_tls("127.0.0.1")
    assert cert1 != cert2


def test_ssl_context_is_server_context():
    ctx, _ = generate_ephemeral_tls("127.0.0.1")
    assert ctx.check_hostname is False
