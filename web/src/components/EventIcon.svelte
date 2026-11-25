<script lang="ts">
  // A small stroke icon per event kind (16×16 grid).
  let { kind, size = 14 }: { kind: string; size?: number } = $props();

  const PATHS: Record<string, string> = {
    warning: "M8 2.5 14.5 13.5h-13z M8 6.5v3.2 M8 11.6v.1",
    clear: "M3 8.5l3 3 7-7",
    takeoff: "M8 13V3 M4 7l4-4 4 4",
    landed: "M8 3v10 M4 9l4 4 4-4 M2.5 14.5h11",
    seat: "M7 1.5a1.6 1.6 0 1 0 0 3.2a1.6 1.6 0 1 0 0-3.2z M7 6v4.5h4v4 M4 4.5v7.5h4.5",
    leave: "M10 3h3v10h-3 M7 5 4 8l3 3 M4 8h7",
    ship: "M8 1.5l2 5 4.5 3-4.5 1L8 14.5 6 10.5l-4.5-1 4.5-3z",
    mode: "M2 5h9 M8 2l3 3-3 3 M14 11H5 M8 8l-3 3 3 3",
    hull: "M8 1.5 13.5 4v4c0 3.5-2.5 5.5-5.5 6.5C5 13.5 2.5 11.5 2.5 8V4z",
    fuel: "M8 2s4.5 5 4.5 8a4.5 4.5 0 0 1-9 0c0-3 4.5-8 4.5-8z",
    life: "M2 8h3l1.5-3 3 6L11 8h3",
    power: "M8 1.5v6 M4.5 4a5 5 0 1 0 7 0",
    dot: "M8 6a2 2 0 1 1 0 4a2 2 0 1 1 0-4z",
    quantum: "M1.5 8h4 M4 5.5 6.5 8 4 10.5 M8 8h6.5 M11.5 5l3 3-3 3",
    jump: "M8 2a6 6 0 1 0 0 12A6 6 0 1 0 8 2z M8 5a3 3 0 1 0 0 6A3 3 0 1 0 8 5z",
    kill: "M8 1.5v4 M8 10.5v4 M1.5 8h4 M10.5 8h4 M8 5a3 3 0 1 0 0 6A3 3 0 1 0 8 5z",
    lost: "M8 1.5l2 5 4.5 3-4.5 1L8 14.5 6 10.5l-4.5-1 4.5-3z M3 3l10 10",
    contract: "M4 1.5h6l2.5 2.5v10.5h-8.5z M6 7h4 M6 10h4",
    objective: "M2.5 2.5h11v11h-11z M5 8l2 2 4-4",
    reward: "M8 2a6 6 0 1 0 0 12A6 6 0 1 0 8 2z M8 4.5v7 M10 6H7a1 1 0 0 0 0 2h2a1 1 0 0 1 0 2H6",
    armistice: "M8 1.5 13.5 4v4c0 3.5-2.5 5.5-5.5 6.5C5 13.5 2.5 11.5 2.5 8V4z M5.5 8l2 2 3-3.5",
    flag: "M3.5 14.5V2 M3.5 2.5h9l-2 3 2 3h-9",
    eye: "M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z M8 6.5a1.5 1.5 0 1 0 0 3a1.5 1.5 0 1 0 0-3z",
    comms: "M8 14.5V7 M5 4.5a4 4 0 0 1 6 0 M3 2.5a7 7 0 0 1 10 0 M6 14.5h4",
    restricted: "M8 1.5a6.5 6.5 0 1 0 0 13A6.5 6.5 0 1 0 8 1.5z M3.5 3.5l9 9",
    private: "M2 7.5 8 2.5l6 5 M3.5 6.5v7.5h9V6.5 M6.5 14v-4h3v4",
    server: "M2.5 2.5h11v4h-11z M2.5 9.5h11v4h-11z M5 4.5h.1 M5 11.5h.1",
    hangar: "M1.5 14.5V7L8 2.5 14.5 7v7.5 M4.5 14.5v-5h7v5",
    injury: "M6 1.5h4v4.5h4.5v4H10v4.5H6V10H1.5V6H6z",
    heal: "M8 13.5S2 10 2 5.8A3 3 0 0 1 8 4.5a3 3 0 0 1 6 1.3C14 10 8 13.5 8 13.5z M8 6.5v4 M6 8.5h4",
    blueprint: "M2.5 2.5h11v11h-11z M2.5 6h11 M6 6v7.5",
    sync: "M13 6A5.5 5.5 0 0 0 3 5 M3 10a5.5 5.5 0 0 0 10 1 M13 2.5V6H9.5 M3 13.5V10h3.5",
  };

  function iconFor(k: string): string {
    if (k === "warning_on") return "warning";
    if (k === "warning_off") return "clear";
    if (k === "hull_threshold") return "hull";
    if (k === "fuel_threshold") return "fuel";
    if (k === "takeoff" || k === "landed") return k;
    if (k === "seat_enter") return "seat";
    if (k === "seat_leave") return "leave";
    if (k === "ship_change" || k === "boarded" || k === "disembarked") return "ship";
    if (k === "mode_change") return "mode";
    if (k.startsWith("quantum")) return "quantum";
    if (k === "qt_calibration") return "sync";
    if (k.startsWith("jump_")) return "jump";
    if (k === "kill" || k === "vehicle_destroyed") return "kill";
    if (k === "ship_lost") return "lost";
    if (k === "death" || ["spawn", "downed", "dead", "respawn", "incapacitated"].includes(k)) return "life";
    if (k.startsWith("contract")) return "contract";
    if (k.startsWith("objective")) return "objective";
    if (k === "reward") return "reward";
    if (k.startsWith("armistice")) return "armistice";
    if (k === "jurisdiction" || k === "mark") return "flag";
    if (k.startsWith("monitored")) return "eye";
    if (k.startsWith("comms")) return "comms";
    if (k.startsWith("restricted")) return "restricted";
    if (k.startsWith("private")) return "private";
    if (k === "shard_join") return "server";
    if (k.startsWith("hangar")) return "hangar";
    if (k === "injury") return "injury";
    if (k === "healed") return "heal";
    if (k === "blueprint") return "blueprint";
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
    flex: none;
  }
  path {
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
</style>
