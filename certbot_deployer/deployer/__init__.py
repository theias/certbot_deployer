"""
Base classes for the Certbot deploy hook framework.

This module provides the core types used by the framework:
  - `certbot_deployer.deployer.CertificateBundle`: Represents the collection of
    certificate files produced by Certbot, along with metadata extracted from
    the main certificate.
  - `certbot_deployer.deployer.Deployer`: An abstract base class for deployer
    plugins. Plugin developers should subclass
    `certbot_deployer.deployer.Deployer` and implement its abstract methods to
    register their subcommand-specific arguments and handle deployment tasks.

Here is a minimal example of a deployer which would work with this framework:

```
import argparse

from typing import ClassVar

from certbot_deployer.deployer import Deployer
from certbot_deployer import main as framework_main

class ExampleDeployer(Deployer):
    subcommand: ClassVar[str] = "example"
    version: ClassVar[str] = "v0.0.0"

    @staticmethod
    def register_args(*, parser: argparse.ArgumentParser) -> None:
        '''
        Register command-line arguments for the ExampleDeployer.
        '''
        parser.description = "Minimal Example Deployer"
        parser.add_argument(
            "--message",
            type=str,
            required=True,
            help="A custom message to display during deployment",
        )


    @staticmethod
    def argparse_post(*, args: argparse.Namespace) -> None:
        '''
        Optionally process parsed command-line arguments.
        '''
        # No extra processing needed for this minimal example.

    @staticmethod
    def entrypoint(
        *, args: argparse.Namespace, certificate_bundle: CertificateBundle
    ) -> None:

        '''
        Execute the deployment process.

        This is where one would generally process/deploy certificates
        '''
        # `certificate_bundle` should have everything you need to know about
        # the certificate bundle components - their paths, filenames, and
        # "labels" (the static values predetermined by Certbot itself)
        print("Executing deployment with message:", args.message)


def main() -> None:
    new_argv = [ExampleDeployer.subcommand] + argv
    framework_main(deployers=[ExampleDeployer], argv=new_argv)

if __name__ == "__main__":
    main()
```

And with the following, include the required entry point in your plugin's `setup.cfg`:

```
[options.entry_points]
certbot_deployer.plugins =
    example = certbot_deployer_example:ExampleDeployer

```

The plugin can be installed into an environment alongside this tool, and your
new deployer can be called as follows:

```
$ certbot_deployer example --message "Hello, World!"
Executing deployment with message: Hello, World!
```
"""

import argparse
import logging
import os
import warnings

from collections import namedtuple
from pathlib import Path

from abc import abstractmethod
from typing import Any, Callable, ClassVar, Dict, Iterable, List, NamedTuple, Optional

# pylint: disable-next=duplicate-code
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=UserWarning)
    from cryptography.utils import CryptographyDeprecationWarning
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.x509 import ExtensionOID
    from cryptography.hazmat.primitives import hashes

# We assume the directory structure and filenames created by Certbot
CERT = "cert"
""" The base name used by Certbot for the "cert only" certificate file """
CERT_FILENAME = "cert.pem"
""" The full filename used by Certbot for the "cert only" certificate file """
FULLCHAIN = "fullchain"
""" The base name used by Certbot for the "full chain" certificate file """
FULLCHAIN_FILENAME = "fullchain.pem"
""" The full filename used by Certbot for the "full chain" certificate file """
INTERMEDIATES = "intermediates"
""" The base name used by Certbot for the "intermediates-only" certificate file """
INTERMEDIATES_FILENAME = "chain.pem"
""" The full filename used by Certbot for the "intermediates-only" certificate file """
KEY = "privkey"
""" The base name used by Certbot for the "key" certificate file """
KEY_FILENAME = "privkey.pem"
""" The full filename used by Certbot for the "key" certificate file """


class DeployerPluginConflict(Exception):
    """
    Exception raised when there is a conflict between deployer plugins.

    This typically occurs when two plugins attempt to register the same subcommand,
    which would otherwise lead to ambiguity in the command-line interface.
    """


