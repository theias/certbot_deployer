"""
Resources to assist in testing Certbot Deployer and its plugins

Functions here should be made available as pytest
[fixtures](https://docs.pytest.org/en/latest/how-to/fixtures.html#how-to-fixtures).

Other documented resources can be used by import from `certbot_deployer.testing`, e.g.:

```
from certbot_deployer.testing import COMMON_NAME
```
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

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
""" A hard-coded default value used by testing fixtures """
NOT_VALID_BEFORE: datetime = datetime(2020, 1, 1)
""" A hard-coded default value used by testing fixtures """
NOT_VALID_AFTER: datetime = datetime(2099, 1, 1)
""" A hard-coded default value used by testing fixtures """


@pytest.fixture(name="certbot_deployer_self_signed_certificate_bundle")
# pylint: disable=too-many-locals
def fixture_self_signed_certificate_bundle(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> CertificateBundle:
    """
    Pytest fixture which generates a self-signed certificate bundle for testing.

    Example usage:

    ```
    import certbot_deployer
    from certbot_deployer.testing import COMMON_NAME

    def test_your_plugin_function(
        certbot_deployer_self_signed_certificate_bundle: certbot_deployer.CertificateBundle
    ) -> None:
        assert certbot_deployer_self_signed_certificate_bundle.common_name == COMMON_NAME
    ```

    Args:
        request (`pytest.FixtureRequest`): The pytest request object to access
            indirect fixture parameters.

    Parameters for Pytest indirect parameterization via `request`:

    * common_name (str): The desired Common Name for the certificate, else COMMON_NAME
    * not_valid_before (datetime): The certificate validity start time, else NOT_VALID_BEFORE
    * not_valid_after (datetime): The certificate validity end time, else NOT_VALID_AFTER
    * path (pathlib.Path): optional path in which to create the bundle files

    Returns:
        `certbot_deployer.deployer.CertificateBundle` corresponding to the created bundle.
    """
    req_params: dict = getattr(request, "param", {})
    not_valid_before: datetime = NOT_VALID_BEFORE
    if "not_valid_before" in req_params:
        assert isinstance(req_params["not_valid_before"], datetime)
        not_valid_before = req_params["not_valid_before"]
    not_valid_after: datetime = NOT_VALID_AFTER
    if "not_valid_after" in req_params:
        assert isinstance(req_params["not_valid_after"], datetime)
        not_valid_after = req_params["not_valid_after"]
    path: Optional[Path] = None
    if "path" in req_params:
        assert isinstance(req_params["path"], (Path, type(None)))
        path = req_params["path"]
    subject_alternative_names: List[str] = []
    if "subject_alternative_names" in req_params:
        assert isinstance(req_params["subject_alternative_names"], list)
        subject_alternative_names = req_params["subject_alternative_names"]
    common_name: Optional[str] = COMMON_NAME
    if "common_name" in req_params:
        assert isinstance(req_params["common_name"], (str, type(None)))
        common_name = req_params["common_name"]

    bundle_path: Path = path if path is not None else tmp_path
    key: rsa.RSAPrivateKey = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    subject: x509.Name
    issuer: x509.Name
    if common_name is None:
        subject = issuer = x509.Name([])
    else:
        subject = issuer = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
        )
    cert_builder: x509.CertificateBuilder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    )
    if subject_alternative_names:
        san_extension = x509.SubjectAlternativeName(
            [x509.DNSName(fqdn) for fqdn in subject_alternative_names]
        )
        cert_builder = cert_builder.add_extension(san_extension, critical=False)
    cert: x509.Certificate = cert_builder.sign(key, hashes.SHA256())
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


# pylint: enable=too-many-locals
