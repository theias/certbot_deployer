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

# pylint: disable-next=unused-import # not actually unused, just difft name from pytest
from .testing import fixture_self_signed_certificate_bundle
from .testing import COMMON_NAME, NOT_VALID_AFTER

SAN_NAMES = ["somesite1.domain.tld", "site2.domain.tld"]


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


def test_certificate_bundle_keys(
    certbot_deployer_self_signed_certificate_bundle: CertificateBundle,
) -> None:
    """
    Verify that CertificateBundle correctly builds its components and populates
    the expected values
    """
    bundle: CertificateBundle = certbot_deployer_self_signed_certificate_bundle

    # Verify `keys`
    expected_keys = ["cert", "intermediates", "fullchain", "privkey"]
    assert bundle.keys() == expected_keys

    # Verify expected objects are present as attributes
    assert getattr(bundle, "cert")
    assert getattr(bundle, "key")
    assert getattr(bundle, "fullchain")
    assert getattr(bundle, "intermediates")

    # Verify contents of each cert component
    assert bundle.cert == CertificateComponent(
        label=CERT,
        filename=CERT_FILENAME,
        path=os.path.join(bundle.path, (CERT_FILENAME)),
    )

    assert bundle.key == CertificateComponent(
        label=KEY,
        filename=KEY_FILENAME,
        path=os.path.join(bundle.path, (KEY_FILENAME)),
    )

    assert bundle.intermediates == CertificateComponent(
        label=INTERMEDIATES,
        filename=INTERMEDIATES_FILENAME,
        path=os.path.join(bundle.path, (INTERMEDIATES_FILENAME)),
    )

    assert bundle.fullchain == CertificateComponent(
        label=FULLCHAIN,
        filename=FULLCHAIN_FILENAME,
        path=os.path.join(bundle.path, (FULLCHAIN_FILENAME)),
    )


def test_certificate_bundle_paths(
    certbot_deployer_self_signed_certificate_bundle: CertificateBundle,
) -> None:
    """
    Verify that whether the path to the certs is given via `str` or
    `pathlib.Path`, we still get the same results

    So we'll use the bundle-creating fixture just to get a valid cert files in a directory,
    """
    ref_path = certbot_deployer_self_signed_certificate_bundle.path
    ref_path_obj = certbot_deployer_self_signed_certificate_bundle.path_obj
    test_bundle: CertificateBundle

    test_bundle = CertificateBundle(path=ref_path)
    assert test_bundle.path == ref_path
    assert test_bundle.path_obj == ref_path_obj

    test_bundle = CertificateBundle(path_obj=ref_path_obj)
    assert test_bundle.path == ref_path
    assert test_bundle.path_obj == ref_path_obj


@pytest.mark.parametrize(
    "certbot_deployer_self_signed_certificate_bundle",
    [
        {
            "subject_alternative_names": SAN_NAMES,
            "common_name": None,
        }
    ],
    indirect=True,
)
def test_certificate_bundle_name_from_san(
    certbot_deployer_self_signed_certificate_bundle: CertificateBundle,
) -> None:
    """
    Verify that CertificateBundle correctly gets the cert name from the SAN if
    no value is present in `common_name`
    """
    assert certbot_deployer_self_signed_certificate_bundle.common_name == SAN_NAMES[0]


def test_certificate_bundle_metadata(
    certbot_deployer_self_signed_certificate_bundle: CertificateBundle,
) -> None:
    """
    Verify that CertificateBundle correctly extracts the 'expires' date and
    'common_name' from the certificate
    """
    expected_expires: str = NOT_VALID_AFTER.strftime("%Y-%m-%dT%H:%M:%S")

    assert certbot_deployer_self_signed_certificate_bundle.expires == expected_expires
    assert certbot_deployer_self_signed_certificate_bundle.common_name == COMMON_NAME


def test_deployer_register_args_not_implemented() -> None:
    """
    Verify that calling the Deployer.register_args method (without overriding)
    raises NotImplementedError.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    with pytest.raises(NotImplementedError):
        Deployer.register_args(parser=parser)


def test_deployer_entrypoint_not_implemented(
    certbot_deployer_self_signed_certificate_bundle: CertificateBundle,
) -> None:
    """
    Verify that calling the Deployer.entrypoint method (without overriding)
    raises NotImplementedError.
    """
    args: argparse.Namespace = argparse.Namespace()
    with pytest.raises(NotImplementedError):
        Deployer.entrypoint(
            args=args,
            certificate_bundle=certbot_deployer_self_signed_certificate_bundle,
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
