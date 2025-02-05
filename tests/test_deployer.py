"""
Unit tests for the the `deployer` submodule
"""

import argparse
import os
from pathlib import Path

from datetime import datetime

import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from deployer import CertificateBundle, Deployer
from deployer import (
    CERT,
    CERT_FILENAME,
    FULLCHAIN,
    FULLCHAIN_FILENAME,
    INTERMEDIATES,
    INTERMEDIATES_FILENAME,
    KEY,
    KEY_FILENAME,
)


def generate_self_signed_cert(
    common_name: str,
    not_valid_before: datetime,
    not_valid_after: datetime,
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


def test_certificate_bundle_keys(tmp_path: Path) -> None:
    """
    Verify that CertificateBundle correctly builds its components and populates
    the expected values
    """
    # Create a self-signed certificate with fixed validity dates.
    common_name: str = "Test Common Name"
    not_valid_before: datetime = datetime(2020, 1, 1)
    not_valid_after: datetime = datetime(2099, 1, 1)
    cert_pem: str = generate_self_signed_cert(
        common_name, not_valid_before, not_valid_after
    )

    cert_file: Path = tmp_path / CERT_FILENAME
    cert_file.write_text(cert_pem, encoding="utf-8")
    bundle: CertificateBundle = CertificateBundle(path=str(tmp_path))

    # Verify `keys`
    expected_keys = ["cert", "intermediates", "fullchain", "privkey"]
    assert bundle.keys() == expected_keys

    # Verify expected objects are present as attributes
    assert getattr(bundle, "cert")
    assert getattr(bundle, "key")
    assert getattr(bundle, "fullchain")
    assert getattr(bundle, "intermediates")

    # Verify contents of each cert component
    assert bundle.cert.label == CERT
    assert bundle.cert.filename == CERT_FILENAME
    assert bundle.cert.path == os.path.join(tmp_path, (CERT_FILENAME))
    assert bundle.key.label == KEY
    assert bundle.key.filename == KEY_FILENAME
    assert bundle.key.path == os.path.join(tmp_path, (KEY_FILENAME))
    assert bundle.fullchain.label == FULLCHAIN
    assert bundle.fullchain.filename == FULLCHAIN_FILENAME
    assert bundle.fullchain.path == os.path.join(tmp_path, (FULLCHAIN_FILENAME))
    assert bundle.intermediates.label == INTERMEDIATES
    assert bundle.intermediates.filename == INTERMEDIATES_FILENAME
    assert bundle.intermediates.path == os.path.join(tmp_path, (INTERMEDIATES_FILENAME))


def test_certificate_bundle_missing_cert(tmp_path: Path) -> None:
    """
    Verify that CertificateBundle raises a RuntimeError when the primary
    certificate file is missing.
    """
    # Do not create a 'cert.pem'. Instantiating should raise a RuntimeError.
    with pytest.raises(RuntimeError):
        CertificateBundle(path=str(tmp_path))


def test_certificate_bundle_expires_and_common_name(tmp_path: Path) -> None:
    """
    Verify that CertificateBundle correctly extracts the 'expires' date and
    'common_name' from the certificate.
    """
    common_name: str = "Test Common Name"
    not_valid_before: datetime = datetime(2020, 1, 1)
    not_valid_after: datetime = datetime(2030, 1, 1)
    cert_pem: str = generate_self_signed_cert(
        common_name, not_valid_before, not_valid_after
    )

    cert_file: Path = tmp_path / CERT_FILENAME
    cert_file.write_text(cert_pem, encoding="utf-8")

    bundle: CertificateBundle = CertificateBundle(path=str(tmp_path))
    expected_expires: str = not_valid_after.isoformat()

    assert bundle.expires == expected_expires
    assert bundle.common_name == common_name


def test_deployer_register_args_not_implemented() -> None:
    """
    Verify that calling the Deployer.register_args method (without overriding)
    raises NotImplementedError.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    with pytest.raises(NotImplementedError):
        Deployer.register_args(parser=parser)


def test_deployer_entrypoint_not_implemented(tmp_path: Path) -> None:
    """
    Verify that calling the Deployer.entrypoint method (without overriding)
    raises NotImplementedError.
    """
    common_name: str = "Test Common Name"
    not_valid_before: datetime = datetime(2020, 1, 1)
    not_valid_after: datetime = datetime(2030, 1, 1)
    cert_pem: str = generate_self_signed_cert(
        common_name, not_valid_before, not_valid_after
    )
    cert_file: Path = tmp_path / CERT_FILENAME
    cert_file.write_text(cert_pem, encoding="utf-8")

    args: argparse.Namespace = argparse.Namespace()
    certificate_bundle: CertificateBundle = CertificateBundle(
        path=str(tmp_path),
    )
    with pytest.raises(NotImplementedError):
        Deployer.entrypoint(args=args, certificate_bundle=certificate_bundle)


def test_deployer_argparse_post_default() -> None:
    """
    Verify that Deployer.argparse_post does nothing unless overridden by child
    """
    args: argparse.Namespace = argparse.Namespace(dummy="value")
    result: None = Deployer.argparse_post(args=args)
    # The namespace should remain unchanged
    assert args.dummy == "value"
    assert result is None
