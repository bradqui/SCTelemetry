<script lang="ts">
  // Customize → Header alerts: which warning lights go in your top bar and in the fleet
  // header, as warnings (major) and as cautions (minor). Saved in this browser.
  import { defaultAlerts, LIGHTS, type AlertPick, type Alerts } from "../lib/alerts";
  import { LIGHT_NAMES } from "../lib/format";

  let {
    alerts,
    self = true,
  }: {
    /** prefs.alerts (changed in place: the preferences save themselves). */
    alerts: Alerts;
    /** Show the top bar's columns (the cockpit view; not the hub's fleet page). */
    self?: boolean;
  } = $props();

  type Col = { pick: AlertPick; level: "warning" | "caution"; label: string };
  const cols = $derived<Col[]>([
    ...(self
      ? [
          { pick: alerts.self, level: "warning", label: "Warn" },
          { pick: alerts.self, level: "caution", label: "Caut" },
        ]
      : []),
    { pick: alerts.fleet, level: "warning", label: "Warn" },
    { pick: alerts.fleet, level: "caution", label: "Caut" },
  ] as Col[]);

  function set(pick: AlertPick, level: "warning" | "caution", light: string, on: boolean) {
    const now = pick[level].filter((l) => l !== light);
    pick[level] = on ? [...now, light] : now;
  }
  /** A column's header: all on, or (when all are on already) all off. */
  function toggleColumn(c: Col) {
    c.pick[c.level] = c.pick[c.level].length === LIGHTS.length ? [] : [...LIGHTS];
  }
  function preset(which: "default" | "all" | "none") {
    const d = defaultAlerts();
    const all = { warning: [...LIGHTS], caution: [...LIGHTS] };
    const none = { warning: [], caution: [] };
    const p = which === "default" ? d : which === "all" ? { self: all, fleet: all } : { self: none, fleet: none };
    alerts.self.warning = [...p.self.warning];
    alerts.self.caution = [...p.self.caution];
    alerts.fleet.warning = [...p.fleet.warning];
    alerts.fleet.caution = [...p.fleet.caution];
  }
</script>

<section>
  <h3>Header alerts</h3>
  <p class="hint">
    Which warning lights {self ? "show in your top bar and the fleet header" : "show in the fleet header"}. A warning is a light
    at major (red), a caution at minor (amber). In the fleet header a light shows once it's been on for a second. Cards and
    dashboards always show every light.
  </p>
  <table>
    <thead>
      <tr>
        <th></th>
        {#if self}<th colspan="2" class="grp">Your top bar</th>{/if}
        <th colspan="2" class="grp">Fleet header</th>
      </tr>
      <tr>
        <th></th>
        {#each cols as c, i (i)}
          <th>
            <button
              class="col {c.level}"
              onclick={() => toggleColumn(c)}
              title={`${c.level === "warning" ? "Warnings" : "Cautions"}: all on or all off`}>{c.label}</button
            >
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each LIGHTS as light (light)}
        <tr>
          <th scope="row">{LIGHT_NAMES[light] ?? light}</th>
          {#each cols as c, i (i)}
            {#if light === "hit" && c.level === "caution"}
              <td class="na" title="Getting hit is always a warning">–</td>
            {:else}
            <td>
              <input
                type="checkbox"
                class={c.level}
                checked={c.pick[c.level].includes(light)}
                onchange={(e) => set(c.pick, c.level, light, e.currentTarget.checked)}
                aria-label={`${LIGHT_NAMES[light] ?? light}: ${c.level} in ${c.pick === alerts.self ? "your top bar" : "the fleet header"}`}
              />
            </td>
            {/if}
          {/each}
        </tr>
      {/each}
      <tr>
        <th scope="row">Badly hurt</th>
        {#if self}<td colspan="2" class="na">–</td>{/if}
        <td>
          <input type="checkbox" class="warning" bind:checked={alerts.fleet.hurt} aria-label="Badly hurt: warning in the fleet header" />
        </td>
        <td class="na">–</td>
      </tr>
    </tbody>
  </table>
  <label class="toggle">
    <input type="checkbox" bind:checked={alerts.fleet.me} />
    <span><b>You in the fleet header too</b><small>Your own lights, as the fleet sees them</small></span>
  </label>
  <div class="presets">
    <button onclick={() => preset("default")} title="Your own: everything. The fleet: getting hit and radar, as warnings."
      >Defaults</button
    >
    <button onclick={() => preset("all")}>Everything</button>
    <button onclick={() => preset("none")}>Nothing</button>
  </div>
</section>

<style>
  section {
    display: grid;
    gap: 8px;
  }
  h3 {
    margin: 0;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .hint {
    margin: 0;
    color: var(--text-3);
    font-size: 0.78rem;
  }
  table {
    border-collapse: collapse;
    font-size: 0.82rem;
    width: 100%;
  }
  th,
  td {
    padding: 2px 4px;
    text-align: center;
  }
  tbody th {
    text-align: left;
    font-weight: 600;
    color: var(--text-2);
  }
  tbody tr:nth-child(odd) {
    background: color-mix(in srgb, var(--text) 4%, transparent);
  }
  .grp {
    font-size: 0.68rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-3);
    border-bottom: 1px solid var(--line-2);
  }
  .col {
    border: 0;
    background: none;
    padding: 1px 2px;
    font: inherit;
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    cursor: pointer;
  }
  .col.warning {
    color: var(--bad);
  }
  .col.caution {
    color: var(--warn);
  }
  input.warning {
    accent-color: var(--bad);
  }
  input.caution {
    accent-color: var(--warn);
  }
  .na {
    color: var(--text-3);
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
  .presets {
    display: flex;
    gap: 6px;
  }
  .presets button {
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    padding: 4px 10px;
    background: var(--bg-2);
    color: var(--text-2);
    font: inherit;
    font-size: 0.78rem;
    cursor: pointer;
  }
</style>
