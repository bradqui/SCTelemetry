import { shardLabel } from "../../lib/format";
import type { MemberSummary } from "../../lib/types";

export type GroupBy = "ship" | "server" | "status";

export interface Group {
  key: string;
  title: string;
  sub?: string;
  /** Highlight: your own server. */
  mine?: boolean;
  members: MemberSummary[];
}

const ROLE_ORDER: Record<string, number> = { pilot: 0, copilot: 1, gunner: 2, crew: 3 };

export function online(m: MemberSummary): boolean {
  return m.presence !== "offline";
}

function byRoleThenName(a: MemberSummary, b: MemberSummary): number {
  const ra = ROLE_ORDER[a.role ?? ""] ?? 9;
  const rb = ROLE_ORDER[b.role ?? ""] ?? 9;
  return ra - rb || a.name.localeCompare(b.name);
}

function byName(a: MemberSummary, b: MemberSummary): number {
  return a.name.localeCompare(b.name);
}

/** Which crew someone belongs to: the ship they're seated in, or the one they're aboard on
 * foot (its owner flying it: their ship; otherwise the ship's channel name). */
export function crewKey(m: MemberSummary): string | null {
  if (m.ship) return `ship:${m.ship.id}`;
  const a = m.location?.aboard;
  if (!a) return null;
  return a.ship_id ? `ship:${a.ship_id}` : `aboard:${a.owner.toLowerCase()}:${a.ship}`;
}

/** "Wren's RSI Constellation Taurus" / "own Origin M80": whose ship someone is aboard. */
export function aboardText(m: MemberSummary, nameOf: (id: string) => string | undefined): string | null {
  const a = m.location?.aboard;
  if (!a) return null;
  if (a.owner_id === m.id) return `own ${a.ship}`;
  const owner = (a.owner_id && nameOf(a.owner_id)) || a.owner;
  return `${owner}'s ${a.ship}`;
}

/** What someone not in a seat is doing: "On foot · aboard Wren's RSI Constellation Taurus". */
export function footLine(m: MemberSummary, nameOf: (id: string) => string | undefined): string {
  const base = m.locomotion === "eva" ? "EVA" : m.locomotion === "seated" ? "Seated" : "On foot";
  const aboard = aboardText(m, nameOf);
  return aboard ? `${base} · aboard ${aboard}` : base;
}

/** Crews: seated members' ships, with people aboard on foot added to theirs. */
export function crews(rows: MemberSummary[]): MemberSummary[][] {
  const by = new Map<string, MemberSummary[]>();
  for (const m of rows) {
    const k = online(m) ? crewKey(m) : null;
    if (k) by.set(k, [...(by.get(k) ?? []), m]);
  }
  // A crew is shown under a ship someone's flying, or under the channel's name.
  return [...by.values()].map((crew) =>
    crew.sort((a, b) => Number(!a.ship) - Number(!b.ship) || byRoleThenName(a, b)),
  );
}

/** A crew's ship name: the seated member's model, else the channel's. */
export function crewTitle(crew: MemberSummary[]): string {
  return crew[0].ship?.model ?? crew[0].location?.aboard?.ship ?? "Ship";
}

/** The roster's sections: crews by ship, people by server, or by what they're doing. */
export function groupRoster(rows: MemberSummary[], by: GroupBy, myShard: string | null): Group[] {
  const live = rows.filter(online);
  const offline = rows.filter((m) => !online(m)).sort(byName);
  const out: Group[] = [];

  if (by === "ship") {
    const groups = crews(live).sort(
      (a, b) => b.length - a.length || crewTitle(a).localeCompare(crewTitle(b)),
    );
    for (const crew of groups) {
      const ship = crew[0].ship;
      out.push({
        key: crewKey(crew[0])!,
        title: crewTitle(crew),
        sub: crew.length > 1 ? `${crew.length} aboard` : (ship?.manufacturer ?? undefined),
        members: crew,
      });
    }
    const loose = live.filter((m) => !crewKey(m));
    if (loose.length) out.push({ key: "loose", title: "Not in a ship", members: loose.sort(byName) });
  } else if (by === "server") {
    const servers = new Map<string, MemberSummary[]>();
    for (const m of live) {
      const k = m.location?.shard ?? "";
      servers.set(k, [...(servers.get(k) ?? []), m]);
    }
    const keys = [...servers.keys()].sort((a, b) => {
      if (a === myShard) return -1;
      if (b === myShard) return 1;
      if (!a) return 1;
      if (!b) return -1;
      return servers.get(b)!.length - servers.get(a)!.length;
    });
    for (const k of keys) {
      const mine = !!k && k === myShard;
      out.push({
        key: `srv:${k}`,
        title: k ? (mine ? "Your server" : `Server ${shardLabel(k)}`) : "Server unknown",
        sub: mine ? (shardLabel(k) ?? undefined) : undefined,
        mine,
        members: servers.get(k)!.sort(byName),
      });
    }
  } else {
    const buckets: [string, string, (m: MemberSummary) => boolean][] = [
      ["flying", "In a ship", (m) => !!m.ship],
      ["foot", "On foot", (m) => !m.ship && m.presence !== "idle"],
      ["idle", "Agent on, not in game", (m) => !m.ship && m.presence === "idle"],
    ];
    for (const [key, title, test] of buckets) {
      const members = live.filter(test).sort(byName);
      if (members.length) out.push({ key, title, members });
    }
  }
  if (offline.length) out.push({ key: "offline", title: "Offline", members: offline });
  return out;
}
