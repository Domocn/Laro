import { useState } from "react";
import { DINING, STREET_FOOD } from "../data/food";
import { SearchField } from "../components/SearchField";

export function FoodPage({ q }: { q?: string }) {
  const [query, setQuery] = useState(q ?? "");
  const needle = query.trim().toLowerCase();
  const vendors = STREET_FOOD.filter((v) =>
    needle ? `${v.name} ${v.vibe}`.toLowerCase().includes(needle) : true
  );
  return (
    <div className="page">
      <h1>Food &amp; drink</h1>
      <p>Street food from the official map, plus bookable dining experiences.</p>
      <SearchField
        value={query}
        placeholder="Search tacos, dumplings, paella…"
        onChange={setQuery}
      />
      <section className="card">
        <h2>Dining experiences</h2>
        {DINING.map((d) => (
          <article key={d.name}>
            <div className="row">
              <strong>{d.name}</strong>
              <span className="meta">{d.when}</span>
            </div>
            <p>{d.detail}</p>
          </article>
        ))}
      </section>
      {vendors.map((v) => (
        <article className="card" key={v.name}>
          <h2>{v.name}</h2>
          <p>{v.vibe}</p>
        </article>
      ))}
    </div>
  );
}
