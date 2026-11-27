# Releasing

The hub and the agent share one version number. A release consists of:

- `starglance.exe`, attached to the GitHub release;
- the hub image, `ghcr.io/bradqui/starglance-hub:<version>` and `:latest`.

Agents learn of the release from GitHub's "latest release" (they check at start and every few hours), and from hubs, which announce their own version: an agent that's behind shows **Update** in the cockpit. Publish the release only once its assets are attached: the moment it's "latest", agents may download it. The hub refuses agents older than `MIN_AGENT_VERSION` (in `hub/starglance_hub/__init__.py`). Raise that only when an older agent would break or mislead the fleet.

## Cutting a release

`main` only changes through pull requests whose checks pass, so the version bump goes through one too.

1. On a branch, set the new version in all three places:
   - `pyproject.toml`
   - `agent/starglance/__init__.py`
   - `hub/starglance_hub/__init__.py`

   and add its section at the top of [CHANGELOG.md](../CHANGELOG.md): `## 0.2.0 (2026-11-24)`, then what changed, in words players and org admins use (what they'll notice, not how it's done), under `### Hub` or `### App` when a release has both. The release's notes and its Discord announcement are that section, and the workflow refuses a tag without one.

   Commit it with `uv lock` if it changed anything (it can go in the pull request with the changes it releases), open a pull request, and merge it once the checks pass.
2. Tag the merged commit on `main` and push the tag:

   ```
   git switch main && git pull
   git tag v0.2.0
   git push origin v0.2.0
   ```

3. The [Release workflow](../.github/workflows/release.yml) then:
   - checks the tag matches the versions;
   - runs the tests;
   - builds the web UI and `starglance.exe`;
   - signs the exe (only if SignPath is set up, below; releases are unsigned for now);
   - records a build attestation for the exe (`actions/attest`), so anyone can check where it came from;
   - pushes the hub image;
   - publishes the GitHub release with the exe and `SHA256SUMS.txt`, its notes starting with the changelog section;
   - posts that section to Discord, if set up (below).

   Keep those two names: the app's **Update** button downloads exactly `starglance.exe` and `SHA256SUMS.txt` from the `v<version>` release, and checks one against the other.
4. **If signing is set up**, SignPath emails you a signing request for approval. The workflow waits up to an hour, then the release appears with the signed exe.

To publish a tag again, for example after setting up signing, use **Actions → Release → Run workflow** with the tag. Delete the old GitHub release first.

To try a change to `release.yml` before it ships, run it from your branch with **dry run** ticked and an existing tag, or `gh workflow run release.yml --ref <branch> -f tag=v<version> -f dry_run=true`. It builds and tests the exe and the hub image and passes them between the jobs, but signs, pushes and publishes nothing.

### Announcing releases on Discord

Each release can post its changelog to a Discord channel through a webhook. In the channel's settings: **Integrations → Webhooks → New Webhook**, name it Starglance, **Copy Webhook URL**. Then in this repository: **Settings → Secrets and variables → Actions → New repository secret**, named `DISCORD_RELEASE_WEBHOOK`, with the URL as its value. Without the secret, releases just aren't announced; a failed post doesn't fail the release. Treat the URL like a password: anyone with it can post in that channel.

The first time the hub image is pushed, make the package public on GitHub so servers can pull it without signing in: **Packages → starglance-hub → Package settings → Change visibility → Public**.

## Docs site

The docs and the live demos are published on GitHub Pages, at https://www.starglance.app/, by the [Docs site workflow](../.github/workflows/pages.yml) whenever `main` changes (it also builds, without publishing, on pull requests that touch them). The guide is Markdown in `site/` ([VitePress](https://vitepress.dev)); the demos are `web/demo/` (the real cockpit view and fleet page on the bundled recordings).

```
cd site && npm install
npm run demo                 # builds the demos into public/demo/ (needs uv and web's npm install)
npx playwright install chromium
npm run shots -- demo clips  # screenshots and clips of the demos (the workflow does this itself)
npm run dev                  # the site with live reload on http://localhost:5173/
```

The demo screenshots and clips are made fresh on every deploy, so they always match the release. The screens the demos can't show (Agent settings, problem reports, the hub's admin) come from a real agent and test hub: `npm run shots -- app` runs both in a temporary folder, with a made-up handle and PC name, and writes `site/public/shots/app/`, which is committed. Run it after changing those screens, and look at every picture before committing it.

When a feature changes, change its page in `site/` in the same pull request.

One-time setup (done): **Settings → Pages → Source: GitHub Actions**.

## Building the exe yourself

```
cd web && npm install && npm run build && cd ..
uv run --extra app --with pyinstaller==6.22.3 pyinstaller packaging/starglance.spec --noconfirm
dist\starglance.exe --help
```

After a release, check it end to end: download `starglance.exe` and `SHA256SUMS.txt` from the release, then `sha256sum -c SHA256SUMS.txt` and `gh attestation verify starglance.exe --repo bradqui/starglance`.

## Code signing

Releases are unsigned for now; [CODE_SIGNING.md](CODE_SIGNING.md) says so publicly and explains how to verify a download instead. The options, for when signing is worth it:

- **SignPath Foundation** (below): free, with its certificate, for open-source projects that already have a public following (stars, forks, contributors, articles or discussions elsewhere). Apply again once Starglance has that.
- **Azure Artifact Signing**: $9.99 a month (Basic). Individuals must be in the US or Canada and pass an ID check; the certificate shows the publisher's legal name, city, state and country. Microsoft has a GitHub Action for it.
- **Certum Open Source Code Signing**: about €69 a year, for individuals, "Open Source Developer, *your name*". The key is in Certum's SimplySign cloud, which wants a one-time code per session, so it's awkward to run unattended in Actions.

Pick one and keep it: once a release is signed, the app's updater only installs updates signed by the same publisher, so moving to another certificate later would stop automatic updates for everyone on the signed version.

### SignPath

SignPath Foundation signs open-source projects for free, using its own certificate. Its rules ask for a public code signing policy page: rewrite [CODE_SIGNING.md](CODE_SIGNING.md) to say which certificate signs releases, with its credit line ("Free code signing provided by SignPath.io, certificate by SignPath Foundation") at the top, roles for approvers, and SignPath's contact for reports.

#### Before applying

- Turn on two-factor authentication on GitHub (Settings → Password and authentication). SignPath requires it for everyone in the signing roles.
- Have at least one unsigned release out, so they can see the project ships an exe.

#### Apply

Apply at https://signpath.org/apply with:
- the repository: https://github.com/bradqui/starglance;
- the license (MIT);
- what's signed: `starglance.exe`, built by GitHub Actions from this repo;
- the code signing policy: https://github.com/bradqui/starglance/blob/main/docs/CODE_SIGNING.md.

They review each project by hand, and no turnaround time is published. If they ask about the PyInstaller bootloader: it's PyInstaller's own open-source bootloader, unmodified, which every PyInstaller exe contains.

#### Once accepted

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
