export type DayId = "fri" | "sat" | "sun";
export type Kind =
  | "music"
  | "comedy"
  | "food"
  | "family"
  | "talk"
  | "workshop"
  | "other";

export type FestivalEvent = {
  id: string;
  day: DayId;
  stage: string;
  start: string;
  end: string;
  title: string;
  kind: Kind;
};

export const DAYS: { id: DayId; label: string; date: string; iso: string }[] = [
  { id: "fri", label: "Friday", date: "28 Aug", iso: "2026-08-28" },
  { id: "sat", label: "Saturday", date: "29 Aug", iso: "2026-08-29" },
  { id: "sun", label: "Sunday", date: "30 Aug", iso: "2026-08-30" },
];

export const KIND_LABEL: Record<Kind, string> = {
  music: "Music",
  comedy: "Comedy",
  food: "Food",
  family: "Family",
  talk: "Talks",
  workshop: "Workshop",
  other: "Other",
};

/** Minutes from 00:00. After-midnight times (00:xx) count as +24h. */
export function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  const mins = h * 60 + m;
  return h < 6 ? mins + 24 * 60 : mins;
}

export function eventDuration(ev: FestivalEvent): number {
  return toMinutes(ev.end) - toMinutes(ev.start);
}

export function nowDayId(now = new Date()): DayId | null {
  const iso = now.toISOString().slice(0, 10);
  const hit = DAYS.find((d) => d.iso === iso);
  return hit?.id ?? null;
}
