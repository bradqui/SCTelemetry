# Admin

Admins manage the fleet from the hub's page: **your name → Admin**.

## Members

Everyone in the fleet, with their linked PCs and whether they're live. Make someone an admin, **Suspend** them (they can't sign in or send until restored), or **Remove** them, which deletes their PCs and history.

![Admin → Members](/shots/app/hub-admin-members.jpg)

## Invites

Pick how many people can use an invite and how long it lasts, and whether it makes them a member or an admin. **Create** gives you a link to send. Revoke any invite that's still open.

![Admin → Invites](/shots/app/hub-admin-invites.jpg)

What a new member sees, and what they do with it: [Joining a fleet](/fleet/joining).

## Problem reports

When a member sends a [problem report](/guide/problem-reports) to the fleet's admins, it shows up here, with a count of new ones on the tab.

- **View** shows what they wrote and every file in the report.
- **Download** saves the report's `.zip`.
- **Open a GitHub issue** opens the project's bug form, filled in from the report, and marks it as forwarded. Attach the downloaded file to the issue.
- Set a status to keep track, or **Delete** it. Reports are deleted after 30 days anyway (`HUB_REPORT_RETENTION_DAYS`).

![Admin → Reports](/shots/app/hub-admin-reports.jpg)

The hub never sends anything to GitHub by itself: an issue is only opened when you do it, from your own browser and GitHub account.

## Integrations

API keys for a Discord bot, a stream overlay or a script: read the roster and anyone's live state, follow every event as it happens (warnings, kills, contracts, quantum jumps), and hand out invites. Enough to build a `!fleet` command, readiness checks and alerts. The key is shown once; delete it to cut it off. See the [API reference](https://github.com/bradqui/starglance/blob/main/docs/HUB_API.md).

## Settings

The org's name, Discord options, and the org's data.

### Your data

**Download everything** saves the whole hub as one file (a zip with `hub.sqlite3`): members, linked PCs, invites, settings, the event history and problem reports, with every token and key only as a hash. Keep it as a backup, or use it to run your own hub: put it in the new hub's data folder before its first start, and members link their PCs to the new address. Their accounts and history are already there.

### Hosted orgs

If someone else runs your hub for you, the sign-in page says **Hosted by** them, with a link to their privacy and terms page, and Settings shows a **Hosting** section. **Ask to close this org** (type the org's name to confirm) asks them to delete the org and everything in it; download your data first if you want to keep it. You can withdraw the request until they act on it. A hub you run yourself doesn't have this: you just stop it.

### Discord

Discord is optional; without it, everything works with invites and codes. To turn it on, connect your org's own Discord application and server under **Admin → Settings → Discord**:

1. At [discord.com/developers](https://discord.com/developers/applications), choose **New Application** and name it after your org (members see the name when they sign in).
2. On its **OAuth2** page, add the redirect the Settings page shows (your hub's address followed by `/auth/discord/callback`), and copy the **Client ID** and **Client Secret** into Settings.
3. In Discord, turn on **Developer Mode** (User Settings → Advanced). Right-click your server's icon → **Copy Server ID**. For a member role: Server Settings → Roles → right-click the role → **Copy Role ID**.
4. **Save.** The hub checks the Client ID and secret with Discord; once saved, the secret is never shown again (type a new one to change it).

This works the same whether you run the hub or someone [hosts it for you](#hosted-orgs). Then:

- invite pages offer **Join with Discord**, and members can connect Discord under **Your account** and sign in with it anywhere;
- members who connected Discord are suspended if they lose your server's member role, and restored if they get it back;
- **Admin → Settings** can let holders of the role join without an invite.
