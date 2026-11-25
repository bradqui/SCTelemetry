<script lang="ts">
  // Report a problem (docs/REPORTS.md): pick the moment (a mark, an event, or now), say
  // what happened, read the report as it will be sent, save it to Downloads and open a
  // pre-filled GitHub issue to drop it into. The agent builds and cleans it; nothing is
  // uploaded by Starglance.
  import { onMount } from "svelte";
  import { fly } from "svelte/transition";
  import { clock, eventText, eventTone } from "../lib/format";
  import { openExternal, reportCall } from "../lib/reports";
  import type { ReportsStatus } from "../lib/types";
  import EventIcon from "./EventIcon.svelte";

  let { reports = null, onClose }: { reports?: ReportsStatus | null; onClose: () => void } = $props();

  interface Item {
    t: number;
    kind: string;
    data: Record<string, unknown>;
  }
  interface Timeline extends ReportsStatus {
    now: number;
    oldest: number | null;
    events: Item[];
    before: number[];
    after: number[];
    parts: string[];
  }
  interface Preview {
    id: string;
    name: string;
    size: number;
    files: { name: string; size: number }[];
    texts: Record<string, string>;
    counts: Record<string, number>;
  }
  interface Saved {
    path: string;
    folder: string;
    issue_url: string;
  }
  type Pick = { kind: "mark"; id: string; t: number } | { kind: "event"; t: number; item: Item } | { kind: "now"; t: number };

  let tl = $state<Timeline | null>(null);
  let error = $state("");
  let busy = $state<string | null>(null);
  let pick = $state<Pick | null>(null);
  let before = $state(3);
  let after = $state(1);
  let what = $state("");
  let expected = $state("");
  let part = $state("");
  let preview = $state<Preview | null>(null);
  let shown = $state("gamelog.txt");
  let saved = $state<Saved | null>(null);

  const status = $derived(reports ?? tl);
  const marks = $derived([...(status?.marks ?? [])].sort((a, b) => b.t - a.t));

  async function load() {
    error = "";
    try {
      tl = await reportCall<Timeline>("timeline");
      part ||= tl.parts[0] ?? "";
      if (!pick) {
        const m = [...tl.marks].sort((a, b) => b.t - a.t)[0];
        pick = m ? { kind: "mark", id: m.id, t: m.t } : { kind: "now", t: tl.now };
      }
    } catch (e) {
      error = (e as Error).message;
    }
  }
  onMount(load);

  async function run(what_: string, fn: () => Promise<void>) {
    busy = what_;
    error = "";
    try {
      await fn();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = null;
    }
  }

  const windowText = $derived(
    pick ? `${clock(pick.t - before * 60_000)} to ${clock(pick.t + after * 60_000)}` : "",
  );

  function makePreview(e: SubmitEvent) {
    e.preventDefault();
    if (!pick) return;
    const p = pick;
    void run("preview", async () => {
      preview = await reportCall<Preview>("preview", {
        t: p.t,
        before,
        after,
        mark: p.kind === "mark" ? p.id : null,
        focus: p.kind === "event" ? { kind: p.item.kind, data: p.item.data, t: p.t } : { kind: p.kind, t: p.t },
        what,
        expected,
        part,
      });
      shown = preview.texts["gamelog.txt"] ? "gamelog.txt" : "report.json";
    });
  }
  function back() {
    void reportCall("discard").catch(() => {});
    preview = null;
  }
  function save() {
    if (!preview) return;
    const id = preview.id;
    void run("save", async () => {
      saved = await reportCall<Saved>("save", { id });
    });
  }
  function forget(id: string) {
    void run(`forget-${id}`, async () => {
      await reportCall("forget", { id });
      if (pick?.kind === "mark" && pick.id === id) pick = null;
      await load();
    });
  }
  function keepOn() {
    void run("keep", async () => {
      await reportCall("keep", { on: true });
      await load();
    });
  }
  function close() {
    if (preview && !saved) void reportCall("discard").catch(() => {});
    onClose();
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape") close();
  }
  const n = (count: number, what: string) => `${count} ${what}${count === 1 ? "" : "s"}`;
  const kb = (n: number) => (n < 1024 ? `${n} B` : `${Math.round(n / 1024)} KB`);
  const isPick = (p: Pick | null, kind: string, t: number) => p?.kind === kind && p.t === t;
</script>

<svelte:window onkeydown={onKey} />