# pylint: disable-next=too-few-public-methods
class CertificateComponent:
    # pylint: disable=line-too-long
    """
    Represents a single component of a certificate bundle.

    A `certbot_deployer.deployer.CertificateComponent` is an abstraction for individual parts of a certificate
    bundle, such as the certificate, private key, or certificate chain. Each component
    is associated with a specific file path and metadata, allowing it to be processed
    or transferred independently.

    The corresponding file under `path` is read at initialization.

    Attributes:
        contents (str): The contents of the file
        label (str): A human-readable label for the component, one of `["cert", "privkey", "fullchain", "intermediates"]`
        path (str): The path to the component file on the local filesystem.
        filename (str): The name of the component's file on the local filesystem
    """
    # pylint: enable=line-too-long

    def __init__(self, path: str, filename: str, label: str) -> None:
        self.path: str = path
        self.filename: str = filename
        self.label: str = label
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self.contents: str = fh.read()
        except FileNotFoundError as err:
            raise RuntimeError(f"Unable to find `{path}`") from err

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, CertificateComponent):
            return NotImplemented
        return (
            (self.path == other.path)
            and (self.filename == other.filename)
            and (self.label == other.label)
        )


# pylint: disable-next=too-many-instance-attributes
class CertificateBundle:
    # pylint: disable=line-too-long
    """
    Represents a certificate bundle produced by Certbot.

    A certificate bundle consists of several components, each of which is a file
    generated by Certbot. The main components are:

      - `cert`: The primary certificate file.
      - `intermediates`: The file containing intermediate certificates.
      - `key`: The private key file.
      - `fullchain`: The file containing the full certificate chain.

    Upon initialization, the certificate bundle reads the main certificate file to
    extract metadata such as the "Not After" date and common name.

    Attributes:
        `path` (str): The path to the certificate directory on disk
        `cert` (`CertificateComponent`): The primary
            certificate component.
        `intermediates` (`CertificateComponent`): The
            intermediate certificates component.
        `key` (`certbot_deployer.deployer.CertificateComponent`): The private
            key component.
        `fullchain` (`CertificateComponent`): The
            full certificate chain component.
        `components` (Dict[str,
        `CertificateComponent`]): Dictionary mapping
            component labels to their corresponding
            `certbot_deployer.deployer.CertificateComponent`.
        `certdata` (x509.Certificate): The parsed x509 certificate from the
            cert file.
        `expires` (str): The expiration date (Not After) of the certificate in
            ISO8601 format with seconds precision
        `common_name` (str): The common name extracted from the certificate
            (falls back to the first subject alternative name if not present).
    """
    # pylint: enable=line-too-long

    def __init__(
        self, *, path: Optional[str] = None, path_obj: Optional[Path] = None
    ) -> None:
        """
        Initialize a CertificateBundle from a given Certbot "live" directory.

        Reads the certificate file `cert.pem` from the specified directory and
        makes available the bundle of certificate components based on the
        expected filenames.

        Args:
            path (Optional[str]): The directory path (as a string) that
                contains the certificate files. Mutually exclusive with `path_obj`.
            path_obj (Optional[Path]): The directory path (as a `pathlib.Path`)
                that contains the certificate files. Mutually exclusive with
                `path`.

        Raises:
            RuntimeError: If the primary certificate file (`cert.pem`) cannot be found.
            ValueError: If neither or both of `path` and `path_obj` are provided.
        """
        self.path: str
        self.path_obj: Path
        if path is not None and path_obj is None:
            self.path = path
            self.path_obj = Path(path)
        elif path_obj is not None and path is None:
            self.path = str(path_obj)
            self.path_obj = path_obj
        else:
            raise ValueError(
                "One of either `path` or `path_obj` are required and mutually exclusive"
            )
        self.cert: CertificateComponent = CertificateComponent(
            label=CERT,
            filename=CERT_FILENAME,
            path=os.path.join(self.path, CERT_FILENAME),
        )
        self.intermediates: CertificateComponent = CertificateComponent(
            label=INTERMEDIATES,
            filename=INTERMEDIATES_FILENAME,
            path=os.path.join(self.path, INTERMEDIATES_FILENAME),
        )
        self.key: CertificateComponent = CertificateComponent(
            label=KEY, filename=KEY_FILENAME, path=os.path.join(self.path, KEY_FILENAME)
        )
        self.fullchain: CertificateComponent = CertificateComponent(
            label=FULLCHAIN,
            filename=FULLCHAIN_FILENAME,
            path=os.path.join(self.path, FULLCHAIN_FILENAME),
        )
        self.components: Dict[str, CertificateComponent] = {
            CERT: self.cert,
            INTERMEDIATES: self.intermediates,
            FULLCHAIN: self.fullchain,
            KEY: self.key,
        }
        self.certdata: x509.Certificate = x509.load_pem_x509_certificate(
            str.encode(self.cert.contents)
        )
        self.expires: str = self.certdata.not_valid_after_utc.strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        self.common_name: str
        try:
            # Try for Common Name which is not required to be present
            self.common_name = str(
                self.certdata.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[
                    0
                ].value
            )
        except IndexError:
            # Else try to first sub alt name
            san_extension: x509.Extension = (
                self.certdata.extensions.get_extension_for_oid(
                    ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                )
            )
            self.common_name = san_extension.value.get_values_for_type(x509.DNSName)[0]
        logging.debug("Live cert initialized as: `%s`", str(self))

    def keys(self) -> List[str]:
        """
        Get a list of certificate component labels.

            Returns:
                List[str]: The labels of the certificate components (e.g.,
                `["cert", "intermediates", "fullchain", "privkey"]`).
        """
        return list(self.components.keys())

    def __getitem__(self, key: str) -> CertificateComponent:
        """
        Retrieve a certificate component by its label.

        Args:
            key (str): The label of the certificate component to retrieve.

        Returns:
            CertificateComponent: The certificate component associated with the given key.

        Raises:
            KeyError: If the given key does not exist in the components.
        """
        return self.components[key]

    def __str__(self) -> str:
        """
        Returns:
            str: A string summary of the bundle's components and metadata.
        """
        return str(vars(self))


