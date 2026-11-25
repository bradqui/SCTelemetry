# Code signing and verifying downloads

**Releases of `starglance.exe` aren't code-signed.** A signing certificate costs money every year, and the free program for open-source projects ([SignPath Foundation](https://signpath.org)) takes projects once they have a wider following. Starglance may apply again later. Until then:

- Windows SmartScreen may warn the first time you run a download: choose **More info → Run anyway**. Updates that Starglance installs itself don't show the warning.
- Every release has a **build attestation** instead: a record, signed by GitHub, that the exact file was built by this repository's release workflow from that release's tag. You can check it yourself (below).

## How releases are built

`starglance.exe`, the Windows agent attached to each [release](https://github.com/bradqui/starglance/releases), is built by the [Release workflow](../.github/workflows/release.yml) on GitHub-hosted runners, from a tagged commit of this public repository. The build runs the tests, builds the web UI, and packages the agent with PyInstaller. The same workflow run records the attestation and the file's SHA-256 (`SHA256SUMS.txt`) and publishes the release. Nobody uploads an exe by hand.

The exe contains this project's code plus open-source dependencies, unmodified, as installed from PyPI and npm. The full list is in `pyproject.toml`, `uv.lock` and `web/package-lock.json`, and the build uses PyInstaller's own open-source bootloader.

## Checking a download

With the [GitHub CLI](https://cli.github.com):

```
gh attestation verify starglance.exe --repo bradqui/starglance
```

It prints the workflow, tag and commit the file was built from, or fails if the file wasn't built by this repository. Every attestation is also listed on the repository's [Attestations](https://github.com/bradqui/starglance/attestations) page.

Without the CLI, compare the file's SHA-256 with the release's `SHA256SUMS.txt`, in PowerShell:

```
Get-FileHash starglance.exe
```

That shows the file wasn't damaged or swapped on the way, as long as you trust the release page itself.

## Antivirus warnings

Programs packaged with PyInstaller, especially unsigned ones, are sometimes flagged by antivirus software even though nothing is wrong with them. If Microsoft Defender flags a release, check it as above and report it to Microsoft as a false positive at <https://www.microsoft.com/en-us/wdsi/filesubmission> (that usually clears it in a day or two), and please tell us in an issue. For other antivirus products, use that product's false-positive form.

## Team roles

| Role | Members |
|---|---|
| Committers, reviewers and release managers | [@bradqui](https://github.com/bradqui) (owner) |

Changes from anyone else come in as pull requests and are reviewed by a committer before merging. Releases are tagged from `main` after the merge. Everyone in these roles uses multi-factor authentication on GitHub.

## If releases are signed later

Starglance's updater installs an unsigned update over an unsigned copy, and once a copy is signed it only accepts updates signed by the same publisher. So the first signed release reaches everyone as a normal update, and from then on the publisher stays the same. This page will say which certificate is used.

## Privacy

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

In particular, the agent connects only to the game on the same PC and to the fleet hubs the user links it to (each from an invite link). It sends each hub only what the user chooses to share with that fleet. At start and every few hours it asks this repository's GitHub page which release is the latest (unless switched off), sending nothing else. When the user clicks **Update**, or has switched on automatic updates, it downloads the new release's `starglance.exe` and checksums from this repository's GitHub releases. Before replacing itself it checks the checksum and, for a signed build, that the new file is signed by the same publisher. See the [privacy policy](../PRIVACY.md) for exactly what's read, sent and stored.

## Reporting

If you think a release is malicious or was not built from this repository, tell us via a [GitHub security advisory](https://github.com/bradqui/starglance/security/advisories/new) or an issue.
