"""
shared helper functions
"""

from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

COMMON_NAME: str = "test_common_name"
""" Common name used by `generate_self_signed_cert` if not overridden """
NOT_VALID_BEFORE: datetime = datetime(2020, 1, 1)
""" NOT_VALID_BEFORE value used by `generate_self_signed_cert` if not overridden """
NOT_VALID_AFTER: datetime = datetime(2099, 1, 1)
""" NOT_VALID_AFTER value used by `generate_self_signed_cert` if not overridden """


def generate_self_signed_cert(
    common_name: str = COMMON_NAME,
    not_valid_before: datetime = NOT_VALID_BEFORE,
    not_valid_after: datetime = NOT_VALID_AFTER,
) -> str:
    """
    Generate a self-signed certificate in PEM format for testing.

    Args:
        common_name (str): The desired Common Name for the certificate.
        not_valid_before (datetime): The certificate validity start time.
        not_valid_after (datetime): The certificate validity end time.

    Returns:
        str: The PEM-encoded certificate.
    """
    key: rsa.RSAPrivateKey = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    subject: x509.Name
    issuer: x509.Name
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert: x509.Certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    pem_bytes: bytes = cert.public_bytes(encoding=serialization.Encoding.PEM)
    return pem_bytes.decode("utf-8")
