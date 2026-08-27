import { PLACES, type Place } from "../data/places";
import { go } from "../lib/routes";

const CATS: { id: Place["category"] | "all"; label: string }[] = [
  { id: "all", label: "All" },
  { id: "stage", label: "Stages" },
  { id: "experience", label: "Experiences" },
  { id: "bar", label: "Bars" },
  { id: "facility", label: "Facilities" },
];

export function MapPage({ cat }: { cat?: string }) {
  const active = CATS.some((c) => c.id === cat) ? cat : "all";
  const list = PLACES.filter((p) => (active === "all" ? true : p.category === active));
  return (
    <div className="page">
      <h1>Site directory</h1>
      <p>
        Offline list of stages, experiences, bars and facilities from the official festival map.
        Use it when the interactive map will not load.
      </p>
      <div className="filters">
        {CATS.map((c) => (
          <button
            key={c.id}
            className={`pill ${active === c.id ? "active" : ""}`}
            onClick={() => go({ name: "map", cat: c.id === "all" ? undefined : c.id })}
          >
            {c.label}
          </button>
        ))}
      </div>
      {list.map((place) => (
        <article className="card" key={place.id}>
          <div className="row">
            <h2>{place.name}</h2>
            <span className="chip">{place.category}</span>
          </div>
          <p>{place.blurb}</p>
        </article>
      ))}
    </div>
  );
}
