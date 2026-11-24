<script lang="ts">
  import type { PanelCtx } from "../../lib/context";

  // Current contract (from Game.log), its objective, and how the session's going.
  let { ctx }: { ctx: PanelCtx } = $props();

  const missions = $derived(ctx.snap.missions ?? null);
  const main = $derived(missions?.[0] ?? null);
  const others = $derived(missions?.slice(1) ?? []);
  const session = $derived(ctx.snap.session ?? null);
  const STATE: Record<string, string> = {
    active: "Active",
    complete: "Complete",
    failed: "Failed",
    abandoned: "Abandoned",
  };
</script>

{#if missions === null}
  <p class="muted">Contracts come from the game's log, which the agent can't read here.</p>
{:else if !main}
  <div class="none">
    <span class="title">No active contract</span>
    <span class="muted">Accept one from your mobiGlas and it shows up here.</span>
  </div>
{:else}
  <div class="main {main.state}">
    <div class="head">
      <span class="badge">{STATE[main.state]}</span>
      {#if main.shared}<span class="badge shared">Shared</span>{/if}
      {#each main.tags as tag (tag)}<span class="tag">{tag}</span>{/each}
    </div>
    <span class="title display">{main.title ?? "Objective"}</span>
    {#if main.objective}
      <div class="objective" class:done={main.objective_done}>
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path d="M2.5 2.5h11v11h-11z" />
          {#if main.objective_done}<path d="M5 8l2 2 4-4" />{/if}
        </svg>
        <span>{main.objective}</span>
      </div>
    {/if}
  </div>
  {#if others.length}
    <ul class="others">
      {#each others as m, i (i)}
        <li class={m.state}><span class="dot"></span>{m.title ?? m.objective}<em>{STATE[m.state]}</em></li>
      {/each}
    </ul>
  {/if}
{/if}

{#if session && (session.contracts || session.failed || session.earned)}
  <div class="tally">
    <span><b class="num">{session.contracts}</b> done</span>
    {#if session.failed}<span class="bad"><b class="num">{session.failed}</b> failed</span>{/if}
    <span class="earned"><b class="num">{session.earned.toLocaleString()}</b> aUEC</span>
  </div>
{/if}

<style>
  .main {
    display: grid;
    gap: 5px;
    padding: 8px 10px;
    border: 1px solid var(--line);
    border-left: 3px solid var(--c);
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--c) 7%, var(--bg-2));
    --c: var(--warn);
  }
  .main.complete {
    --c: var(--good);
  }
  .main.failed {
    --c: var(--bad);
  }
  .main.abandoned {
    --c: var(--text-3);
  }
  .head {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
  }
  .badge,
  .tag {
    font-size: 0.6rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 1px 6px;
    border-radius: var(--radius-sm);
  }
  .badge {
    color: var(--bg);
    background: var(--c);
  }
  .badge.shared {
    background: var(--nav);
  }
  .tag {
    color: var(--text-2);
    border: 1px solid var(--line-2);
  }
  .title {
    font-size: 0.98rem;
    font-weight: 700;
    line-height: 1.25;
  }
  .objective {
    display: flex;
    align-items: flex-start;
    gap: 7px;
    font-size: 0.82rem;
    color: var(--text-2);
  }
  .objective svg {
    width: 14px;
    height: 14px;
    flex: none;
    margin-top: 1px;
  }
  .objective path {
    fill: none;
    stroke: var(--c);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .objective.done span {
    color: var(--text-3);
    text-decoration: line-through;
  }
  .others {
    list-style: none;
    padding: 0;
    margin: 5px 0 0;
    display: grid;
    gap: 2px;
  }
  .others li {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.74rem;
    color: var(--text-2);
    white-space: nowrap;
    overflow: hidden;
  }
  .others em {
    margin-left: auto;
    font-style: normal;
    font-size: 0.6rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .others .dot {
    color: var(--warn);
  }
  .others .complete .dot {
    color: var(--good);
  }
  .others .failed .dot {
    color: var(--bad);
  }
  .none {
    display: grid;
    gap: 3px;
    padding: 8px 10px;
    border: 1px dashed var(--line-2);
    border-radius: var(--radius-sm);
  }
  .none .title {
    color: var(--text-2);
    font-size: 0.9rem;
  }
  .tally {
    display: flex;
    gap: 10px;
    margin-top: 6px;
    font-size: 0.74rem;
    color: var(--text-3);
  }
  .tally b {
    color: var(--text);
    font-size: 0.9rem;
  }
  .tally .earned {
    margin-left: auto;
  }
  .tally .earned b {
    color: var(--good);
  }
  .tally .bad b {
    color: var(--bad);
  }
  .muted {
    color: var(--text-3);
    margin: 0;
    font-size: 0.78rem;
  }
</style>