class Deployer:
    """
    Abstract base class for deployer plugins.

    Plugin developers should subclass Deployer to implement their custom
    deployment strategies.

    Each deployer plugin must define:

      - A class attribute `subcommand` used to identify the plugin.
      - A class attribute `version` specifying the current plugin version
      - The static method `register_args(*, parser: argparse.ArgumentParser)`
        to add subcommand-specific arguments.
      - The static method `entrypoint(*, args: argparse.Namespace)` that
        defines the main execution logic.

    Example:

        Basic Deployer

        ```
        class MyDeployer(Deployer):
            subcommand: ClassVar[str] = "mysubcommand"
            version: ClassVar[str] = "v0.0.0"

            @staticmethod
            def register_args(*, parser: argparse.ArgumentParser) -> None:
                # add arguments
                pass

            @staticmethod
            def entrypoint(*, args: argparse.Namespace) -> None:
                pass


        ```

    Optionally, plugins can override `argparse_post(*, args: argparse.Namespace)` for
    post-processing of parsed arguments.
    """

    subcommand: ClassVar[str]
    version: ClassVar[str]

    @staticmethod
    @abstractmethod
    def register_args(*, parser: argparse.ArgumentParser) -> None:
        """
        Register subcommand-specific command-line arguments.

        Plugin implementations must override this method to add their own required
        arguments to the provided argparse parser.

        Example:

            A simple implementation might add a configuration file argument as follows:

            ```
            @staticmethod
            def register_args(*, parser: argparse.ArgumentParser) -> None:
                parser.description = "Subcommand-specific options for MyPlugin."
                parser.add_argument(
                    "--config",
                    type=str,
                    required=True,
                   help="Path to the MyPlugin configuration file."
                )
            ```

        Note that any arguments registered with `required=True` by your plugin
        will make that argument explicitly required on the command-line.

        If you want such an argument to be able to come from the configuration
        file *and* still be "required", you should instead just verify its
        presence in your `argparse_post`

        Args:
            parser (argparse.ArgumentParser): The subparser for this deployer plugin.
        """
        raise NotImplementedError

    @staticmethod
    def argparse_post(*, args: argparse.Namespace) -> None:
        """
        Optional hook for post-processing and validating parsed command-line arguments.

        This method can be overridden by plugins to enforce additional argument
        requirements or to modify the namespace after parsing.

        Example:

            It is possible to inspect or modify `args` in place as needed

            ```
            @staticmethod
            def argparse_post(*, args: argparse.Namespace) -> None:
                if args.arg1:
                    args.arg2 = True
                )
            ```

        Args:
            args (argparse.Namespace): The result of argument parsing.
        """

    @staticmethod
    @abstractmethod
    def entrypoint(
        *, args: argparse.Namespace, certificate_bundle: CertificateBundle
    ) -> None:
        """
        Execute the deployment process.

        This method serves as the main execution hook for the deployer plugin.
        It is invoked by the framework after command-line arguments have been parsed
        and a certificate bundle has been created from the Certbot-generated files.
        The certificate bundle contains the primary certificate, private key, full chain,
        and any intermediate certificates needed for deployment.

        Plugin developers should implement this method to perform the actual deployment
        or processing of the certificates as required by their specific use-case.

        Args:
            args (argparse.Namespace): The namespace containing the parsed
                command-line arguments.
            certificate_bundle (`CertificateBundle`): The certificate bundle,
                built from the directory specified by the environment variable (or
                argument) `RENEWED_LINEAGE`, containing the certificate, key, full
                chain, and intermediate certificates.

        Returns:
        None
        """
        raise NotImplementedError
