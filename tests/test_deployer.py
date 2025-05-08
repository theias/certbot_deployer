"""
Unit tests for the the `deployer` submodule
"""

import argparse
import os

from pathlib import Path

import pytest

from certbot_deployer.deployer import CertificateBundle, CertificateComponent, Deployer
from certbot_deployer.deployer import (
    CERT,
    CERT_FILENAME,
    FULLCHAIN,
    FULLCHAIN_FILENAME,
    INTERMEDIATES,
    INTERMEDIATES_FILENAME,
    KEY,
    KEY_FILENAME,
)

# pylint: disable-next=unused-import
from .helpers import generate_self_signed_cert, fixture_self_signed_certificate_bundle
from .helpers import COMMON_NAME, NOT_VALID_AFTER


def test_certificate_bundle_keys(
    self_signed_certificate_bundle: CertificateBundle,
) -> None:
    """
    Verify that CertificateBundle correctly builds its components and populates
    the expected values
    """
    bundle: CertificateBundle = self_signed_certificate_bundle

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
    assert bundle.cert.path == os.path.join(bundle.path, (CERT_FILENAME))

    assert bundle.key.label == KEY
    assert bundle.key.filename == KEY_FILENAME
    assert bundle.key.path == os.path.join(bundle.path, (KEY_FILENAME))

    assert bundle.fullchain.label == FULLCHAIN
    assert bundle.fullchain.filename == FULLCHAIN_FILENAME
    assert bundle.fullchain.path == os.path.join(bundle.path, (FULLCHAIN_FILENAME))

    assert bundle.intermediates.label == INTERMEDIATES
    assert bundle.intermediates.filename == INTERMEDIATES_FILENAME
    assert bundle.intermediates.path == os.path.join(
        bundle.path, (INTERMEDIATES_FILENAME)
    )


def test_certificate_component_missing_cert(tmp_path: Path) -> None:
    """
    Verify that CertificateComponent raises a RuntimeError when a certificate
    file is missing.
    """
    # Do not create any actual bundle files.. Instantiating should raise a RuntimeError.
    with pytest.raises(RuntimeError):
        CertificateComponent(
            label=CERT, filename=CERT_FILENAME, path=str((tmp_path / CERT_FILENAME))
        )


def test_certificate_bundle_expires_and_common_name(
    self_signed_certificate_bundle: CertificateBundle,
) -> None:
    """
    Verify that CertificateBundle correctly extracts the 'expires' date and
    'common_name' from the certificate.
    """
    expected_expires: str = NOT_VALID_AFTER.strftime("%Y-%m-%dT%H:%M:%S")

    assert self_signed_certificate_bundle.expires == expected_expires
    assert self_signed_certificate_bundle.common_name == COMMON_NAME


def test_deployer_register_args_not_implemented() -> None:
    """
    Verify that calling the Deployer.register_args method (without overriding)
    raises NotImplementedError.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    with pytest.raises(NotImplementedError):
        Deployer.register_args(parser=parser)


def test_deployer_entrypoint_not_implemented(
    self_signed_certificate_bundle: CertificateBundle,
) -> None:
    """
    Verify that calling the Deployer.entrypoint method (without overriding)
    raises NotImplementedError.
    """
    args: argparse.Namespace = argparse.Namespace()
    with pytest.raises(NotImplementedError):
        Deployer.entrypoint(
            args=args, certificate_bundle=self_signed_certificate_bundle
        )


def test_deployer_argparse_post_default() -> None:
    """
    Verify that Deployer.argparse_post does nothing unless overridden by child
    """
    args: argparse.Namespace = argparse.Namespace(dummy="value")
    result: None = Deployer.argparse_post(args=args)
    # The namespace should remain unchanged
    assert args.dummy == "value"
    assert result is None
