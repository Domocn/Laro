import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { eventDuration, toMinutes, type FestivalEvent } from "./data/types";
import { parseHash, toHash } from "./lib/routes";
import { togglePlan } from "./lib/plan";

const dir = dirname(fileURLToPath(import.meta.url));
const events = JSON.parse(
  readFileSync(join(dir, "data/events.json"), "utf8")
) as FestivalEvent[];

describe("festival data", () => {
  it("has unique event ids", () => {
    const ids = events.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("has friday headliners and sunday Bastille", () => {
    expect(events.some((e) => e.title === "Basement Jaxx" && e.day === "fri")).toBe(true);
    expect(events.some((e) => e.title === "The Streets" && e.day === "sat")).toBe(true);
    expect(events.some((e) => e.title === "Bastille" && e.day === "sun")).toBe(true);
  });

  it("keeps end after start, including after midnight", () => {
    for (const ev of events) {
      expect(eventDuration(ev), ev.id).toBeGreaterThan(0);
    }
    expect(toMinutes("00:15")).toBeGreaterThan(toMinutes("22:45"));
  });
});

describe("routing and plan", () => {
  it("round-trips timetable filters", () => {
    const hash = toHash({ name: "timetable", day: "sat", stage: "Main Stage", q: "streets" });
    expect(parseHash(hash)).toEqual({
      name: "timetable",
      day: "sat",
      stage: "Main Stage",
      q: "streets",
    });
  });

  it("toggles saved ids", () => {
    expect(togglePlan(["a"], "b")).toEqual(["a", "b"]);
    expect(togglePlan(["a", "b"], "a")).toEqual(["b"]);
  });
});
