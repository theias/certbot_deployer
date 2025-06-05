#!/usr/bin/env python3
"""
Pluggable certbot deploy hook framework

This module defines the primary behavior of the deploy hook framework.
It parses command-line arguments, dispatches to the appropriate deployer
plugin based on the subcommand provided, and executes the deployment workflow.
"""
import argparse
import json
import logging
import os
import sys
from typing import cast
from typing import Any, Dict, List, Optional, Type, Tuple

try:
    # python>=3.10
    from importlib.metadata import entry_points, EntryPoints
except ImportError:
    # python<3.10
    # Use the pip backport of importlib.metadata because the stdlib version
    # misbehaves and duplicates discovered entry points
    from importlib_metadata import entry_points, EntryPoint  # type:ignore

from certbot_deployer.deployer import (
    Deployer,
    CertificateBundle,
    DeployerPluginConflict,
)


from certbot_deployer.meta import __prog__, __title__, __version__

ConfigDict = Dict[str, Dict[str, Any]]
CONFIG_FILENAME: str = "certbot_deployer.conf"


def load_deployer_plugins() -> List[Type[Deployer]]:
    """
    Discover deployer plugins registered as entry points under the group
    'certbot_deployer.plugins'.

    Returns:
        List[Type[Deployer]]: A list of deployer plugin classes.
    """
    plugins: List[Type[Deployer]] = []

    # python>=3.10 `entrypoints` returns an `EntryPoints` of `EntryPoint`
    # objects, while earlier returns a dict of `EntryPoint` objects
    try:
        # python>=3.10
        deployer_entrypoints: EntryPoints = entry_points(
            group="certbot_deployer.plugins"
        )
        # Load each plugin and append it to the plugins list.
        for entry_point in deployer_entrypoints:
            plugin_class = entry_point.load()
            plugins.append(plugin_class)
    except (TypeError, AttributeError):
        # python<3.10
        deployer_entrypoints_pylt310: Tuple[
            EntryPoint
        ] = entry_points().get(  # type:ignore
            "certbot_deployer.plugins", {}  # type:ignore
        )
        # Load each plugin and append it to the plugins list.
        for _, entry_point in deployer_entrypoints_pylt310:  # type:ignore
            plugin_class = entry_point.load()
            plugins.append(plugin_class)

    return plugins


def read_config(filepath: Optional[str] = None) -> ConfigDict:
    """
    Reads a configuration file from the specified path or discovers one from a
    predefined set of reasonable paths.

    If a filepath is provided, it attempts to read the configuration from that path.

    If no filepath is provided, it searches for 'certbot_deployer.conf' in the
    following locations:
        1. The `XDG_CONFIG_HOME` directory (or `~/.config/certbot_deployer/` if unset).
        2. `/etc`

    Returns:
        A dictionary containing the configuration data if a valid file is found and
        successfully read. If no file is found or an error occurs, an empty dictionary
        is returned.
    """
    config_filepath: str = ""
    config: ConfigDict = {}
    if filepath is not None:
        config_filepath = filepath
    else:
        config_filename: str = "certbot_deployer.conf"
        config_paths: List[str] = [
            os.path.join(
                os.getenv(
                    "XDG_CONFIG_HOME",
                    default=os.path.join(
                        os.getenv("HOME", default=""),
                        ".config",
                    ),
                ),
                __title__,
                config_filename,
            ),
            os.path.join(os.path.sep, "etc", config_filename),
        ]
        for config_path in config_paths:
            if os.path.isfile(config_path):
                config_filepath = config_path
                break
    logging.info("Opening configuration file `%s`", config_filepath)
    try:
        with open(config_filepath, "r", encoding="utf-8") as config_file:
            config = json.loads(config_file.read())
        logging.debug("Configuration read from file: `%s`", config)
        return config
    except FileNotFoundError:
        return {}


