"""
shared helper functions
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

import pytest

from certbot_deployer import (
    CERT_FILENAME,
    FULLCHAIN_FILENAME,
    INTERMEDIATES_FILENAME,
    KEY_FILENAME,
)
from certbot_deployer.deployer import CertificateBundle

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
        common_name (str): The desired Common Name for the certificate, else COMMON_NAME
        not_valid_before (datetime): The certificate validity start time, else NOT_VALID_BEFORE
        not_valid_after (datetime): The certificate validity end time, else NOT_VALID_AFTER

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


@pytest.fixture(name="self_signed_certificate_bundle")
def fixture_self_signed_certificate_bundle(
    tmp_path: Path,
    common_name: str = COMMON_NAME,
    not_valid_before: datetime = NOT_VALID_BEFORE,
    not_valid_after: datetime = NOT_VALID_AFTER,
    path: Optional[Path] = None,
) -> CertificateBundle:
    """
    Generate a self-signed certificate bundle for testing.

    Args:
        common_name (str): The desired Common Name for the certificate, else COMMON_NAME
        not_valid_before (datetime): The certificate validity start time, else NOT_VALID_BEFORE
        not_valid_after (datetime): The certificate validity end time, else NOT_VALID_AFTER
        path (pathlib.Path): optional path in which to create the bundle files

    Returns:
        CertificateBundle object corresponding to the bundle
    """
    bundle_path: Path = path if path is not None else tmp_path
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

    key_text: str = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    cert_text: str = pem_bytes.decode("utf-8")

    (bundle_path / CERT_FILENAME).write_text(cert_text, encoding="utf-8")
    (bundle_path / KEY_FILENAME).write_text(key_text, encoding="utf-8")
    (bundle_path / INTERMEDIATES_FILENAME).write_text(cert_text, encoding="utf-8")
    (bundle_path / FULLCHAIN_FILENAME).write_text(
        f"{cert_text}\n{cert_text}", encoding="utf-8"
    )

    return CertificateBundle(path_obj=bundle_path)
