<script lang="ts">
  // The agent's own settings, for this PC: the fleets it sends to (one per org's hub, as
  // many as you play with), what it shares with each, and the game's telemetry switch.
  // Saved by the agent (not this browser), applied at once.
  import { onMount } from "svelte";
  import { appWindow } from "../lib/appwin.svelte";
  import type { UpdaterStatus, UplinkStatus } from "../lib/types";
  import OtherDevices, { type Lan } from "./OtherDevices.svelte";

  let {
    uplinks = {},
    updater = null,
  }: {
    uplinks?: Record<string, UplinkStatus>;
    /** Live update progress (the agent's feed); the settings call has it too. */
    updater?: UpdaterStatus | null;
  } = $props();

  interface Share {
    id: string;
    label: string;
    help: string;
    on: boolean;
  }
  interface Fleet {
    hub: string;
    org: string | null;
    label: string;
    member: string | null;
    enabled: boolean;
    linked: boolean;
    sending: boolean;
    share: Share[];
  }
  interface Install {
    channel: string;
    path: string;
    telemetry: boolean;
    current: boolean;
  }
  interface State {
    agent_version: string;
    fleets: Fleet[];
    can_send: boolean;
    joining: string | null;
    suggested_name: string | null;
    installs: Install[];
    restart_note: string;
    lan: Lan | null;
    updates: UpdaterStatus | null;
  }

  let info = $state<State | null>(null);
  let error = $state("");
  let busy = $state<string | null>(null);
  let target = $state("");
  let name = $state("");
  let restartFor = $state<string | null>(null);
  let adding = $state(false);
  /** Which fleet's sharing is open (one at a time). */
  let open = $state<string | null>(null);

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
      if (info && info.fleets.length === 1) open = info.fleets[0].hub;
    } catch (e) {
      error = (e as Error).message;
    }
  });

  const isInvite = $derived(/\/join\/[^/\s]+\s*$/.test(target));
  async function joinFleet(e: SubmitEvent) {
    e.preventDefault();
    const before = info?.fleets.length ?? 0;
    await act("join", "join", { target, name });
    if ((info?.fleets.length ?? 0) > before || !error) {
      target = "";
      adding = false;
    }
  }
  async function leave(f: Fleet) {
    if (!confirm(`Leave ${f.label}? This PC stops sending to it, and its hub forgets this PC. You can join again with an invite link.`))
      return;
    await act(`leave-${f.hub}`, "leave", { hub: f.hub });
  }
  async function share(f: Fleet, s: Share, on: boolean) {
    await act(`share-${f.hub}-${s.id}`, "share", { hub: f.hub, share: { [s.id]: on } });
  }
  async function enable(f: Fleet, on: boolean) {
    await act(`fleet-${f.hub}`, "fleet", { hub: f.hub, enabled: on });
  }
  async function telemetry(i: Install, on: boolean) {
    await act(`tel-${i.channel}`, "telemetry", { channel: i.channel, on });
    if (on) restartFor = i.channel;
  }

  function live(f: Fleet): { text: string; ok: boolean } {
    if (!f.enabled) return { text: "Paused: nothing sent", ok: false };
    if (!info?.can_send) return { text: "Not sending (replay, or --no-uplink)", ok: false };
    const u = uplinks[f.hub];
    if (!u || u.state === "unlinked") return { text: f.sending ? "Connecting…" : "Not sending", ok: false };
    if (u.state === "connected") return { text: "Connected", ok: true };
    if (u.state === "rejected") return { text: u.message ?? "Refused by the hub", ok: false };
    return { text: u.message ?? "Connecting…", ok: false };
  }
  const offCount = (f: Fleet) => f.share.filter((s) => !s.on).length;
</script>

