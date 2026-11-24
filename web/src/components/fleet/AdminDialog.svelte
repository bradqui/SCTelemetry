<script lang="ts">
  import { onMount } from "svelte";
  import { api, copy } from "../../lib/api";
  import { ago } from "../../lib/format";
  import type { Account } from "../../lib/types";
  import Dialog from "./Dialog.svelte";

  let { me, onClose }: { me: Account; onClose: () => void } = $props();

  type Tab = "members" | "invites" | "integrations" | "settings";
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
    discord: boolean;
    discord_autojoin: boolean;
    discord_member_role_id: string | null;
  }

  let members = $state<MemberRow[]>([]);
  let invites = $state<Invite[]>([]);
  let keys = $state<Key[]>([]);
  let settings = $state<Settings | null>(null);

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
  async function saveSettings() {
    if (!settings) return;
    await run(async () => {
      settings = await api<Settings>("PUT", "/api/admin/settings", {
        org_name: settings!.org_name,
        discord_autojoin: settings!.discord_autojoin,
        discord_member_role_id: settings!.discord_member_role_id,
      });
      saved = true;
      setTimeout(() => (saved = false), 1500);
    });
  }

  function expires(i: Invite): string {
    if (!i.expires_at) return "never expires";
    const days = Math.ceil((i.expires_at - now) / 86_400_000);
    return days <= 1 ? "expires today" : `expires in ${days} days`;
  }
</script>

<Dialog title="Admin" wide {onClose}>
  <nav class="tabs">
    {#each [["members", "Members"], ["invites", "Invites"], ["integrations", "Integrations"], ["settings", "Settings"]] as [id, label] (id)}
      <button class:on={tab === id} onclick={() => (tab = id as Tab)}>{label}</button>
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
        <p>Members can connect Discord and sign in with it.</p>
        <label class="row"
          ><input type="checkbox" bind:checked={settings.discord_autojoin} /> Holders of the member role can join without an
          invite</label
        >
        <div class="row" style="margin-top:6px">
          <span>Member role id</span>
          <input type="text" bind:value={settings.discord_member_role_id} placeholder="Any member of the server" />
        </div>
        <p style="margin-top:6px">
          Members who connected Discord are suspended if they lose this role, and restored if they get it back.
        </p>
      {:else}
        <p>Off. To offer "Sign in with Discord", set the DISCORD_* settings in the hub's <code>.env</code>.</p>
      {/if}
    </section>
    <div class="row"><button class="btn primary" onclick={saveSettings}>{saved ? "Saved" : "Save"}</button></div>
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
