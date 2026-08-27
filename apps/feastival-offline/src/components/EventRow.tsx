import type { FestivalEvent } from "../data/types";
import { KIND_LABEL } from "../data/types";

type Props = {
  event: FestivalEvent;
  saved: boolean;
  onToggle: (id: string) => void;
  showDay?: boolean;
};

const DAY: Record<string, string> = { fri: "Fri", sat: "Sat", sun: "Sun" };

export function EventRow({ event, saved, onToggle, showDay }: Props) {
  return (
    <article className="event">
      <div className="time">
        {showDay ? `${DAY[event.day]} ` : null}
        {event.start}
        <div>{event.end}</div>
      </div>
      <div>
        <h3>{event.title}</h3>
        <div className="meta">
          {event.stage} · {KIND_LABEL[event.kind]}
        </div>
      </div>
      <button
        className="star"
        aria-pressed={saved}
        aria-label={saved ? "Remove from my plan" : "Add to my plan"}
        onClick={() => onToggle(event.id)}
      >
        {saved ? "★" : "☆"}
      </button>
    </article>
  );
}
