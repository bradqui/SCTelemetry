<script lang="ts" module>
  export interface Lan {
    enabled: boolean;
    running: boolean;
    error: string | null;
    port: number;
    addresses: string[];
    code: { code: string; expires_in: number; tries: number } | null;
    devices: { id: string; name: string; paired: number; seen: number; online: boolean }[];
  }
</script>

<script lang="ts">
  // Show on other devices (Settings → Agent): the agent's view-only server on your home
  // network. Switch it on, pair a tablet or phone with a code (or its QR), see and remove
  // paired devices. Pairing finishes on the device, so this checks back while a code shows.
  import qrcode from "qrcode-generator";


  let {
    lan,
    busy,
    act,
    refresh,
  }: {
    lan: Lan;
    busy: string | null;
    act: (what: string, path: string, body: unknown) => Promise<void>;
    refresh: () => Promise<void>;
  } = $props();

  // Check back: every 2 s while a code shows (has the device paired?), else every 15 s
  // (who's watching now).
  $effect(() => {
    if (!lan.running) return;
    const t = setInterval(() => void refresh().catch(() => {}), lan.code ? 2000 : 15000);
    return () => clearInterval(t);
  });

  // The code's countdown, between check-backs.
  let now = $state(Date.now());
  let codeAt = $state(Date.now());
  $effect(() => {
    if (lan.code) {
      void lan.code.expires_in; // each check-back restarts the count from the agent's
      codeAt = now = Date.now();
    }
  });
  $effect(() => {
    if (!lan.code) return;
    const t = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(t);
  });
  const left = $derived(lan.code ? Math.max(0, lan.code.expires_in - Math.floor((now - codeAt) / 1000)) : 0);
  const clock = $derived(`${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`);

  const main = $derived(lan.addresses[0] ?? `http://this-pc:${lan.port}`);
  const others = $derived(lan.addresses.slice(1));

  /** The QR: the pairing page with the code filled in. Dark on light, whatever the theme:
   * that's what phone cameras read. */
  const qr = $derived.by(() => {
    if (!lan.code) return null;
    const q = qrcode(0, "M");
    q.addData(`${main}/pair?code=${lan.code.code}`);
    q.make();
    const n = q.getModuleCount();
    let d = "";
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (q.isDark(r, c)) d += `M${c} ${r}h1v1h-1z`;
    return { n, d };
  });

  function ago(ms: number): string {
    const s = Math.max(0, (Date.now() - ms) / 1000);
    if (s < 90) return "just now";
    if (s < 3600) return `${Math.round(s / 60)} min ago`;
    if (s < 86400 * 2) return `${Math.round(s / 3600)} h ago`;
    return `${Math.round(s / 86400)} days ago`;
  }

  const forget = (id: string | null, name: string) => {
    if (!confirm(id ? `Remove ${name}? It stops showing this PC at once.` : "Remove every device? They stop showing this PC at once."))
      return;
    void act(`forget-${id ?? "all"}`, "lan/forget", { id });
  };
</script>

<section>
  <h3>Other devices</h3>
  <ul class="list">
    <li>
      <label class="toggle">
        <input
          type="checkbox"
          checked={lan.enabled}
          disabled={busy === "lan"}
          onchange={(e) => act("lan", "lan", { on: e.currentTarget.checked })}
        />
        <span
          ><b>Show on other devices</b><small
            >A tablet or phone on your home network can watch this cockpit view and the fleet. View only: nothing there can
            change settings or reach the game.</small
          ></span
        >
      </label>
    </li>
  </ul>

  {#if lan.error}<p class="error" role="alert">{lan.error}</p>{/if}

  {#if lan.running}
    <p class="addr">
      On the device, open <b>{main}</b>
      {#if others.length}<small>or {others.join(" · ")}</small>{/if}
    </p>

    {#if lan.code}
      <div class="pair">
        {#if qr}
          <svg class="qr" viewBox="-2 -2 {qr.n + 4} {qr.n + 4}" shape-rendering="crispEdges" role="img" aria-label="QR code for pairing">
            <rect x="-2" y="-2" width={qr.n + 4} height={qr.n + 4} />
            <path d={qr.d} />
          </svg>
        {/if}
        <div class="codebox">
          <span class="label">Pairing code</span>
          <b class="display code">{lan.code.code.slice(0, 3)} {lan.code.code.slice(3)}</b>
          <small>Scan it, or enter the code on the device. {clock} left.</small>
          <button class="btn" onclick={() => act("code", "lan/code", { cancel: true })}>Cancel</button>
        </div>
      </div>
    {:else}
      <button class="btn primary" disabled={busy === "code"} onclick={() => act("code", "lan/code", {})}>Pair a device</button>
    {/if}

    {#if lan.devices.length}
      <ul class="devices">
        {#each lan.devices as d (d.id)}
          <li>
            <span class="dot" class:ok={d.online}></span>
            <span class="who"
              ><b>{d.name}</b><small>{d.online ? "Watching now" : `Last seen ${ago(d.seen)}`} · paired {ago(d.paired)}</small></span
            >
            <button class="btn danger" disabled={busy === `forget-${d.id}`} onclick={() => forget(d.id, d.name)}>Remove</button>
          </li>
        {/each}
      </ul>
      {#if lan.devices.length > 1}
        <button class="btn danger" disabled={busy === "forget-all"} onclick={() => forget(null, "")}>Remove all</button>
      {/if}
    {/if}

    <p class="hint">
      Windows may ask whether Starglance can use your network: allow it on private networks. It's plain HTTP, so use it at home,
      not on public Wi-Fi.
    </p>
  {/if}
</section>

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
  .toggle span,
  .who,
  .addr {
    display: grid;
  }
  small {
    color: var(--text-3);
    font-size: 0.75rem;
    overflow-wrap: anywhere;
  }
  .addr {
    margin: 0;
    font-size: 0.85rem;
    overflow-wrap: anywhere;
  }
  .addr b {
    color: var(--accent);
    user-select: all;
  }
  .pair {
    display: flex;
    gap: 14px;
    align-items: center;
    padding: 10px 12px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--panel);
  }
  .qr {
    width: 132px;
    height: 132px;
    flex: none;
  }
  /* Dark modules on light, in every theme: what cameras read. */
  .qr rect {
    fill: white;
  }
  .qr path {
    fill: black;
  }
  .codebox {
    display: grid;
    gap: 4px;
    justify-items: start;
  }
  .code {
    font-size: 1.9rem;
    letter-spacing: 0.12em;
    font-variant-numeric: tabular-nums;
  }
  .devices li {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 10px;
    align-items: center;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-3);
  }
  .dot.ok {
    background: var(--good);
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
</style>
