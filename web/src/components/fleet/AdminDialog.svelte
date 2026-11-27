<script lang="ts">
  import { onMount } from "svelte";
  import { api, copy } from "../../lib/api";
  import { ago } from "../../lib/format";
  import { issueUrl, type IssueFields } from "../../lib/issue";
  import type { Account, HubHost } from "../../lib/types";
  import Dialog from "./Dialog.svelte";

  let { me, onClose }: { me: Account; onClose: () => void } = $props();

  type Tab = "members" | "invites" | "reports" | "integrations" | "settings";
  let tab = $state<Tab>("members");
  let error = $state("");
  const now = Date.now();

  interface MemberRow extends Account {
    pcs: number;
    last_seen: number | null;
    presence: string;
  }
  interface Invite {
    id: number;
    role: string;
    note: string | null;
    expires_at: number | null;
    max_uses: number | null;
    uses: number;
  }
  interface Key {
    id: number;
    name: string;
    scopes: string[];
    created_at: number;
    last_used: number | null;
  }
  interface Settings {
    org_name: string;
    /** Discord sign-in is on (the app and server below are set up). */
    discord: boolean;
    discord_client_id: string | null;
    /** There's a client secret; it's never sent back. */
    discord_secret_set: boolean;
    discord_guild_id: string | null;
    discord_redirect_uri: string;
    discord_autojoin: boolean;
    discord_member_role_id: string | null;
    host: HubHost | null;
    close_request: { at: number; by: string } | null;
  }

  let members = $state<MemberRow[]>([]);
  let invites = $state<Invite[]>([]);
  let keys = $state<Key[]>([]);
  let settings = $state<Settings | null>(null);
  interface Report extends IssueFields {
    id: number;
    member: { id: string; name: string };
    machine: string | null;
    created_at: number;
    status: "new" | "forwarded" | "not_a_bug";
    size: number;
    windows: string | null;
  }
  let reports = $state<Report[]>([]);
  const newReports = $derived(reports.filter((r) => r.status === "new").length);

  async function run(fn: () => Promise<unknown>) {
    error = "";
    try {
      await fn();
    } catch (e) {
      error = (e as Error).message;
    }
  }
  const load = {
    members: async () => (members = await api<MemberRow[]>("GET", "/api/admin/members")),
    invites: async () => (invites = await api<Invite[]>("GET", "/api/admin/invites")),
    reports: async () => (reports = await api<Report[]>("GET", "/api/admin/reports").catch(() => [])),
    integrations: async () => (keys = await api<Key[]>("GET", "/api/admin/keys")),
    settings: async () => (settings = await api<Settings>("GET", "/api/admin/settings")),
  };
  onMount(() => run(async () => Promise.all(Object.values(load).map((f) => f()))));

  // -- members
  async function setRole(m: MemberRow, role: string) {
    await run(async () => {
      await api("PATCH", `/api/admin/members/${m.id}`, { role });
      await load.members();
    });
  }
  async function setActive(m: MemberRow, active: boolean) {
    await run(async () => {
      await api("PATCH", `/api/admin/members/${m.id}`, { active });
      await load.members();
    });
  }
  async function remove(m: MemberRow) {
    if (!confirm(`Remove ${m.name}? Their PCs are unlinked and their history is deleted.`)) return;
    await run(async () => {
      await api("DELETE", `/api/admin/members/${m.id}`);
      await load.members();
    });
  }

  // -- invites
  let invUses = $state("1");
  let invDays = $state("7");
  let invRole = $state("member");
  let invNote = $state("");
  let newInvite = $state<string | null>(null);
  let copied = $state(false);
  async function createInvite() {
    await run(async () => {
      const r = await api<{ url: string }>("POST", "/api/admin/invites", {
        uses: invUses === "none" ? null : Number(invUses),
        days: invDays === "none" ? null : Number(invDays),
        role: invRole,
        note: invNote || null,
      });
      newInvite = r.url;
      invNote = "";
      await load.invites();
    });
  }
  async function revokeInvite(i: Invite) {
    await run(async () => {
      await api("DELETE", `/api/admin/invites/${i.id}`);
      await load.invites();
    });
  }
  async function copyNow(text: string) {
    copied = await copy(text);
    setTimeout(() => (copied = false), 1500);
  }

  // -- problem reports members sent (docs/REPORTS.md)
  let openReport = $state<number | null>(null);
  let texts = $state<Record<string, string> | null>(null);
  let shown = $state("gamelog.txt");
  const STATUS: Record<Report["status"], string> = { new: "New", forwarded: "Forwarded", not_a_bug: "Not a bug" };
  async function viewReport(r: Report) {
    if (openReport === r.id) {
      openReport = null;
      return;
    }
    await run(async () => {
      texts = null;
      openReport = r.id;
      texts = (await api<{ texts: Record<string, string> }>("GET", `/api/admin/reports/${r.id}`)).texts;
      shown = texts["gamelog.txt"] ? "gamelog.txt" : "report.json";
    });
  }
  async function setStatus(r: Report, status: string) {
    await run(async () => {
      await api("PATCH", `/api/admin/reports/${r.id}`, { status });
      await load.reports();
    });
  }
  async function deleteReport(r: Report) {
    if (!confirm(`Delete ${r.member.name}'s report? It can't be brought back.`)) return;
    await run(async () => {
      await api("DELETE", `/api/admin/reports/${r.id}`);
      if (openReport === r.id) openReport = null;
      await load.reports();
    });
  }
  // Download: fetched here so the button can say what happened (a plain link saves with
  // no sign in many browsers, and a hub error would be a silent failed download).
  let saving = $state<Record<number, "busy" | "saved">>({});
  async function download(r: Report) {
    if (saving[r.id] === "busy") return;
    saving[r.id] = "busy";
    error = "";
    try {
      const res = await fetch(`/api/admin/reports/${r.id}/download`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? `The hub said ${res.status}.`);
      }
      const name =
        /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? `Starglance-report-${r.id}.zip`;
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      saving[r.id] = "saved";
      setTimeout(() => {
        if (saving[r.id] === "saved") delete saving[r.id];
      }, 2500);
    } catch (e) {
      delete saving[r.id];
      error = `Couldn't download the report: ${(e as Error).message}`;
    }
  }
  function forward(r: Report) {
    window.open(
      issueUrl(r, "Sent through a fleet hub. Report file: drop it here."),
      "_blank",
      "noopener,noreferrer",
    );
    if (r.status === "new") void setStatus(r, "forwarded");
  }
  const kb = (n: number) => (n < 1024 ? `${n} B` : `${Math.round(n / 1024)} KB`);

  // -- integrations
  let keyName = $state("");
  let keyRead = $state(true);
  let keyInvites = $state(false);
  let newKey = $state<string | null>(null);
  async function createKey() {
    await run(async () => {
      const scopes = [...(keyRead ? ["read"] : []), ...(keyInvites ? ["invites"] : [])];
      const r = await api<{ key: string }>("POST", "/api/admin/keys", { name: keyName || "Integration", scopes });
      newKey = r.key;
      keyName = "";
      await load.integrations();
    });
  }
  async function deleteKey(k: Key) {
    if (!confirm(`Delete the key "${k.name}"? Anything using it stops working.`)) return;
    await run(async () => {
      await api("DELETE", `/api/admin/keys/${k.id}`);
      await load.integrations();
    });
  }

  // -- settings
  let saved = $state(false);
  /** A new client secret; empty keeps the saved one. */
  let discordSecret = $state("");
  async function saveSettings() {
    if (!settings) return;
    await run(async () => {
      settings = await api<Settings>("PUT", "/api/admin/settings", {
        org_name: settings!.org_name,
        discord_client_id: settings!.discord_client_id,
        discord_client_secret: discordSecret,
        discord_guild_id: settings!.discord_guild_id,
        discord_autojoin: settings!.discord_autojoin,
        discord_member_role_id: settings!.discord_member_role_id,
      });
      discordSecret = "";
      saved = true;
      setTimeout(() => (saved = false), 1500);
    });
  }
  async function discordOff() {
    if (!confirm("Turn off Discord sign-in? Members sign in with their PCs' links or codes instead.")) return;
    await run(async () => {
      settings = await api<Settings>("PUT", "/api/admin/settings", {
        discord_client_id: "",
        discord_guild_id: "",
        discord_clear_secret: true,
      });
      discordSecret = "";
    });
  }
  let copiedRedirect = $state(false);
  async function copyRedirect() {
    if (!settings) return;
    await copy(settings.discord_redirect_uri);
    copiedRedirect = true;
    setTimeout(() => (copiedRedirect = false), 1500);
  }

  // -- the org's data, and closing a hosted org (spec decision 28)
  let exporting = $state<"busy" | "saved" | null>(null);
  async function downloadAll() {
    if (exporting === "busy") return;
    exporting = "busy";
    error = "";
    try {
      const res = await fetch("/api/admin/export");
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? `The hub said ${res.status}.`);
      }
      const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? "starglance-data.zip";
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      exporting = "saved";
      setTimeout(() => {
        if (exporting === "saved") exporting = null;
      }, 2500);
    } catch (e) {
      exporting = null;
      error = `Couldn't download the data: ${(e as Error).message}`;
    }
  }
  let closeName = $state("");
  async function askToClose() {
    await run(async () => {
      settings = await api<Settings>("POST", "/api/admin/close", { confirm: closeName });
      closeName = "";
    });
  }
  async function cancelClose() {
    await run(async () => {
      settings = await api<Settings>("DELETE", "/api/admin/close");
    });
  }

  const day = (ms: number) => new Date(ms).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

  function expires(i: Invite): string {
    if (!i.expires_at) return "never expires";
    const days = Math.ceil((i.expires_at - now) / 86_400_000);
    return days <= 1 ? "expires today" : `expires in ${days} days`;
  }
