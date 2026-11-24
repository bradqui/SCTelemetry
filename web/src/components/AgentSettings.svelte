<script lang="ts">
  // The agent's own settings, for this PC: the fleet it sends to, what it shares, and the
  // game's telemetry switch. Saved by the agent (not this browser), applied at once.
  import { onMount } from "svelte";
  import { appWindow } from "../lib/appwin.svelte";
  import type { UplinkStatus } from "../lib/types";

  let { uplink = null }: { uplink?: UplinkStatus | null } = $props();

  interface Share {
    id: string;
    label: string;
    help: string;
    on: boolean;
  }
  interface Install {
    channel: string;
    path: string;
    telemetry: boolean;
    current: boolean;
  }
  interface State {
    agent_version: string;
    linked: boolean;
    hub: string | null;
    org: string | null;
    member: string | null;
    sending: boolean;
    joining: string | null;
    suggested_name: string | null;
    share: Share[];
    installs: Install[];
    restart_note: string;
  }

  let info = $state<State | null>(null);
  let error = $state("");
  let busy = $state<string | null>(null);
  let target = $state("");
  let name = $state("");
  let restartFor = $state<string | null>(null);

  async function call(path: string, body?: unknown): Promise<void> {
    error = "";
    const r = await fetch(`/api/agent/${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error ?? `The agent said ${r.status}.`);
    info = data as State;
  }
  async function act(what: string, path: string, body: unknown) {
    busy = what;
    try {
      await call(path, body);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = null;
    }
  }

  onMount(async () => {
    try {
      await call("settings");
      name = info?.suggested_name ?? "";
    } catch (e) {
      error = (e as Error).message;
    }
  });

  const isInvite = $derived(/\/join\/[^/\s]+\s*$/.test(target));
  async function joinFleet(e: SubmitEvent) {
    e.preventDefault();
    await act("join", "join", { target, name });
    if (info?.linked) target = "";
  }
  async function leave() {
    if (!confirm(`Leave ${info?.org ?? "the fleet"}? This PC stops sending, and the hub forgets it. You can join again with an invite link.`))
      return;
    await act("leave", "leave", {});
  }
  async function share(s: Share, on: boolean) {
    await act(`share-${s.id}`, "share", { share: { [s.id]: on } });
  }
  async function telemetry(i: Install, on: boolean) {
    await act(`tel-${i.channel}`, "telemetry", { channel: i.channel, on });
    if (on) restartFor = i.channel;
  }

  const live = $derived(
    !uplink || uplink.state === "unlinked"
      ? null
      : uplink.state === "connected"
        ? "Connected"
        : uplink.state === "rejected"
          ? (uplink.message ?? "Refused by the hub")
          : (uplink.message ?? "Connecting…"),
  );
</script>

{#if error}<p class="error" role="alert">{error}</p>{/if}

{#if !info}
  <p class="hint">Loading…</p>
{:else}
  <section>
    <h3>Fleet</h3>
    {#if info.linked}
      <div class="fleet">
        <span class="dot" class:ok={uplink?.state === "connected"}></span>
        <div>
          <b>{info.org ?? "Your fleet"}</b>
          <small>as {info.member ?? "you"} · {info.hub}</small>
          {#if live}<small class="live" class:ok={uplink?.state === "connected"}>{live}</small>{/if}
          {#if !info.sending}<small>Not sending (replay without --uplink, or --no-uplink).</small>{/if}
        </div>
      </div>
      <button class="btn danger" disabled={busy === "leave"} onclick={leave}>{busy === "leave" ? "Leaving…" : "Leave the fleet"}</button>
    {:else}
      <p class="hint">Paste the invite link from your org's admin. Already a member, on another PC? Paste the hub's address instead: its page opens to confirm.</p>
      <form onsubmit={joinFleet}>
        <input type="url" placeholder="https://fleet.example.org/join/…" bind:value={target} required />
        {#if isInvite}
          <label class="field"
            ><span>Your name in the fleet</span>
            <input type="text" bind:value={name} maxlength="32" placeholder="Your in-game handle" required /></label
          >
        {/if}
        <button class="btn primary" type="submit" disabled={busy === "join" || !target.trim()}>
          {busy === "join" ? (info.joining ? "Confirm in your browser…" : "Joining…") : isInvite ? "Join the fleet" : "Link this PC"}
        </button>
      </form>
    {/if}
  </section>

  <section>
    <h3>What you share</h3>
    <p class="hint">{info.linked ? "With your fleet" : "Once you join a fleet"}. Anything off never leaves this PC.</p>
    <ul class="share">
      {#each info.share as s (s.id)}
        <li>
          <label class="toggle">
            <input type="checkbox" checked={s.on} disabled={busy === `share-${s.id}`} onchange={(e) => share(s, e.currentTarget.checked)} />
            <span><b>{s.label}</b><small>{s.help}</small></span>
          </label>
        </li>
      {/each}
    </ul>
  </section>

  <section>
    <h3>Game telemetry</h3>
    {#if !info.installs.length}
      <p class="hint">No Star Citizen install found.</p>
    {:else}
      <p class="hint">The game's own setting (in its user.cfg) that lets the agent read it. Switching it off puts the file back as it was.</p>
      <ul class="installs">
        {#each info.installs as i (i.channel)}
          <li>
            <span class="ch"><b>{i.channel}</b>{#if i.current}<em>this one</em>{/if}<small>{i.path}</small></span>
            <span class="tel" class:on={i.telemetry}>{i.telemetry ? "On" : "Off"}</span>
            <button class="btn" disabled={busy === `tel-${i.channel}`} onclick={() => telemetry(i, !i.telemetry)}>
              {i.telemetry ? "Switch off" : "Switch on"}
            </button>
          </li>
          {#if restartFor === i.channel && i.telemetry}<li class="note">{info.restart_note}</li>{/if}
        {/each}
      </ul>
    {/if}
  </section>

  {#if appWindow.inApp && appWindow.state}
    {@const w = appWindow.state}
    <section>
      <h3>Window</h3>
      <ul class="share">
        <li>
          <label class="toggle">
            <input type="checkbox" checked={w.frameless} onchange={(e) => appWindow.setFrameless(e.currentTarget.checked)} />
            <span><b>Hide the title bar</b><small>Drag the window by its top bar; its buttons move there too</small></span>
          </label>
        </li>
        <li>
          <label class="toggle">
            <input type="checkbox" checked={w.on_top} onchange={(e) => appWindow.setOnTop(e.currentTarget.checked)} />
            <span><b>Always on top</b><small>Over the game, for a second screen or a VR overlay app</small></span>
          </label>
        </li>
        <li>
          <label class="toggle">
            <input
              type="checkbox"
              checked={!!w.autostart}
              disabled={w.autostart === null}
              onchange={(e) => appWindow.setAutostart(e.currentTarget.checked)}
            />
            <span
              ><b>Start with Windows</b><small
                >{w.autostart === null ? "Only in the installed starglance.exe" : "In the tray when you sign in, ready before the game"}</small
              ></span
            >
          </label>
        </li>
      </ul>
    </section>
  {/if}

  <p class="hint">Agent {info.agent_version} · settings saved on this PC, for every window.</p>
{/if}

<style>
  section {
    display: grid;
    gap: 8px;
  }
  h3 {
    margin: 0 0 2px;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .hint {
    margin: 0;
    color: var(--text-3);
    font-size: 0.8rem;
  }
  .error {
    margin: 0;
    padding: 8px 10px;
    border: 1px solid var(--bad);
    border-radius: var(--radius-sm);
    color: var(--bad);
    font-size: 0.85rem;
  }
  .fleet {
    display: flex;
    gap: 10px;
    align-items: start;
    padding: 10px 12px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--panel);
  }
  .fleet div {
    display: grid;
    gap: 2px;
    min-width: 0;
  }
  .fleet small {
    color: var(--text-3);
    font-size: 0.75rem;
    overflow-wrap: anywhere;
  }
  .fleet small.live.ok {
    color: var(--good);
  }
  .dot {
    width: 8px;
    height: 8px;
    margin-top: 6px;
    border-radius: 50%;
    background: var(--warn);
    flex: none;
  }
  .dot.ok {
    background: var(--good);
  }
  form {
    display: grid;
    gap: 8px;
  }
  input[type="url"],
  input[type="text"] {
    width: 100%;
    box-sizing: border-box;
    padding: 7px 9px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    color: var(--text);
    font: inherit;
  }
  .field {
    display: grid;
    gap: 4px;
    font-size: 0.78rem;
    color: var(--text-3);
  }
  .btn {
    justify-self: start;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    padding: 6px 12px;
    background: var(--bg-2);
    color: var(--text);
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .btn:disabled {
    opacity: 0.6;
    cursor: default;
  }
  .btn.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
    font-weight: 700;
  }
  .btn.danger {
    color: var(--bad);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 6px;
  }
  .toggle {
    display: flex;
    gap: 10px;
    align-items: start;
    cursor: pointer;
  }
  .toggle input {
    margin-top: 3px;
    accent-color: var(--accent);
  }
  .toggle span {
    display: grid;
  }
  .toggle small {
    color: var(--text-3);
    font-size: 0.75rem;
  }
  .installs li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: 10px;
    align-items: center;
  }
  .ch {
    display: grid;
    min-width: 0;
  }
  .ch em {
    font-style: normal;
    font-size: 0.7rem;
    color: var(--accent);
  }
  .ch small {
    color: var(--text-3);
    font-size: 0.72rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tel {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .tel.on {
    color: var(--good);
  }
  .note {
    display: block !important;
    font-size: 0.78rem;
    color: var(--warn);
  }
</style>
