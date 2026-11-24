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

/** The roster's sections: crews by ship, people by server, or by what they're doing. */
export function groupRoster(rows: MemberSummary[], by: GroupBy, myShard: string | null): Group[] {
  const live = rows.filter(online);
  const offline = rows.filter((m) => !online(m)).sort(byName);
  const out: Group[] = [];

  if (by === "ship") {
    const ships = new Map<string, MemberSummary[]>();
    const loose: MemberSummary[] = [];
    for (const m of live) {
      if (m.ship) ships.set(m.ship.id, [...(ships.get(m.ship.id) ?? []), m]);
      else loose.push(m);
    }
    const crews = [...ships.values()].sort(
      (a, b) => b.length - a.length || a[0].ship!.model.localeCompare(b[0].ship!.model),
    );
    for (const crew of crews) {
      const ship = crew[0].ship!;
      out.push({
        key: `ship:${ship.id}`,
        title: ship.model,
        sub: crew.length > 1 ? `${crew.length} aboard` : ship.manufacturer ?? undefined,
        members: crew.sort(byRoleThenName),
      });
    }
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