{#if error}<p class="error" role="alert">{error}</p>{/if}

{#if !info}
  <p class="hint">Loading…</p>
{:else}
  <section>
    <h3>{info.fleets.length > 1 ? "Fleets" : "Fleet"}</h3>
    {#if info.fleets.length > 1}
      <p class="hint">Each org's hub sees only what you share with it. Switch a fleet off to stop sending to it without leaving.</p>
    {/if}
    {#each info.fleets as f (f.hub)}
      {@const st = live(f)}
      <div class="fleet" class:off={!f.enabled}>
        <div class="head">
          <span class="dot" class:ok={st.ok}></span>
          <div class="who">
            <b>{f.label}</b>
            <small>as {f.member ?? "you"} · {f.hub}</small>
            <small class="live" class:ok={st.ok}>{st.text}</small>
          </div>
          <label class="switch" title={f.enabled ? "Sending to this fleet" : "Paused"}>
            <input
              type="checkbox"
              checked={f.enabled}
              disabled={busy === `fleet-${f.hub}`}
              onchange={(e) => enable(f, e.currentTarget.checked)}
            />
            <span>{f.enabled ? "On" : "Off"}</span>
          </label>
        </div>
        <div class="actions">
          <button class="btn" onclick={() => (open = open === f.hub ? null : f.hub)} aria-expanded={open === f.hub}>
            What you share{offCount(f) ? ` (${offCount(f)} off)` : ""}
          </button>
          <button class="btn danger" disabled={busy === `leave-${f.hub}`} onclick={() => leave(f)}
            >{busy === `leave-${f.hub}` ? "Leaving…" : "Leave"}</button
          >
        </div>
        {#if open === f.hub}
          <p class="hint">With {f.label}. Anything off never leaves this PC for this hub.</p>
          <ul class="share">
            {#each f.share as s (s.id)}
              <li>
                <label class="toggle">
                  <input
                    type="checkbox"
                    checked={s.on}
                    disabled={busy === `share-${f.hub}-${s.id}`}
                    onchange={(e) => share(f, s, e.currentTarget.checked)}
                  />
                  <span><b>{s.label}</b><small>{s.help}</small></span>
                </label>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {/each}

    {#if !info.fleets.length || adding}
      <p class="hint">
        Paste the invite link from {info.fleets.length ? "the other" : "your"} org's admin. Already a member, on another PC? Paste the
        hub's address instead: its page opens to confirm.
      </p>
      <form onsubmit={joinFleet}>
        <input type="url" placeholder="https://fleet.example.org/join/…" bind:value={target} required />
        {#if isInvite}
          <label class="field"
            ><span>Your name in this fleet</span>
            <input type="text" bind:value={name} maxlength="32" placeholder="Your in-game handle" required /></label
          >
        {/if}
        <div class="actions">
          <button class="btn primary" type="submit" disabled={busy === "join" || !target.trim()}>
            {busy === "join" ? (info.joining ? "Confirm in your browser…" : "Joining…") : isInvite ? "Join the fleet" : "Link this PC"}
          </button>
          {#if info.fleets.length}<button class="btn" type="button" onclick={() => (adding = false)}>Cancel</button>{/if}
        </div>
      </form>
    {:else}
      <button class="btn" onclick={() => (adding = true)}>Join another fleet</button>
    {/if}
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

  {#if info.lan}
    <OtherDevices lan={info.lan} {busy} {act} refresh={() => call("settings")} />
  {/if}

  {@const u = updater ?? info.updates}
  {#if u}
    {@const working = ["downloading", "checking", "installing"].includes(u.state)}
    <section>
      <h3>Updates</h3>
      <p class="hint">
        Starglance {u.current}.
        {#if u.available}<b class="new">{u.available} is out.</b>
        {:else if u.check || info.fleets.length}Up to date.
        {:else}With the check off and no fleet, nothing tells it about new versions: look at the
          <a href={u.releases} target="_blank" rel="noopener noreferrer">releases page</a> now and then.{/if}
      </p>
      {#if u.available && u.can}
        <button class="btn primary" disabled={working || busy === "update"} onclick={() => act("update", "update", {})}>
          {u.state === "downloading"
            ? `Downloading… ${Math.round((u.progress ?? 0) * 100)}%`
            : u.state === "checking"
              ? "Checking the download…"
              : u.state === "installing"
                ? "Restarting…"
                : `Update to ${u.available}`}
        </button>
      {:else if u.available}
        <a class="btn" href={u.releases} target="_blank" rel="noopener noreferrer">Download {u.available}</a>
      {/if}
      {#if u.state === "error" && u.error}
        <p class="error" role="alert">
          {u.error} <a href={u.releases} target="_blank" rel="noopener noreferrer">Releases page</a>
        </p>
      {/if}
      <ul class="share">
        <li>
          <label class="toggle">
            <input type="checkbox" checked={u.check !== false} disabled={busy === "check"} onchange={(e) => act("check", "update/check", { on: e.currentTarget.checked })} />
            <span
              ><b>Check for new versions</b><small
                >Asks this project's GitHub page which release is the latest, when Starglance starts and every few hours. Nothing about
                you or your game goes with it.</small
              ></span
            >
          </label>
        </li>
        {#if u.can}
          <li>
            <label class="toggle">
              <input type="checkbox" checked={u.auto} disabled={busy === "auto"} onchange={(e) => act("auto", "update/auto", { on: e.currentTarget.checked })} />
              <span
                ><b>Update automatically</b><small
                  >When a new version is out and Star Citizen isn't running. Starglance restarts by itself, back where it was (open or in
                  the tray).</small
                ></span
              >
            </label>
          </li>
        {/if}
      </ul>
      <p class="hint">
        GitHub or your fleet's hub says when there's a new version; Starglance then downloads it from the project's GitHub releases
        only, and checks it before replacing itself. Your settings stay.
      </p>
    </section>
  {/if}

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
    display: grid;
    gap: 8px;
    padding: 10px 12px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--panel);
  }
  .fleet.off {
    opacity: 0.75;
  }
  .fleet .head {
    display: flex;
    gap: 10px;
    align-items: start;
  }
  .fleet .who {
    display: grid;
    gap: 2px;
    min-width: 0;
    flex: 1;
  }
  .actions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .switch {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text-3);
    cursor: pointer;
  }
  .switch input {
    accent-color: var(--accent);
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
  .new {
    color: var(--accent);
  }
  a.btn {
    text-decoration: none;
  }
  .note {
    display: block !important;
    font-size: 0.78rem;
    color: var(--warn);
  }
</style>
