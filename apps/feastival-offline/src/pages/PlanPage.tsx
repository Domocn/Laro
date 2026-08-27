import events from "../data/events.json";
import { DAYS, toMinutes, type FestivalEvent } from "../data/types";
import { EventRow } from "../components/EventRow";
import { usePlan } from "../lib/usePlan";
import { toHash } from "../lib/routes";

const all = events as FestivalEvent[];

export function PlanPage() {
  const plan = usePlan();
  const saved = all
    .filter((e) => plan.has(e.id))
    .sort(
      (a, b) =>
        DAYS.findIndex((d) => d.id === a.day) - DAYS.findIndex((d) => d.id === b.day) ||
        toMinutes(a.start) - toMinutes(b.start)
    );

  return (
    <div className="page">
      <h1>My plan</h1>
      <p>Saved on this device only. Works offline. Clearing site data will wipe stars.</p>
      {saved.length === 0 ? (
        <div className="empty">
          Nothing saved yet. Open the timetable and tap ☆.{" "}
          <a href={toHash({ name: "timetable" })}>Browse times</a>
        </div>
      ) : (
        DAYS.map((d) => {
          const list = saved.filter((e) => e.day === d.id);
          if (!list.length) return null;
          return (
            <section className="card" key={d.id}>
              <h2>
                {d.label} {d.date}
              </h2>
              {list.map((event) => (
                <EventRow key={event.id} event={event} saved onToggle={plan.toggle} />
              ))}
            </section>
          );
        })
      )}
    </div>
  );
}
