import atexit
import datetime
import ipaddress
import os
import ssl
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def generate_ephemeral_tls(host: str) -> tuple[ssl.SSLContext, bytes]:
    """
    Generate a per-invocation self-signed TLS cert for `host`.
    Returns (ssl_server_context, cert_der_bytes).
    Temp key/cert files are registered for atexit cleanup.
    """
    key = ec.generate_private_key(ec.SECP256R1())

    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "terminalsync")])
    san_list: list[x509.GeneralName] = [x509.DNSName("terminalsync")]
    try:
        san_list.append(x509.IPAddress(ipaddress.ip_address(host)))
    except ValueError:
        san_list.append(x509.DNSName(host))

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(hours=24))
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    cert_der = cert.public_bytes(serialization.Encoding.DER)

    cert_f = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode="wb")
    key_f = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode="wb")
    cert_f.write(cert_pem)
    key_f.write(key_pem)
    cert_f.close()
    key_f.close()

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.check_hostname = False
    ctx.load_cert_chain(cert_f.name, key_f.name)

    atexit.register(lambda: os.unlink(cert_f.name) if os.path.exists(cert_f.name) else None)
    atexit.register(lambda: os.unlink(key_f.name) if os.path.exists(key_f.name) else None)

    return ctx, cert_der
