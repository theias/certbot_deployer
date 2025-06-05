"""
Unit tests for main app ``certbot_deployer`
"""

import argparse
import builtins
import json
import os

from pathlib import Path

from typing import Any, ClassVar, List, Dict, TextIO, Tuple

import pytest

from certbot_deployer.main import (
    parse_args,
    main,
    read_config,
    ConfigDict,
    CONFIG_FILENAME,
)
from certbot_deployer import DeployerPluginConflict
from certbot_deployer.deployer import Deployer, CertificateBundle
from certbot_deployer.meta import __prog__, __version__

# pylint: disable-next=unused-import # not actually unused, just difft name from pytest
from .testing import fixture_self_signed_certificate_bundle


@pytest.fixture(name="config_dict", scope="function")
def fixture_config_dict() -> ConfigDict:
    """
    Return a ConfigDict with some config
    """
    test_config: Dict[str, Any] = {}
    test_config["certbot_deployer"] = {"verbosity": 1}
    test_config["dummy"] = {
        "dummy_arg_str": "bar",
        "dummy_arg_int": 11,
        "dummy_arg_bool": False,
        "dummy_arg_list": [
            "value1",
            "value2",
        ],
    }
    return test_config


@pytest.fixture(name="config_file", scope="function")
def fixture_config_file(
    tmp_path: Path, config_dict: ConfigDict
) -> Tuple[Path, ConfigDict]:
    """
    Return a tuple of:

    * the path on disk for a config file to use in testing
    * the config object that the file was created from
    """
    config_filepath: Path = tmp_path / CONFIG_FILENAME
    with open(config_filepath, "w", encoding="utf-8") as cfile:
        cfile.write(json.dumps(config_dict))
    return (config_filepath, config_dict)


# pylint: disable=missing-class-docstring
class DummyDeployer(Deployer):
    subcommand: ClassVar[str] = "dummy"
    version: ClassVar[str] = "v0.0.0"

    @staticmethod
    def register_args(*, parser: argparse.ArgumentParser) -> None:
        # Register a dummy argument and assign the entrypoint.
        parser.add_argument("--dummy-arg-str", default="default")
        parser.add_argument(
            "--dummy-arg-int",
            type=int,
            default=0,
        )
        parser.add_argument(
            "--dummy-arg-bool",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "--dummy-arg-list",
            nargs="+",
            type=str,
            default=["value1", "value2"],
        )

    @staticmethod
    def argparse_post(*, args: argparse.Namespace) -> None:
        # For testing, mark that this post-processing has been done.
        args.dummy_post = True

    @staticmethod
    def entrypoint(
        *, args: argparse.Namespace, certificate_bundle: CertificateBundle
    ) -> None:
        args.entrypoint_called = True


