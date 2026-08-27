import { useMemo, useState } from "react";
import events from "../data/events.json";
import { DAYS, toMinutes, type DayId, type FestivalEvent } from "../data/types";
import { EventRow } from "../components/EventRow";
import { SearchField } from "../components/SearchField";
import { go } from "../lib/routes";
import { usePlan } from "../lib/usePlan";

const all = events as FestivalEvent[];
const STAGES = [...new Set(all.map((e) => e.stage))];

type Props = { day?: string; stage?: string; q?: string };

export function TimetablePage({ day, stage, q }: Props) {
  const plan = usePlan();
  const dayId = (DAYS.some((d) => d.id === day) ? day : "fri") as DayId;
  const [query, setQuery] = useState(q ?? "");
  const needle = query.trim().toLowerCase();

  const rows = useMemo(() => {
    return all
      .filter((e) => e.day === dayId)
      .filter((e) => (stage ? e.stage === stage : true))
      .filter((e) =>
        needle ? `${e.title} ${e.stage} ${e.kind}`.toLowerCase().includes(needle) : true
      )
      .sort((a, b) => toMinutes(a.start) - toMinutes(b.start) || a.stage.localeCompare(b.stage));
  }, [dayId, stage, needle]);

  const grouped = useMemo(() => {
    const map = new Map<string, FestivalEvent[]>();
    for (const ev of rows) {
      const list = map.get(ev.stage) ?? [];
      list.push(ev);
      map.set(ev.stage, list);
    }
    return [...map.entries()];
  }, [rows]);

  return (
    <div className="page">
      <h1>Timetable</h1>
      <p>Every billed set we captured from the official grid. Star a row to keep it on My plan.</p>
      <SearchField
        value={query}
        placeholder="Search artist, chef or stage"
        onChange={setQuery}
      />
      <div className="filters" role="tablist" aria-label="Day">
        {DAYS.map((d) => (
          <button
            key={d.id}
            className={`pill ${d.id === dayId ? "active" : ""}`}
            onClick={() => go({ name: "timetable", day: d.id, stage })}
          >
            {d.label}
          </button>
        ))}
      </div>
      <div className="filters" role="tablist" aria-label="Stage">
        <button
          className={`pill ${!stage ? "active" : ""}`}
          onClick={() => go({ name: "timetable", day: dayId })}
        >
          All stages
        </button>
        {STAGES.map((s) => (
          <button
            key={s}
            className={`pill ${stage === s ? "active" : ""}`}
            onClick={() => go({ name: "timetable", day: dayId, stage: s })}
          >
            {s}
          </button>
        ))}
      </div>
      {grouped.length === 0 ? <div className="empty">Nothing matches those filters.</div> : null}
      {grouped.map(([name, list]) => (
        <section className="card stage-group" key={name}>
          <h2>{name}</h2>
          {list.map((event) => (
            <EventRow key={event.id} event={event} saved={plan.has(event.id)} onToggle={plan.toggle} />
          ))}
        </section>
      ))}
    </div>
  );
}
