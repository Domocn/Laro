import events from "../data/events.json";
import { DAYS, nowDayId, toMinutes, type FestivalEvent } from "../data/types";
import { toHash } from "../lib/routes";
import { EventRow } from "../components/EventRow";
import { usePlan } from "../lib/usePlan";

const all = events as FestivalEvent[];

function headlineFor(day: NonNullable<ReturnType<typeof nowDayId>> | "fri") {
  return all
    .filter((e) => e.day === day && e.stage === "Main Stage")
    .sort((a, b) => toMinutes(a.start) - toMinutes(b.start));
}

export function HomePage() {
  const plan = usePlan();
  const today = nowDayId() ?? "fri";
  const dayMeta = DAYS.find((d) => d.id === today)!;
  const headliners = headlineFor(today);
  const saved = all
    .filter((e) => plan.has(e.id) && e.day === today)
    .sort((a, b) => toMinutes(a.start) - toMinutes(b.start))
    .slice(0, 5);

  return (
    <div className="page">
      <section className="hero">
        <div className="kicker">Unofficial pocket guide · 28–30 Aug 2026</div>
        <h1>Good music, good food, no signal required.</h1>
        <p>
          Timetable, line-up, traders and travel for Big Feastival on Alex James&apos; farm
          are stored on this phone. Open it once on wifi, then use it in the field.
        </p>
      </section>

      <div className="grid">
        <a className="tile" href={toHash({ name: "timetable", day: today })}>
          <strong>Today&apos;s times</strong>
          <small>
            {dayMeta.label} {dayMeta.date}
          </small>
        </a>
        <a className="tile" href={toHash({ name: "plan" })}>
          <strong>My plan</strong>
          <small>{plan.ids.length} saved sets</small>
        </a>
        <a className="tile" href={toHash({ name: "map" })}>
          <strong>On-site map</strong>
          <small>Stages, food, facilities</small>
        </a>
        <a className="tile" href={toHash({ name: "info" })}>
          <strong>Travel &amp; camping</strong>
          <small>OX7 6UJ · Kingham</small>
        </a>
      </div>

      <section className="card">
        <div className="row">
          <h2>Main Stage · {dayMeta.label}</h2>
          <a href={toHash({ name: "timetable", day: today, stage: "Main Stage" })}>Full grid</a>
        </div>
        {headliners.map((event) => (
          <EventRow key={event.id} event={event} saved={plan.has(event.id)} onToggle={plan.toggle} />
        ))}
      </section>

      {saved.length > 0 ? (
        <section className="card">
          <h2>Up next on your plan</h2>
          {saved.map((event) => (
            <EventRow key={event.id} event={event} saved onToggle={plan.toggle} />
          ))}
        </section>
      ) : null}

      <p className="notice">
        Fan-made companion, not affiliated with PWR Events or Big Feastival. Times copied from{" "}
        <a href="https://bigfeastival.com/timetable/">bigfeastival.com/timetable</a> on 27 Aug
        2026. Official tickets and last-minute changes live on the real site.
      </p>
    </div>
  );
}
