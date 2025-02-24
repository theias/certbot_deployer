"""
Unit tests for main app ``certbot_deployer`
"""

import argparse
from pathlib import Path

from datetime import datetime

from typing import ClassVar, List, Dict


import pytest

from certbot_deployer.main import parse_args
from certbot_deployer import main, DeployerPluginConflict
from certbot_deployer.deployer import Deployer, CertificateBundle
from certbot_deployer.deployer import CERT_FILENAME
from .helpers import generate_self_signed_cert


# pylint: disable=missing-class-docstring
class DummyDeployer(Deployer):
    subcommand: ClassVar[str] = "dummy"

    @staticmethod
    def register_args(*, parser: argparse.ArgumentParser) -> None:
        # Register a dummy argument and assign the entrypoint.
        parser.add_argument("--dummy-arg", default="default", help="A dummy argument")

    @staticmethod
    def argparse_post(*, args: argparse.Namespace) -> None:
        # For testing, mark that this post-processing has been done.
        args.dummy_post = True

    @staticmethod
    def entrypoint(
        *, args: argparse.Namespace, certificate_bundle: CertificateBundle
    ) -> None:
        args.entrypoint_called = True


def test_parse_args(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify that:

    * args are parsed by the deployer
    * optional post-processing is applied
    * verbosity is set as requested
    """

    argv: List[str] = ["-vv", "dummy", "--dummy-arg", "foo"]
    monkeypatch.setenv("RENEWED_LINEAGE", "/path/to/nowhere")
    args = parse_args(argv=argv, deployers=[DummyDeployer])

    # Verify that the subcommand and custom arguments are set.
    assert args.subcommand == "dummy"
    assert args.dummy_arg == "foo"
    # The deployer’s argparse_post should have set this attribute.
    assert args.dummy_post
    # A valid entrypoint should be set by the dummy deployer.
    assert callable(args.entrypoint)
    # Note that we are inspecting the number of times `-v` was passed, and not
    # the actual log level configured in `logging`. Good enough
    assert args.verbosity == 2


def test_plugin_conflict() -> None:
    """
    Verify that when two deployer plugins use the same subcommand, a
    DeployerPluginConflict is raised.
    """
    with pytest.raises(DeployerPluginConflict):
        parse_args(argv=["conflict"], deployers=[DummyDeployer, DummyDeployer])


def test_exit_no_arguments() -> None:
    """
    Verify that the main application errors out appropriately when no args are given
    """
    # Simulate a situation where no args are passed via sys.argv.
    with pytest.raises(SystemExit) as exc:
        parse_args(argv=[], deployers=[DummyDeployer])
    assert exc.value.code == 1


def test_main_delegates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Test that main() correctly delegates to the deployer plugin's entrypoint.
    To do this, we override the deployers in `main` with our dummy
    and patch DummyDeployer.entrypoint to record the call.
    """

    # As a dict is mutable and will be passed by reference, the mock will
    # modify this in the calling context for us to inspect after
    called: Dict[str, bool] = {"called": False}

    def mock_entrypoint(
        *,
        # pylint: disable-next=unused-argument
        args: argparse.Namespace,
        # pylint: disable-next=unused-argument
        certificate_bundle: CertificateBundle
    ) -> None:
        # pylint: disable-next=unused-variable
        called["called"] = True

    monkeypatch.setattr(DummyDeployer, "entrypoint", mock_entrypoint)

    # Create a self-signed certificate with fixed validity dates.
    common_name: str = "Test Common Name"
    not_valid_before: datetime = datetime(2020, 1, 1)
    not_valid_after: datetime = datetime(2099, 1, 1)
    cert_pem: str = generate_self_signed_cert(
        common_name, not_valid_before, not_valid_after
    )
    cert_file: Path = tmp_path / CERT_FILENAME
    cert_file.write_text(cert_pem, encoding="utf-8")
    # IRL this is always provided by Certbot, but for testing...
    monkeypatch.setenv("RENEWED_LINEAGE", str(tmp_path))

    argv: List[str] = ["-v", "dummy", "--dummy-arg", "bar"]
    main(argv=argv, deployers=[DummyDeployer])

    # Verify that our fake entrypoint was executed.
    assert called
