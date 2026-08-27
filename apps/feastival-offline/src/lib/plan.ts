const KEY = "feastival-pocket-plan-v1";

export function loadPlan(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function savePlan(ids: string[]): void {
  localStorage.setItem(KEY, JSON.stringify(ids));
}

export function togglePlan(ids: string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
}
