import { useMemo } from "react";
import events from "../data/events.json";
import { KIND_LABEL, type FestivalEvent, type Kind } from "../data/types";
import { go } from "../lib/routes";
import { usePlan } from "../lib/usePlan";
import { EventRow } from "../components/EventRow";
import { SearchField } from "../components/SearchField";

const all = events as FestivalEvent[];
const KINDS = Object.keys(KIND_LABEL) as Kind[];

function uniqueActs(list: FestivalEvent[]): FestivalEvent[] {
  const seen = new Set<string>();
  const out: FestivalEvent[] = [];
  for (const ev of [...list].sort((a, b) => a.title.localeCompare(b.title))) {
    const key = ev.title.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(ev);
  }
  return out;
}

export function LineupPage({ q, kind }: { q?: string; kind?: string }) {
  const plan = usePlan();
  const query = (q ?? "").trim().toLowerCase();
  const acts = useMemo(() => {
    return uniqueActs(all)
      .filter((e) => (kind ? e.kind === kind : true))
      .filter((e) => (query ? e.title.toLowerCase().includes(query) : true));
  }, [kind, query]);

  return (
    <div className="page">
      <h1>Line-up</h1>
      <p>Search the full billed weekend, then star what you refuse to miss.</p>
      <SearchField
        value={q ?? ""}
        placeholder="Search Basement Jaxx, Simon Rogan…"
        onCommit={(next) => go({ name: "lineup", q: next || undefined, kind })}
      />
      <div className="filters">
        <button className={`pill ${!kind ? "active" : ""}`} onClick={() => go({ name: "lineup", q })}>
          All
        </button>
        {KINDS.map((k) => (
          <button
            key={k}
            className={`pill ${kind === k ? "active" : ""}`}
            onClick={() => go({ name: "lineup", q, kind: k })}
          >
            {KIND_LABEL[k]}
          </button>
        ))}
      </div>
      <section className="card">
        <div className="meta">{acts.length} names</div>
        {acts.map((event) => (
          <EventRow
            key={event.id}
            event={event}
            saved={plan.has(event.id)}
            onToggle={plan.toggle}
            showDay
          />
        ))}
      </section>
    </div>
  );
}