<div class="scrim" role="presentation" onclick={close}></div>
<div class="dialog" role="dialog" aria-modal="true" aria-label="Report a problem" transition:fly={{ y: 12, duration: 180 }}>
  <header>
    <div>
      <h2>Report a problem</h2>
      <p>Makes one file to attach to a GitHub issue. Nothing is sent by Starglance.</p>
    </div>
    <button class="btn" onclick={close}>Close</button>
  </header>

  {#if error}<p class="error" role="alert">{error}</p>{/if}

  {#if !tl}
    <p class="hint">Loading…</p>
  {:else if !tl.available}
    <p class="hint">Reports are made from live play, not a replay.</p>
  {:else if !tl.keep}
    <p class="hint">
      Keeping the last {tl.keep_minutes} minutes is off, so there's nothing to report from. Switch it on, then report the next time
      something goes wrong.
    </p>
    <button class="btn primary" disabled={busy === "keep"} onclick={keepOn}>Keep the last {tl.keep_minutes} minutes</button>
  {:else if saved}
    <section class="done">
      <p><b>Saved</b> to <code>{saved.path}</code> (Explorer shows it).</p>
      <ol>
        <li>Open the issue: it's filled in with what you wrote.</li>
        <li>Drag the file into the <b>Log or recording</b> box, then submit.</li>
      </ol>
      <p class="warn">GitHub issues are public: anyone can read the issue and download the file.</p>
      <div class="row">
        <button class="btn primary" onclick={() => openExternal(saved!.issue_url)}>Open a GitHub issue</button>
        <button class="btn" onclick={onClose}>Done</button>
      </div>
    </section>
  {:else if preview}
    <section class="preview">
      <p class="hint">
        <b>{preview.name}</b> · {kb(preview.size)} · {n(preview.counts.frames, "telemetry frame")}, {n(preview.counts.events, "event")},
        {n(preview.counts.gamelog_lines, "Game.log line")}{preview.counts.players_renamed
          ? `, ${preview.counts.players_renamed} other player${preview.counts.players_renamed > 1 ? "s" : ""} renamed`
          : ""}.
      </p>
      <div class="tabs" role="tablist">
        {#each Object.keys(preview.texts) as name (name)}
          <button role="tab" class:on={shown === name} aria-selected={shown === name} onclick={() => (shown = name)}
            >{name}<small>{kb(preview.files.find((f) => f.name === name)?.size ?? 0)}</small></button
          >
        {/each}
      </div>
      <pre>{preview.texts[shown] || "(empty)"}</pre>
      <p class="hint">
        Also: <code>capture.jsonl.gz</code> (the telemetry, aUEC removed){#if preview.files.some((f) => f.name === "telemetry.protoset")},
          <code>telemetry.protoset</code> (the game's message definitions){/if}.
      </p>
      <p class="warn">
        This goes on a public GitHub issue. Your handle, other players' names, account and session IDs, addresses and fleet names are
        replaced; your ship, location, server and what happened stay. Read it through: a name in a line Starglance doesn't know can
        slip past.
      </p>
      <div class="row">
        <button class="btn primary" disabled={busy === "save"} onclick={save}>{busy === "save" ? "Saving…" : "Save to Downloads"}</button>
        <button class="btn" onclick={back}>Back</button>
      </div>
    </section>
  {:else}
    <form class="grid" onsubmit={makePreview}>
      <section class="when">
        <h3>1 · When</h3>
        <ul class="pick">
          {#each marks as m (m.id)}
            <li class:on={isPick(pick, "mark", m.t)}>
              <button type="button" onclick={() => (pick = { kind: "mark", id: m.id, t: m.t })}>
                <span class="icon"><EventIcon kind="mark" size={12} /></span>
                <span class="text">Marked{m.source === "hotkey" ? " (hotkey)" : ""}</span>
                <time class="num">{clock(m.t)}</time>
              </button>
              <button type="button" class="x" title="Forget this mark" aria-label="Forget this mark" disabled={busy === `forget-${m.id}`} onclick={() => forget(m.id)}>×</button>
            </li>
          {/each}
          <li class:on={pick?.kind === "now"}>
            <button type="button" onclick={() => (pick = { kind: "now", t: Date.now() })}>
              <span class="icon"><EventIcon kind="dot" size={12} /></span>
              <span class="text">Just now</span>
            </button>
          </li>
        </ul>
        <p class="hint">Or the thing that went wrong, from the last {tl.keep_minutes} minutes:</p>
        <ul class="pick events">
          {#each tl.events as e (`${e.t}-${e.kind}-${JSON.stringify(e.data)}`)}
            <li class="{eventTone(e.kind, e.data)}" class:on={pick?.kind === "event" && pick.t === e.t && pick.item.kind === e.kind}>
              <button type="button" onclick={() => (pick = { kind: "event", t: e.t, item: e })}>
                <span class="icon"><EventIcon kind={e.kind} size={12} /></span>
                <span class="text">{eventText(e.kind, e.data)}</span>
                <time class="num">{clock(e.t)}</time>
              </button>
            </li>
          {:else}
            <li class="none">Nothing recorded yet. It starts when the game sends telemetry.</li>
          {/each}
        </ul>
      </section>

      <section class="what">
        <h3>2 · How much</h3>
        <div class="row">
          <label
            >Before <select bind:value={before}>{#each tl.before as n (n)}<option value={n}>{n} min</option>{/each}</select></label
          >
          <label>After <select bind:value={after}>{#each tl.after as n (n)}<option value={n}>{n} min</option>{/each}</select></label>
        </div>
        {#if windowText}<p class="hint">{windowText}</p>{/if}

        <h3>3 · What happened</h3>
        <textarea bind:value={what} rows="3" required maxlength="4000" placeholder="What you saw. E.g. it said I left quantum twice during one jump."
        ></textarea>
        <textarea bind:value={expected} rows="2" maxlength="4000" placeholder="What you expected (optional)"></textarea>
        <label class="field"
          >Where <select bind:value={part}>{#each tl.parts as p (p)}<option value={p}>{p}</option>{/each}</select></label
        >
        <button class="btn primary" type="submit" disabled={!pick || !what.trim() || busy === "preview"}
          >{busy === "preview" ? "Making it…" : "Preview the report"}</button
        >
        <p class="hint">Nothing leaves this PC: you'll see everything in it before it's saved.</p>
      </section>
    </form>
  {/if}
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 40;
    background: #0008;
  }
  .dialog {
    position: fixed;
    z-index: 41;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    width: min(860px, calc(100vw - 24px));
    max-height: calc(100vh - 24px);
    overflow-y: auto;
    box-sizing: border-box;
    padding: 14px 16px 16px;
    display: grid;
    gap: 12px;
    align-content: start;
    background: var(--bg);
    border: 1px solid var(--line-2);
    border-radius: var(--radius);
    box-shadow: 0 20px 60px #000a;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: start;
    gap: 12px;
  }
  h2 {
    margin: 0;
    font-size: 1.15rem;
  }
  header p,
  .hint {
    margin: 0;
    color: var(--text-3);
    font-size: 0.8rem;
  }
  h3 {
    margin: 4px 0 0;
    font-size: 0.7rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 16px;
  }
  @media (max-width: 680px) {
    .grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  section {
    display: grid;
    gap: 8px;
    align-content: start;
    min-width: 0;
  }
  .pick {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
  }
  .pick.events {
    max-height: 300px;
    overflow-y: auto;
    scrollbar-width: thin;
  }
  .pick li {
    display: flex;
    align-items: center;
    border: 1px solid transparent;
    border-left: 2px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    --c: var(--text-3);
  }
  .pick li.bad {
    --c: var(--bad);
  }
  .pick li.warn {
    --c: var(--warn);
  }
  .pick li.good {
    --c: var(--good);
  }
  .pick li.on {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 14%, var(--bg-2));
  }
  .pick li > button:first-child {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 3px 7px;
    background: none;
    border: 0;
    color: var(--text);
    font: inherit;
    font-size: 0.8rem;
    text-align: left;
    cursor: pointer;
  }
  .pick .icon {
    color: var(--c);
    display: grid;
  }
  .pick .text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pick time {
    color: var(--text-3);
    font-size: 0.72rem;
  }
  .pick .x {
    border: 0;
    background: none;
    color: var(--text-3);
    cursor: pointer;
    padding: 0 8px;
    font-size: 1rem;
  }
  .pick li.none {
    padding: 6px 8px;
    color: var(--text-3);
    font-size: 0.8rem;
  }
  .row {
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
  }
  label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8rem;
    color: var(--text-2);
  }
  .field {
    display: grid;
    gap: 4px;
  }
  select,
  textarea {
    box-sizing: border-box;
    padding: 5px 8px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    color: var(--text);
    font: inherit;
    font-size: 0.85rem;
  }
  textarea {
    width: 100%;
    resize: vertical;
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
  .tabs {
    display: flex;
    gap: 3px;
    flex-wrap: wrap;
  }
  .tabs button {
    display: inline-flex;
    gap: 6px;
    align-items: baseline;
    padding: 3px 8px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    color: var(--text-2);
    font: inherit;
    font-size: 0.78rem;
    cursor: pointer;
  }
  .tabs button.on {
    color: var(--text);
    border-color: var(--accent);
  }
  .tabs small {
    color: var(--text-3);
    font-size: 0.68rem;
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
    line-height: 1.45;
    white-space: pre;
  }
  code {
    font-family: var(--mono);
    font-size: 0.85em;
    overflow-wrap: anywhere;
  }
  .warn {
    margin: 0;
    padding: 7px 10px;
    border: 1px solid color-mix(in srgb, var(--warn) 60%, transparent);
    border-radius: var(--radius-sm);
    color: var(--text-2);
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
  .done p,
  .done ol {
    margin: 0;
    font-size: 0.85rem;
  }
  .done ol {
    padding-left: 20px;
    display: grid;
    gap: 4px;
  }
</style>