def parse_args(
    argv: Optional[list] = None,
    deployers: Optional[List[Type[Deployer]]] = None,
    config: Optional[ConfigDict] = None,
) -> argparse.Namespace:
    """
    Parse command-line arguments and set up deployer subcommands.

    This function builds an argparse.ArgumentParser with a common description,
    attaches subparsers for each provided deployer plugin (using their
    `subcommand` attribute), and configures root logging based on the verbosity
    flag.

    Args:
        argv (Optional[list]): The list of command-line arguments. Defaults to
            an empty list (which triggers help output) if None.
        deployers (Optional[List[Type[Deployer]]]): A list of deployer plugin
            classes. Each plugin must define a `version, a unique `subcommand` and
            implement the required interface. If not provided, the framework may
            warn that no subcommands are available.
        config (Optional[ConfigDict]): A dict with the values from a config
            file with the keys being subconfigs per plugin

    Returns:
        argparse.Namespace: The namespace containing the parsed arguments.

    Raises:
        DeployerPluginConflict: If two or more deployer plugins share the same subcommand.
        SystemExit: If no command-line arguments are provided (help is printed and execution exits).
    """
    argv = [] if argv is None else argv
    deployers = [] if deployers is None else deployers
    versions: Dict[str, str] = {}

    epilog: str
    if not deployers:
        epilog = """Warning:

        No subcommand plugins discovered. This tool only functions via its plugins.
        """
    else:
        epilog = """Try `%(prog)s <subcommand> -h`. This tool only functions via its plugins.
        """
    descr = "Pluggable certbot deploy hook framework"
    parser = argparse.ArgumentParser(
        description=descr,
        epilog=epilog,
        prog=__prog__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    config = config if config is not None else read_config()

    parser.add_argument(
        "--version",
        "-V",
        action="store_true",
        help="Print current software version of Certbot Deployer and any plugins",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        dest="verbosity",
        help="Set output verbosity (-v=warning, -vv=debug)",
    )

    parser.add_argument(
        # This is hidden because this tool is intended to be used exclusively
        # as a deploy hook for Certbot and relies upon the documented
        # environment variable `RENEWED_LINEAGE`. No user should be passing this.
        "--renewed-lineage",
        default=os.environ.get("RENEWED_LINEAGE"),
        help=argparse.SUPPRESS,
        type=str,
    )

    if len({deployer.subcommand for deployer in deployers}) != len(deployers):
        raise DeployerPluginConflict(
            "There are conflicting `subcommand` values among deployer plugins"
        )
    subparsers = parser.add_subparsers(
        title="Subcommands",
        description="Specific certificate deployers",
        dest="subcommand",
    )
    for deployer in deployers:
        subparser = subparsers.add_parser(deployer.subcommand)
        deployer.register_args(parser=subparser)
        subparser.set_defaults(entrypoint=deployer.entrypoint)
        subparser.set_defaults(**config.get(deployer.subcommand, {}))
        versions[deployer.subcommand] = deployer.version if deployer.version else ""

    if not argv:
        parser.print_help()
        sys.exit(1)

    parser.set_defaults(**config.get(__title__, {}))
    args = parser.parse_args(argv) if argv else parser.parse_args([])

    if args.version:
        versions[__title__] = __version__
        print(json.dumps(versions, indent=2))
        sys.exit(0)

    if not args.renewed_lineage:
        raise argparse.ArgumentTypeError(
            "RENEWED_LINEAGE` not found in environment. Is this tool not being "
            "run by Certbot?"
        )

    for deployer in deployers:
        if deployer.subcommand == args.subcommand:
            deployer.argparse_post(args=args)
            break

    if args.verbosity >= 2:
        log_level = logging.DEBUG
    elif args.verbosity >= 1:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    logging.basicConfig(level=log_level)

    return args


def main(
    argv: list = sys.argv[1:],
    deployers: Optional[List[Type[Deployer]]] = None,
) -> None:
    # pylint: disable=line-too-long
    """
    Main entry point of the certbot deploy hook framework.

    This function parses the command-line arguments, creates a `CertificateBundle`
    using the `renewed_lineage` path provided by Certbot, and delegates execution
    to the appropriate deployer plugin's entrypoint.

    The deployer plugin is selected based on the subcommand provided in the
    command-line arguments. Each deployer plugin must define a unique subcommand
    and implement the required interface, including an `entrypoint` method that
    accepts the parsed arguments and the pre-created `CertificateBundle`.

    Args:
        argv (list): The list of command-line arguments (excluding the program name). Defaults to `sys.argv[1:]`.
        deployers (Optional[List[Type[Deployer]]]): A list of deployer plugin classes.

    Returns:
        None

    Raises:
        argparse.ArgumentTypeError: If the `renewed_lineage` path is not provided via the environment variable or command-line arguments.
    """
    # pylint: enable=line-too-long
    deployers = deployers if deployers is not None else load_deployer_plugins()
    args = parse_args(argv, deployers=deployers)
    logging.debug("Argparse results: %s", args)
    certificate_bundle: CertificateBundle = CertificateBundle(path=args.renewed_lineage)
    args.entrypoint(args=args, certificate_bundle=certificate_bundle)