def test_parse_args_without_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify that:

    * args are parsed by the deployer
    * optional post-processing is applied
    * verbosity is set as requested
    """

    # pylint: disable-next=unused-argument
    def fake_open(file: str, *args: Any, **kwargs: Any) -> TextIO:
        assert False, "`parse_args` should not be opening any files in this context"

    monkeypatch.setattr(builtins, "open", fake_open)

    argv: List[str] = ["dummy", "--dummy-arg-str", "foo"]
    monkeypatch.setenv("RENEWED_LINEAGE", "/path/to/nowhere")
    args = parse_args(argv=argv, deployers=[DummyDeployer], config={})

    # Verify that the subcommand and custom arguments are set.
    assert args.subcommand == "dummy"
    assert args.dummy_arg_str == "foo"
    # The deployer’s argparse_post should have set this attribute.
    assert args.dummy_post
    # A valid entrypoint should be set by the dummy deployer.
    # pylint: disable-next=comparison-with-callable
    assert args.entrypoint == DummyDeployer.entrypoint
    assert args.verbosity == 0


def test_parse_args_with_config(
    monkeypatch: pytest.MonkeyPatch, config_file: Tuple[Path, ConfigDict]
) -> None:
    """
    Verify that args get their values from the config when it is present and
    that they are overridden by CLI args where appropriate
    """
    config_filepath: Path
    config_filepath, _ = config_file
    config = read_config(filepath=str(config_filepath))

    argv: List[str]
    monkeypatch.setenv("RENEWED_LINEAGE", "/path/to/nowhere")

    # Verify that config file gets used for args where provided
    argv = ["dummy"]
    args = parse_args(argv=argv, deployers=[DummyDeployer], config=config)
    assert args.verbosity == 1
    assert args.dummy_arg_str == "bar"
    assert args.dummy_arg_bool is False
    assert args.dummy_arg_int == 11
    assert args.dummy_arg_list == ["value1", "value2"]

    # Verify that cli values override any set in config file
    argv = [
        "-v",
        "dummy",
        "--dummy-arg-str",
        "foo",
        "--dummy-arg-bool",
        "--dummy-arg-int",
        "99",
        "--dummy-arg-list",
        "newvalue1",
        "newvalue2",
    ]
    args = parse_args(argv=argv, deployers=[DummyDeployer], config=config)
    assert args.verbosity == 2  # For `action='count'`, values ar addative
    assert args.dummy_arg_str == "foo"
    assert args.dummy_arg_bool is True
    assert args.dummy_arg_int == 99
    assert args.dummy_arg_list == ["newvalue1", "newvalue2"]


@pytest.mark.parametrize(
    "env, fake_filepath",
    [
        (
            {"XDG_CONFIG_HOME": "/home/user/.config"},
            "/home/user/.config/certbot_deployer/certbot_deployer.conf",
        ),
        (
            {"HOME": "/home/user"},
            "/home/user/.config/certbot_deployer/certbot_deployer.conf",
        ),
        (
            {},
            "/etc/certbot_deployer.conf",
        ),
        (
            {},
            "",
        ),
    ],
    ids=[
        "Config from XDG dir",
        "Config from HOME dir",
        "Config from /etc",
        "No config file at all should yield empty",
    ],
)
def test_read_config(
    env: Dict[str, str],
    fake_filepath: str,
    monkeypatch: pytest.MonkeyPatch,
    config_file: Tuple[Path, ConfigDict],
) -> None:
    """
    Verify that the application can:

    * find the config file from a descending series of default paths
    * read the file as config

    Fakes `open` and always returns the same conf so that the function being
    tested can call for system paths like `/etc/`
    """
    real_open = open
    open_count: int = 0

    config_filepath: Path
    test_config: ConfigDict
    config_filepath, test_config = config_file

    def fake_isfile(path: str) -> bool:
        """
        Return True only if the function is looking for our desired path
        """
        return bool(path and (path == fake_filepath))

    monkeypatch.setattr(os.path, "isfile", fake_isfile)

    def fake_open(file: str, *args: Any, **kwargs: Any) -> TextIO:
        """
        No matter what file the tool is trying to open, give it the one we
        want to test on
        """
        nonlocal open_count
        nonlocal config_filepath
        if not file:
            raise FileNotFoundError
        open_count += 1
        assert file == fake_filepath
        # pylint: disable-next=unspecified-encoding
        return real_open(str(config_filepath), *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)

    for key, val in env.items():
        os.environ[key] = val

    resulting_config: ConfigDict = read_config()
    if fake_filepath:
        # If config file exists
        assert test_config == resulting_config
        assert open_count == 1
    else:
        assert not resulting_config
        assert open_count == 0


def test_version(capsys: Any) -> None:
    """
    Verify correct output when `--version` is passed
    """
    expected_version_obj = {
        "certbot_deployer": __version__,
        DummyDeployer.subcommand: DummyDeployer.version,
    }
    with pytest.raises(SystemExit) as sysexit:
        parse_args(argv=["--version"], deployers=[DummyDeployer])
        assert sysexit.value.code == 0
    stdout, _ = capsys.readouterr()
    assert json.loads(stdout) == expected_version_obj


def test_plugin_conflict() -> None:
    """
    Verify that when two deployer plugins use the same subcommand, a
    DeployerPluginConflict is raised.
    """
    with pytest.raises(DeployerPluginConflict):
        parse_args(argv=["conflict"], deployers=[DummyDeployer, DummyDeployer])


def test_plugin_argparse_post_only_called(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify that only the subcommand that was called for runs `argparse_post`
    """

    class DummyDeployerAlt(DummyDeployer):
        subcommand: ClassVar[str] = "dummy2"

        @staticmethod
        def argparse_post(*, args: argparse.Namespace) -> None:
            if args.canary is not True:
                raise argparse.ArgumentTypeError("This error should not come up")

    monkeypatch.setenv("RENEWED_LINEAGE", "/path/to/nowhere")
    parse_args(argv=["dummy"], deployers=[DummyDeployer, DummyDeployerAlt])


def test_exit_no_arguments() -> None:
    """
    Verify that the main application errors out appropriately when no args are given
    """
    # Simulate a situation where no args are passed via sys.argv.
    with pytest.raises(SystemExit) as exc:
        parse_args(argv=[], deployers=[DummyDeployer])
    assert exc.value.code == 1


def test_main_delegates(
    monkeypatch: pytest.MonkeyPatch,
    certbot_deployer_self_signed_certificate_bundle: CertificateBundle,
) -> None:
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
    monkeypatch.setenv(
        "RENEWED_LINEAGE", str(certbot_deployer_self_signed_certificate_bundle.path)
    )

    argv: List[str] = ["-v", "dummy", "--dummy-arg-str", "bar"]
    main(argv=argv, deployers=[DummyDeployer])

    # Verify that our fake entrypoint was executed.
    assert called
