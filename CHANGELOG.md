# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 1.0.0 - 2025-03-21
### Changed
- Add more logging to `read_config`
- Change the key for this tool in its configuration file from `main` to `certbot_deployer`

### Added
- Add new argument `--version` to print version of this tool and any plugins

## 0.2.1 - 2025-03-20
### Fixed
- Fix broken path construction for config file in $HOME

## 0.2.0 - 2025-03-19
### Added
- Introduce the ability to configure plugin arguments via central JSON config file `certbot_deploy.conf`

## 0.1.2 - 2025-03-05
### Fixed
- Fix poor handling of differences in `importlib` in Python 3.9 re `entry_points`

## 0.1.1 - 2025-02-25
### Changed
- bump patch

## 0.1.0 - 2025-02-25
### Added
- initial commit
