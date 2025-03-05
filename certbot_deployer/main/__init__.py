#!/usr/bin/env python3
"""
Pluggable certbot deploy hook framework

This module defines the primary behavior of the deploy hook framework.
It parses command-line arguments, dispatches to the appropriate deployer
plugin based on the subcommand provided, and executes the deployment workflow.
"""
import argparse
import logging
import os
import sys
from typing import cast
from typing import Dict, List, Optional, Type, Tuple

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

from certbot_deployer.meta import __prog__


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


def parse_args(
    argv: Optional[list] = None, deployers: Optional[List[Type[Deployer]]] = None
) -> argparse.Namespace:
    # pylint: disable=line-too-long
    """
    Parse command-line arguments and set up deployer subcommands.

    This function builds an argparse.ArgumentParser with a common description,
    attaches subparsers for each provided deployer plugin (using their
    `subcommand` attribute), and configures root logging based on the verbosity
    flag.

    Args:
        argv (Optional[list]): The list of command-line arguments. Defaults to an empty list (which triggers help output) if None.
        deployers (Optional[List[Type[Deployer]]]): A list of deployer plugin classes. Each plugin must define a unique `subcommand` and implement the required interface. If not provided, the framework may warn that no subcommands are available.

    Returns:
        argparse.Namespace: The namespace containing the parsed arguments.

    Raises:
        DeployerPluginConflict: If two or more deployer plugins share the same subcommand.
        SystemExit: If no command-line arguments are provided (help is printed and execution exits).
    """
    # pylint: enable=line-too-long
    argv = [] if argv is None else argv
    deployers = [] if deployers is None else deployers

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

    if not argv:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args(argv) if argv else parser.parse_args([])

    if not args.renewed_lineage:
        raise argparse.ArgumentTypeError(
            "RENEWED_LINEAGE` not found in environment. Is this tool not being "
            "run by Certbot?"
        )

    for deployer in deployers:
        deployer.argparse_post(args=args)

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