</script>

<Dialog title="Admin" wide {onClose}>
  <nav class="tabs">
    {#each [["members", "Members"], ["invites", "Invites"], ["reports", "Reports"], ["integrations", "Integrations"], ["settings", "Settings"]] as [id, label] (id)}
      <button class="tap" style:--tap="7px" class:on={tab === id} onclick={() => (tab = id as Tab)}
        >{label}{#if id === "reports" && newReports}<span class="count">{newReports}</span>{/if}</button
      >
    {/each}
  </nav>
  {#if error}<p class="error">{error}</p>{/if}

  {#if tab === "members"}
    <section>
      <div class="list">
        {#each members as m (m.id)}
          <div class="item" class:off={!m.active}>
            <span class="grow"
              ><b>{m.name}</b>{#if m.id === me.id}<small class="you">you</small>{/if}
              <small>
                · {m.pcs} PC{m.pcs === 1 ? "" : "s"}
                · {m.presence === "offline" ? (m.last_seen ? `seen ${ago(m.last_seen, now)}` : "never seen") : m.presence}
                {#if m.discord}· Discord{/if}
                {#if !m.active}· <span class="sus">suspended</span>{/if}
              </small></span
            >
            <select value={m.role} onchange={(e) => setRole(m, (e.target as HTMLSelectElement).value)} aria-label="Role">
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
            {#if m.id !== me.id}
              <button class="btn" onclick={() => setActive(m, !m.active)}>{m.active ? "Suspend" : "Restore"}</button>
              <button class="btn danger" onclick={() => remove(m)}>Remove</button>
            {/if}
          </div>
        {/each}
      </div>
    </section>
  {:else if tab === "invites"}
    <section>
      <h3>New invite</h3>
      <div class="row">
        <select bind:value={invUses} aria-label="Uses">
          <option value="1">1 use</option>
          <option value="5">5 uses</option>
          <option value="25">25 uses</option>
          <option value="none">Unlimited uses</option>
        </select>
        <select bind:value={invDays} aria-label="Expires">
          <option value="1">1 day</option>
          <option value="7">7 days</option>
          <option value="30">30 days</option>
          <option value="none">Never expires</option>
        </select>
        <select bind:value={invRole} aria-label="Role">
          <option value="member">Member</option>
          <option value="admin">Admin</option>
        </select>
        <input type="text" bind:value={invNote} placeholder="Note (who it's for)" maxlength="80" />
        <button class="btn primary" onclick={createInvite}>Create</button>
      </div>
      {#if newInvite}
        <p style="margin-top:10px">Send this link. Players run <code>starglance link &lt;link&gt;</code>; anyone can also open it in a browser.</p>
        <div class="secret">
          <code>{newInvite}</code>
          <button class="btn" onclick={() => copyNow(newInvite!)}>{copied ? "Copied" : "Copy"}</button>
        </div>
      {/if}
    </section>
    <section>
      <h3>Open invites</h3>
      <div class="list">
        {#each invites as i (i.id)}
          <div class="item">
            <span class="grow"
              ><b>{i.note ?? (i.role === "admin" ? "Admin invite" : "Invite")}</b>
              <small>· {i.uses}{i.max_uses ? `/${i.max_uses}` : ""} used · {expires(i)}{i.role === "admin" ? " · admin" : ""}</small></span
            >
            <button class="btn danger" onclick={() => revokeInvite(i)}>Revoke</button>
          </div>
        {:else}
          <p>None. Links are only shown when they're created.</p>
        {/each}
      </div>
    </section>
  {:else if tab === "reports"}
    <section>
      <p>
        Problem reports members sent from Starglance (Report a problem). They hold a few minutes of their telemetry and Game.log,
        with names, IDs and addresses taken out, and are deleted after 30 days. A real bug? <b>Open a GitHub issue</b> fills in the
        project's bug form; download the report and drop it in.
      </p>
      <div class="list">
        {#each reports as r (r.id)}
          <div class="report" class:done={r.status !== "new"}>
            <div class="item">
              <span class="grow"
                ><b>{r.what.split("\n")[0] || "Problem report"}</b>
                <small
                  >{r.member.name}{r.machine ? ` (${r.machine})` : ""} · {ago(r.created_at, now)} · Starglance {r.agent_version ?? "?"}{r.game
                    ? ` · ${r.game}`
                    : ""} · {kb(r.size)}</small
                ></span
              >
              <select value={r.status} onchange={(e) => setStatus(r, (e.target as HTMLSelectElement).value)} aria-label="Status">
                {#each Object.entries(STATUS) as [id, label] (id)}<option value={id}>{label}</option>{/each}
              </select>
            </div>
            <div class="row">
              <button class="btn" onclick={() => viewReport(r)}>{openReport === r.id ? "Hide" : "View"}</button>
              <button
                class="btn"
                class:saved={saving[r.id] === "saved"}
                disabled={saving[r.id] === "busy"}
                onclick={() => download(r)}
                >{saving[r.id] === "busy" ? "Downloading…" : saving[r.id] === "saved" ? "Saved ✓" : "Download"}</button
              >
              <button class="btn" onclick={() => forward(r)}>Open a GitHub issue</button>
              <button class="btn danger" onclick={() => deleteReport(r)}>Delete</button>
            </div>
            {#if openReport === r.id}
              {#if r.expected}<p><b>Expected:</b> {r.expected}</p>{/if}
              {#if r.part}<p><b>Where:</b> {r.part}</p>{/if}
              {#if texts}
                <nav class="files">
                  {#each Object.keys(texts) as name (name)}
                    <button class:on={shown === name} onclick={() => (shown = name)}>{name}</button>
                  {/each}
                </nav>
                <pre>{texts[shown] || "(empty)"}</pre>
              {:else}
                <p>Loading…</p>
              {/if}
            {/if}
          </div>
        {:else}
          <p>None yet. Members send them from Starglance: Report a problem, then Send to my fleet's admins.</p>
        {/each}
      </div>
    </section>
  {:else if tab === "integrations"}
    <section>
      <p>
        API keys let a Discord bot or a script read the fleet, follow events and create invites.
        See <code>docs/HUB_API.md</code> in the project.
      </p>
      <div class="row">
        <input type="text" bind:value={keyName} placeholder="Name (e.g. Discord bot)" maxlength="32" />
        <label><input type="checkbox" bind:checked={keyRead} /> Read the fleet</label>
        <label><input type="checkbox" bind:checked={keyInvites} /> Create invites</label>
        <button class="btn primary" onclick={createKey}>Create key</button>
      </div>
      {#if newKey}
        <p style="margin-top:10px">Copy it now: it isn't shown again.</p>
        <div class="secret">
          <code>{newKey}</code>
          <button class="btn" onclick={() => copyNow(newKey!)}>{copied ? "Copied" : "Copy"}</button>
        </div>
      {/if}
    </section>
    <section>
      <h3>Keys</h3>
      <div class="list">
        {#each keys as k (k.id)}
          <div class="item">
            <span class="grow"
              ><b>{k.name}</b>
              <small>· {k.scopes.join(", ")} · {k.last_used ? `used ${ago(k.last_used, now)}` : "never used"}</small></span
            >
            <button class="btn danger" onclick={() => deleteKey(k)}>Delete</button>
          </div>
        {:else}
          <p>No keys yet.</p>
        {/each}
      </div>
    </section>
  {:else if settings}
    <section>
      <h3>Org name</h3>
      <div class="row"><input type="text" bind:value={settings.org_name} maxlength="32" /></div>
    </section>
    <section>
      <h3>Discord</h3>
      {#if settings.discord}
        <p>On: members can connect Discord and sign in with it, through your own Discord application.</p>
      {:else}
        <p>Off. To offer "Sign in with Discord", connect your org's Discord application and server:</p>
      {/if}
      <details class="howto" open={!settings.discord}>
        <summary>How to set it up</summary>
        <ol>
          <li>
            At <a href="https://discord.com/developers/applications" target="_blank" rel="noopener noreferrer"
              >discord.com/developers</a
            >, choose <b>New Application</b> and name it after your org (members see the name when they sign in).
          </li>
          <li>
            On its <b>OAuth2</b> page, add this redirect, then copy the Client ID and Client Secret below:
            <span class="row redirect"
              ><code>{settings.discord_redirect_uri}</code>
              <button class="btn" onclick={copyRedirect}>{copiedRedirect ? "Copied" : "Copy"}</button></span
            >
          </li>
          <li>
            In Discord, turn on <b>Developer Mode</b> (User Settings → Advanced). Right-click your server's icon →
            <b>Copy Server ID</b>; for a member role, Server Settings → Roles → right-click it → <b>Copy Role ID</b>.
          </li>
        </ol>
      </details>
      <div class="fields">
        <span>Client ID</span>
        <input type="text" bind:value={settings.discord_client_id} inputmode="numeric" autocomplete="off" />
        <span>Client secret</span>
        <input
          type="password"
          bind:value={discordSecret}
          autocomplete="new-password"
          placeholder={settings.discord_secret_set ? "Saved (type a new one to change it)" : ""}
        />
        <span>Server ID</span>
        <input type="text" bind:value={settings.discord_guild_id} inputmode="numeric" autocomplete="off" />
        <span>Member role ID</span>
        <input
          type="text"
          bind:value={settings.discord_member_role_id}
          inputmode="numeric"
          placeholder="Any member of the server"
        />
      </div>
      <p>
        Only Discord accounts in your server can sign in. With a member role, only its holders can, and members who
        connected Discord are suspended if they lose it (restored if they get it back).
      </p>
      {#if settings.discord}
        <label class="row"
          ><input type="checkbox" bind:checked={settings.discord_autojoin} /> Holders of the member role can join without an
          invite</label
        >
      {/if}
    </section>
    <div class="row">
      <button class="btn primary" onclick={saveSettings}>{saved ? "Saved" : "Save"}</button>
      {#if settings.discord}<button class="btn" onclick={discordOff}>Turn off Discord</button>{/if}
    </div>
    <section class="apart">
      <h3>Your data</h3>
      <p>
        Everything this hub keeps, as one file: members, linked PCs, invites, settings, the event history and problem
        reports (tokens and keys only as hashes). Keep it as a backup, or run it as your own hub.
      </p>
      <div class="row">
        <button class="btn" class:saved={exporting === "saved"} disabled={exporting === "busy"} onclick={downloadAll}
          >{exporting === "busy" ? "Preparing…" : exporting === "saved" ? "Saved ✓" : "Download everything"}</button
        >
      </div>
    </section>
    {#if settings.host}
      <section>
        <h3>Hosting</h3>
        <p>
          {settings.host.name} runs this hub for {settings.org_name}{#if settings.host.url}{" "}(<a
              href={settings.host.url}
              target="_blank"
              rel="noopener noreferrer">privacy and terms</a
            >){/if}.
        </p>
        {#if settings.close_request}
          <p class="closing">
            {settings.close_request.by} asked {settings.host.name} on {day(settings.close_request.at)} to close this org.
            They delete the org and all its data; download it first if you want to keep it.
          </p>
          <div class="row"><button class="btn" onclick={cancelClose}>Withdraw the request</button></div>
        {:else}
          <p>
            Closing the org asks {settings.host.name} to delete it and everything in it. Download your data first if you
            want to keep it or move to your own hub. To confirm, type the org's name.
          </p>
          <div class="row">
            <input type="text" bind:value={closeName} placeholder={settings.org_name} aria-label="The org's name" />
            <button
              class="btn danger"
              disabled={closeName.trim().toLowerCase() !== settings.org_name.trim().toLowerCase()}
              onclick={askToClose}>Ask to close this org</button
            >
          </div>
        {/if}
      </section>
    {/if}
  {/if}
</Dialog>

<style>
  .tabs {
    display: flex;
    gap: 2px;
    margin-bottom: 12px;
    border-bottom: 1px solid var(--line);
  }
  .tabs button {
    border: 0;
    background: none;
    padding: 6px 12px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-3);
    border-bottom: 2px solid transparent;
    cursor: pointer;
  }
  .tabs button.on {
    color: var(--text);
    border-bottom-color: var(--accent);
  }
  .count {
    margin-left: 6px;
    padding: 0 5px;
    border-radius: 8px;
    background: var(--warn);
    color: var(--bg);
    font-size: 0.68rem;
  }
  .report {
    display: grid;
    gap: 6px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--line);
  }
  .report.done b {
    color: var(--text-2);
  }
  .report p {
    margin: 0;
    font-size: 0.85rem;
  }
  .files {
    display: flex;
    gap: 3px;
    flex-wrap: wrap;
  }
  .files button {
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    color: var(--text-2);
    padding: 2px 8px;
    font-size: 0.75rem;
    cursor: pointer;
  }
  .files button.on {
    color: var(--text);
    border-color: var(--accent);
  }
  pre {
    margin: 0;
    max-height: 320px;
    overflow: auto;
    padding: 8px 10px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    font-family: var(--mono);
    font-size: 0.72rem;
    white-space: pre;
  }
  .btn.saved {
    color: var(--good);
    border-color: var(--good);
  }
  .apart {
    margin-top: 22px;
  }
  .closing {
    color: var(--warn);
  }
  .howto {
    margin: 4px 0 8px;
    font-size: 0.82rem;
    color: var(--text-2);
  }
  .howto summary {
    cursor: pointer;
    color: var(--text);
  }
  .howto ol {
    margin: 6px 0 0;
    padding-left: 20px;
    display: grid;
    gap: 6px;
  }
  .redirect {
    margin-top: 4px;
    flex-wrap: wrap;
  }
  .redirect code {
    font-family: var(--mono);
    font-size: 0.75rem;
    overflow-wrap: anywhere;
  }
  .fields {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 6px 10px;
    align-items: center;
    max-width: 520px;
    font-size: 0.82rem;
    color: var(--text-2);
  }
  .item.off b {
    color: var(--text-3);
  }
  .sus {
    color: var(--warn);
  }
  .you {
    margin-left: 6px;
    color: var(--accent) !important;
  }
  label {
    font-size: 0.82rem;
    color: var(--text-2);
    display: inline-flex;
    gap: 5px;
    align-items: center;
  }
</style>
