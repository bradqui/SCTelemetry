<script lang="ts">
  // The fleet view in the cockpit page. In several fleets (one per org's hub), the one you
  // picked: switching makes a new view, with its own connection.
  import { fleetPick } from "../lib/fleetpick.svelte";
  import type { PrefsStore } from "../lib/prefs.svelte";
  import LocalFleetView from "./LocalFleetView.svelte";

  let { store, onBack }: { store: PrefsStore; onBack: () => void } = $props();
</script>

{#key fleetPick.hub}
  <LocalFleetView {store} {onBack} hub={fleetPick.hub} />
{/key}
