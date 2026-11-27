<script lang="ts">
  // Getting Starglance onto the PC you play on, from the hub's page: download it, open it,
  // then "Link this PC" hands the app a one-time starglance:// link (the app registers the
  // scheme when it starts, and asks before linking). Nothing to type or paste. The page
  // watches the account's PCs to say when it worked.
  import { onDestroy } from "svelte";
  import { api } from "../../lib/api";
  import type { HubMode } from "../../lib/types";

  let { mode, onLinked }: { mode: HubMode; onLinked?: (machine: string) => void } = $props();

  interface Pc {
    id: number;
    machine: string;
  }
  const windows = /Windows/i.test(navigator.userAgent);
  const download = $derived(mode.download_url ?? "https://github.com/bradqui/starglance/releases/latest");
  const setupUrl = location.origin + "/setup";

  let phase = $state<"idle" | "opening" | "waiting" | "linked">("idle");
  let linked = $state("");
  let error = $state("");
  let copied = $state(false);
  let timer: ReturnType<typeof setInterval> | undefined;
  let hint: ReturnType<typeof setTimeout> | undefined;
  onDestroy(() => {
    clearInterval(timer);
    clearTimeout(hint);
  });

  async function linkPC() {
    error = "";
    phase = "opening";
    try {
      const before = new Set((await api<Pc[]>("GET", "/api/me/agents")).map((p) => p.id));
      const { url, expires_in } = await api<{ url: string; expires_in: number }>("POST", "/api/me/pc-link");
      location.assign(url); // the browser asks to open Starglance
      clearTimeout(hint);
      hint = setTimeout(() => {
        if (phase === "opening") phase = "waiting";
      }, 4000);
      clearInterval(timer);
      const until = Date.now() + expires_in * 1000;
      timer = setInterval(async () => {
        if (Date.now() > until) {
          clearInterval(timer);
          if (phase !== "linked") phase = "idle";
          return;
        }
        try {
          const pc = (await api<Pc[]>("GET", "/api/me/agents")).find((p) => !before.has(p.id));
          if (pc) {
            clearInterval(timer);
            linked = pc.machine;
            phase = "linked";
            onLinked?.(pc.machine);
          }
        } catch {
          /* a blip: try again */
        }
      }, 2000);
    } catch (e) {
      error = (e as Error).message;
      phase = "idle";
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(setupUrl);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch {
      /* the address is on screen anyway */
    }
  }
</script>

{#if phase === "linked"}
  <p class="done">✓ <b>{linked}</b> is linked. Starglance sends to the fleet whenever it's running.</p>
{:else if !windows}
  <p>
    Starglance runs on the Windows PC you play Star Citizen on. On that PC, open this page and sign in, then follow the
    steps:
  </p>
  <div class="row">
    <code class="grow">{setupUrl}</code>
    <button class="btn" onclick={copy}>{copied ? "Copied" : "Copy"}</button>
  </div>
{:else}
  <ol class="steps">
    <li>
      <div>
        <b>Download Starglance</b>
        <small>One file, <code>starglance.exe</code>, nothing to install. Put it anywhere, say a Starglance folder in Documents.</small>
      </div>
      <a class="btn primary" href={download}>Download</a>
    </li>
    <li>
      <div>
        <b>Open it</b>
        <small
          >If Windows says it protected your PC, choose <b>More info → Run anyway</b> (Starglance isn't code-signed yet). It opens
          in its own window.</small
        >
      </div>
    </li>
    <li>
      <div>
        <b>Link this PC</b>
        <small>Your browser asks to open Starglance: allow it, then choose <b>Join</b> in Starglance.</small>
      </div>
      <button class="btn primary" disabled={phase === "opening"} onclick={linkPC}
        >{phase === "idle" ? "Link this PC" : "Try again"}</button
      >
    </li>
  </ol>
  {#if phase === "waiting" || phase === "opening"}
    <p class="wait" aria-live="polite">
      Waiting for Starglance… Nothing happened? Make sure Starglance is open (step 2), then click <b>Try again</b>. Or in
      Starglance, open <b>Settings → Agent</b>, choose <b>Or enter the hub's address</b>, and enter <code>{location.host}</code>.
    </p>
  {/if}
{/if}
{#if error}<p class="error">{error}</p>{/if}

<style>
  .steps {
    list-style: none;
    counter-reset: step;
    margin: 10px 0 0;
    padding: 0;
    display: grid;
    gap: 6px;
  }
  .steps li {
    counter-increment: step;
    display: flex;
    gap: 10px;
    align-items: center;
    padding: 8px 10px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
  }
  .steps li::before {
    content: counter(step);
    flex: none;
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 1px solid var(--accent);
    color: var(--accent);
    font-weight: 800;
    font-size: 0.78rem;
  }
  .steps li > div {
    flex: 1;
    min-width: 0;
    display: grid;
    gap: 2px;
    font-size: 0.88rem;
  }
  .steps small {
    color: var(--text-3);
    font-size: 0.78rem;
  }
  .steps .btn {
    flex: none;
    display: inline-grid;
    place-items: center;
    text-decoration: none;
  }
  .wait {
    margin-top: 8px;
    font-size: 0.8rem;
  }
  .done {
    padding: 8px 10px;
    border: 1px solid var(--good);
    border-radius: var(--radius-sm);
    color: var(--text);
  }
  .grow {
    flex: 1;
    min-width: 0;
    align-self: center;
  }
</style>
