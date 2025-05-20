certbot_deployer
===========

<p align="center">
  <a href="#resources">
      <img width="400" src="https://raw.githubusercontent.com/theias/certbot_deployer/refs/heads/main/docs/logo.png" />
  </a>
</p>


Certbot Deployer is a pluggable deploy hook framework for [Certbot] that streamlines the process of deploying certificates managed by Certbot.

The `certbot_deployer` package supports two primary use cases:

* Command-line usage: `certbot-deployer` is intended to be run as a deploy hook launched by Certbot in order to deploy the certificates to arbitrary endpoints e.g. appliances, external machines, etc.
* Plugin development: the library's API is used to build custom deployment plugins

# Official Certbot Deployer plugins

* [Certbot Deployer BIG-IP]
* [Certbot Deployer vSphere]

# Installation

You can install with [pip]:

```sh
python3 -m pip install certbot_deployer
# Also install any needed plugins, or the tool will effectively do nothing
# python3 -m pip install certbot_deployer_<someplugin>
```

Or install from source:

```sh
git clone <url>
pip install certbot_deployer
```

# Usage

Certbot Deployer depends on plugins to actually do any work. Refer to the documentation for a particular plugin for its details, but the general form of this tool's usage will resemble the following:

```sh
# Note that the environment variable RENEWED_LINEAGE must be present for
# Certbot Deployer to work (it is automatically provided by Certbot when launching
# deploy hooks)
certbot-deployer  pluginname --pluginarg1 --pluginarg2
```

## Configuration file

It is possible to set default argument values for this tool and all plugins in a central configuration file. The following locations will be checked in order:

* `${XDG_CONFIG_HOME}/certbot_deployer/certbot_deployer.conf`
* `${HOME}/.config/certbot_deployer/certbot_deployer.conf`
* `/etc/certbot_deployer/certbot_deployer.conf`

The config file should look like the following:

```json
{
  "certbot_deployer": {
    "verbosity": 1
  },
  "pluginname": {
    "string_option": "string_value",
    "int_option": 999,
    "option_that_takes_no_value": true,
    "list_option": [
      "listopt1",
      "listopt2"
    ]
  },
  "pluginname2": {
    "option": "value"
  }
}
```


## As a Certbot deploy hook

See [Certbot User Guide] for detailed documentation on Certbot.

As with any deploy hook, Certbot Deployer can be used as an argument for cert creation or renewal.

It is possible to run the deploy hook with a specific certificate:

```sh
certbot certonly --standalone -d 'sub.domain.tld' --deploy-hook "certbot-deployer pluginname --pluginarg1 --pluginarg2"
```

If all of the certificates managed by Certbot are being deployed with the same deployer plugin, it can be applied across the board:

```sh
certbot renew --deploy-hook "certbot-deployer pluginname --pluginarg1 --pluginarg2"
```

Certbot can also be configured to run specific hook commands on specific certificates in `${certbot_dir}/renewal/sub.domain.tld.conf`. See [Certbot Configuration File] for more on this.

# Plugin development

(For reference: [Certbot Deployer plugin API reference])

Certbot Deployer is a framework that delegates certificate deployment tasks to deployer plugins - it effectively does nothing without any plugins.

These plugins are created by subclassing the abstract `Deployer` class, which defines the public interface for implementing custom deployment logic.

To implement your own deployer as a plugin, subclass `Deployer` and implement a small handful of requirements.

This design enables Certbot Deployer to automatically register, parse, and dispatch to your deployer plugin based on user input.

```python
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

And with the following in your plugin's `setup.cfg`:

```
[options.entry_points]
certbot_deployer.plugins =
    example = certbot_deployer_example:ExampleDeployer

```

The plugin can be installed into the same environment as this tool, and the new
deployer can be called as follows:

```
$ certbot_deployer example --message "Hello, World!"
Executing deployment with message: Hello, World!
```

See full developer documentation: [Certbot Deployer plugin API reference]

## Testing

The `certbot_deployer` package ships with a `testing` feature which includes downstream dependencies for the included pytest fixtures to assist in plugin testing.

To install required dependencies (pytest) to use testing fixtures:

```sh
python3 -m pip install certbot_deployer[testing]
```

See [Certbot Deployer plugin development/testing] for more.

# Contributing

Merge requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

To run the test suite:

```bash
# Dependent targets create venv and install dependencies
make
```

Please make sure to update tests along with any changes.

# License

License :: OSI Approved :: MIT License

# Resources

Logo sources:

* [Wings by Lorc CC-BY-3.0](https://game-icons.net/1x1/lorc/feathered-wing.html)
* [Robot by Delapouite CC-BY-3.0](https://game-icons.net/1x1/delapouite/mono-wheel-robot.html)
* [Lock by Skoll CC-BY-3.0](https://game-icons.net/1x1/skoll/combination-lock.html)



[Certbot Configuration File]: https://eff-certbot.readthedocs.io/en/stable/using.html#configuration-file
[Certbot Deployer BIG-IP]: https://github.com/theias/certbot_deployer_bigip
[Certbot Deployer plugin API reference/testing]: https://theias.github.io/certbot_deployer/test/testing
[Certbot Deployer plugin API reference]: https://theias.github.io/certbot_deployer/
[Certbot Deployer vSphere]: https://github.com/theias/certbot_deployer_vsphere
[Certbot User Guide]: https://eff-certbot.readthedocs.io/en/stable/using.html
[Certbot]: https://certbot.eff.org/
[pip]: https://pip.pypa.io/en/stable/
