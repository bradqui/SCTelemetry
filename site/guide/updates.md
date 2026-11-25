# Updating and checking downloads

## Updating

When a new version is out, an **Update** button appears in the top bar. Click it: Starglance downloads the new version from this project's GitHub releases, checks it, and restarts in a few seconds, with your settings as they were.

- Starglance asks GitHub which version is the latest when it starts and every few hours. Your fleet's hub also says when you're behind.
- Heard about a release before Starglance has? **Settings → Agent → Updates → Check now**.
- **Update automatically** does it by itself, while the game isn't running.
- Switched off **Check for new versions**? Then only your fleet's hub tells it, or the [releases page](https://github.com/bradqui/starglance/releases).

An update only ever comes from this project's GitHub releases, at a fixed address; a hub can say which version is current but not where to get it. Before installing, Starglance checks the download against the release's checksums.

## Checking a download

Releases aren't code-signed. Instead, every `starglance.exe` comes with a **build attestation**: a record, signed by GitHub, that this exact file was built by the project's release workflow from that release's source. Anyone can check it.

With the [GitHub CLI](https://cli.github.com):

```
gh attestation verify starglance.exe --repo bradqui/starglance
```

It names the workflow, tag and commit the file was built from, or fails if the file didn't come from this repository. Every attestation is also listed on the repository's [Attestations](https://github.com/bradqui/starglance/attestations) page. (0.7.0 and earlier don't have one.)

Without the CLI, compare the file's SHA-256 with the release's `SHA256SUMS.txt`. In PowerShell:

```
Get-FileHash starglance.exe
```

## If your antivirus flags it

Programs packaged like Starglance (Python, with PyInstaller), especially unsigned ones, are sometimes flagged by antivirus software though nothing is wrong. If Microsoft Defender flags a release:

1. Check the file as above.
2. Report it to Microsoft as a false positive at [microsoft.com/wdsi/filesubmission](https://www.microsoft.com/en-us/wdsi/filesubmission). That usually clears it within a day or two.
3. Please [open an issue](https://github.com/bradqui/starglance/issues) so others know.

For other antivirus products, use that product's false-positive form. More on how releases are built: [CODE_SIGNING.md](https://github.com/bradqui/starglance/blob/main/docs/CODE_SIGNING.md).
