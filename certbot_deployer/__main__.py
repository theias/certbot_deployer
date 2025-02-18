#!/usr/bin/env python3
"""
Pluggable certbot deploy hook framework

This module defines the main entry point of the deploy hook framework.
It parses command-line arguments, dispatches to the appropriate deployer
plugin based on the subcommand provided, and executes the deployment workflow.
"""
import argparse
import logging
import os
import sys
from typing import List, Optional, Type
from certbot_deployer.deployer import Deployer, CertificateBundle

try:
    # for Python 3.8+
    from importlib.metadata import entry_points, EntryPoints
except ImportError:
    # For older Python versions, use the backport package
    from importlib_metadata import entry_points, EntryPoints  # type:ignore


def load_deployer_plugins() -> List[Type[Deployer]]:
    """
    Discover deployer plugins registered as entry points under the group
    'certbot_deployer.plugins'.

    Returns:
        List[Type[Deployer]]: A list of deployer plugin classes.
    """
    plugins = []
    entrypoints = entry_points()

    # Python 3.10+ supports select() on the entry_points object.
    deployer_entrypoints: EntryPoints
    try:
        deployer_entrypoints = entrypoints.select(group="certbot_deployer.plugins")
    except AttributeError:
        # For older versions of importlib.metadata, entrypoints is dict-like
        deployer_entrypoints = entrypoints.get(
            "certbot_deployer.plugins", EntryPoints([])
        )

    # Load each plugin and append it to the plugins list.
    for entry_point in deployer_entrypoints:
        plugin_class = entry_point.load()
        plugins.append(plugin_class)
    return plugins


class DeployerPluginConflict(Exception):
    """
    Exception raised when there is a conflict between deployer plugins.

    This typically occurs when two plugins attempt to register the same subcommand,
    which would otherwise lead to ambiguity in the command-line interface.
    """


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
    discovered_deployers: Optional[List[Type[Deployer]]] = None,
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
        discovered_deployers (Optional[List[Type[Deployer]]]): A list of deployer plugin classes.

    Returns:
        None

    Raises:
        argparse.ArgumentTypeError: If the `renewed_lineage` path is not provided via the environment variable or command-line arguments.
    """
    # pylint: enable=line-too-long
    discovered_deployers = (
        discovered_deployers
        if discovered_deployers is not None
        else load_deployer_plugins()
    )
    args = parse_args(argv, deployers=discovered_deployers)
    logging.debug("Argparse results: %s", args)
    certificate_bundle: CertificateBundle = CertificateBundle(path=args.renewed_lineage)
    args.entrypoint(args=args, certificate_bundle=certificate_bundle)


if __name__ == "__main__":
    main()
