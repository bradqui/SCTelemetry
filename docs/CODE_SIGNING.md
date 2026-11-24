# Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org).

## What is signed

`starglance.exe`, the Windows agent attached to each [release](https://github.com/bradqui/starglance/releases). Nothing else is signed with this certificate.

Every signed file is built by the [Release workflow](../.github/workflows/release.yml) on GitHub-hosted runners, from a tagged commit of this public repository. The build runs the tests, builds the web UI, and packages the agent with PyInstaller. The resulting file is submitted to SignPath from that same workflow run. Each signing request is approved by hand on SignPath before the file is signed.

The exe contains this project's code plus open-source dependencies, unmodified, as installed from PyPI and npm. The full list is in `pyproject.toml`, `uv.lock` and `web/package-lock.json`, and the build uses the PyInstaller bootloader.

## Team roles

| Role | Members |
|---|---|
| Committers and reviewers | [@bradqui](https://github.com/bradqui) (owner) |
| Approvers | [@bradqui](https://github.com/bradqui) (owner) |

Changes from anyone else come in as pull requests and are reviewed by a committer before merging. Everyone in these roles uses multi-factor authentication on GitHub and on SignPath.

## Privacy

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

In particular, the agent connects only to the game on the same PC and to the fleet hubs the user links it to (each from an invite link). It sends each hub only what the user chooses to share with that fleet. See the [privacy policy](../PRIVACY.md) for exactly what's read, sent and stored.

## Reporting

If you think something signed with this certificate is malicious or was not built from this repository, tell us via a [GitHub security advisory](https://github.com/bradqui/starglance/security/advisories/new) or an issue. You can also report it to SignPath at support@signpath.io.
