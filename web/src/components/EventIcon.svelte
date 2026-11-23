<script lang="ts">
  // A small stroke icon per event kind.
  let { kind, size = 14 }: { kind: string; size?: number } = $props();

  const PATHS: Record<string, string> = {
    warning: "M8 2.5 14.5 13.5h-13z M8 6.5v3.2 M8 11.6v.1",
    clear: "M3 8.5l3 3 7-7",
    takeoff: "M8 13V3 M4 7l4-4 4 4",
    landed: "M8 3v10 M4 9l4 4 4-4 M2.5 14.5h11",
    seat: "M5 2.5v7h6 M5 9.5v4 M11 9.5v4 M11 9.5l1-4",
    leave: "M10 3h3v10h-3 M7 5 4 8l3 3 M4 8h7",
    ship: "M8 1.5l2 5 4.5 3-4.5 1L8 14.5 6 10.5l-4.5-1 4.5-3z",
    mode: "M2 5h9 M8 2l3 3-3 3 M14 11H5 M8 8l-3 3 3 3",
    hull: "M8 1.5 13.5 4v4c0 3.5-2.5 5.5-5.5 6.5C5 13.5 2.5 11.5 2.5 8V4z",
    fuel: "M8 2s4.5 5 4.5 8a4.5 4.5 0 0 1-9 0c0-3 4.5-8 4.5-8z",
    life: "M2 8h3l1.5-3 3 6L11 8h3",
    power: "M8 1.5v6 M4.5 4a5 5 0 1 0 7 0",
    dot: "M8 6a2 2 0 1 1 0 4a2 2 0 1 1 0-4z",
    quantum: "M1.5 8h4 M4 5.5 6.5 8 4 10.5 M8 8h6.5 M11.5 5l3 3-3 3",
  };

  function iconFor(k: string): string {
    if (k === "warning_on" || k === "hull_threshold" || k === "fuel_threshold") return k === "warning_on" ? "warning" : k === "hull_threshold" ? "hull" : "fuel";
    if (k === "warning_off") return "clear";
    if (k === "takeoff" || k === "landed") return k;
    if (k === "seat_enter") return "seat";
    if (k === "seat_leave") return "leave";
    if (k === "ship_change") return "ship";
    if (k === "mode_change") return "mode";
    if (k.startsWith("quantum")) return "quantum";
    if (["spawn", "downed", "dead", "respawn"].includes(k)) return "life";
    if (k === "game_start" || k === "game_exit") return "power";
    return "dot";
  }
</script>

<svg viewBox="0 0 16 16" width={size} height={size} aria-hidden="true">
  <path d={PATHS[iconFor(kind)]} />
</svg>

<style>
  svg {
    display: block;
  }
  path {
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
</style>
