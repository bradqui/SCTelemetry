# Releasing

The hub and the agent share one version number. A release consists of:

- `starglance.exe`, attached to the GitHub release;
- the hub image, `ghcr.io/bradqui/starglance-hub:<version>` and `:latest`.

The hub tells agents which version is current, using its own version, so an agent that's behind shows **Update** in the cockpit. The hub refuses agents older than `MIN_AGENT_VERSION` (in `hub/starglance_hub/__init__.py`). Raise that only when an older agent would break or mislead the fleet.

## Cutting a release

1. Set the new version in all three places:
   - `pyproject.toml`
   - `agent/starglance/__init__.py`
   - `hub/starglance_hub/__init__.py`
   
   Commit it with `uv lock` if it changed anything.
2. Tag the commit and push the tag:

   ```
   git tag v0.2.0
   git push origin v0.2.0
   ```

3. The [Release workflow](../.github/workflows/release.yml) then:
   - checks the tag matches the versions;
   - runs the tests;
   - builds the web UI and `starglance.exe`;
   - signs the exe (once SignPath is set up, below);
   - pushes the hub image;
   - publishes the GitHub release with the exe and `SHA256SUMS.txt`.
4. **If signing is set up**, SignPath emails you a signing request for approval. The workflow waits up to an hour, then the release appears with the signed exe.

To publish a tag again, for example after setting up signing, use **Actions → Release → Run workflow** with the tag. Delete the old GitHub release first.

The first time the hub image is pushed, make the package public on GitHub so servers can pull it without signing in: **Packages → starglance-hub → Package settings → Change visibility → Public**.

## Building the exe yourself

```
cd web && npm install && npm run build && cd ..
uv run --with pyinstaller==6.22.3 pyinstaller packaging/starglance.spec --noconfirm
dist\starglance.exe --help
```

## Code signing with SignPath

SignPath Foundation signs open-source projects for free, using its own certificate. The public side of it is [CODE_SIGNING.md](CODE_SIGNING.md), and the README links to it.

### Before applying

- Turn on two-factor authentication on GitHub (Settings → Password and authentication). SignPath requires it for everyone in the signing roles.
- Have at least one unsigned release out, so they can see the project ships an exe.

### Apply

Apply at https://signpath.org/apply with:
- the repository: https://github.com/bradqui/starglance;
- the license (MIT);
- what's signed: `starglance.exe`, built by GitHub Actions from this repo;
- the code signing policy: https://github.com/bradqui/starglance/blob/main/docs/CODE_SIGNING.md.

They review each project by hand, and no turnaround time is published. If they ask about the PyInstaller bootloader: it's PyInstaller's own open-source bootloader, unmodified, which every PyInstaller exe contains.

### Once accepted

In SignPath (they set up the organization and usually the project with you):

1. **Project**: slug `starglance`, linked to the GitHub repository, with *trusted build system* = GitHub.com.
2. **Artifact configuration** (the workflow uploads a zip containing `starglance.exe`):

   ```xml
   <?xml version="1.0" encoding="utf-8"?>
   <artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
     <zip-file>
       <pe-file path="starglance.exe" product-name="Starglance">
         <authenticode-sign />
       </pe-file>
     </zip-file>
   </artifact-configuration>
   ```

3. **Signing policy** `release-signing`, with:
   - the release certificate;
   - manual approval, one approver (you);
   - origin verification for tags `v*`.
4. **A CI user** with submitter rights on that policy. Make an API token for it.

In GitHub, open **Settings → Secrets and variables → Actions**:

- **Secret** `SIGNPATH_API_TOKEN`: the CI user's token.
- **Variables**:
  - `SIGNPATH_ORGANIZATION_ID`: from SignPath's organization page;
  - `SIGNPATH_PROJECT_SLUG`: `starglance`;
  - `SIGNPATH_SIGNING_POLICY_SLUG`: `release-signing`;
  - `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG`: the configuration's slug. Leave it unset for the default configuration.

The signing step in the Release workflow runs only once `SIGNPATH_ORGANIZATION_ID` is set. Until then, releases are unsigned and their notes say so.
