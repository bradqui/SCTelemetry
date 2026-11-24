// Mirrors shared/fleet_shared/patch.py: objects merge key by key; anything else
// (including null and arrays) replaces. Keys are never deleted.

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** A new state: `target` with `patch` merged in. `target` is not modified. */
export function applyPatch<T>(target: T, patch: Record<string, unknown>): T {
  const out: Record<string, unknown> = isObject(target) ? { ...target } : {};
  for (const [key, value] of Object.entries(patch)) {
    out[key] = isObject(value) && isObject(out[key]) ? applyPatch(out[key], value) : value;
  }
  return out as T;
}

export type { Json };
