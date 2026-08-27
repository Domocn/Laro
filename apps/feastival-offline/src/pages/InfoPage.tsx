import { CAMPING_KIT, TIPS, TRAVEL } from "../data/info";

export function InfoPage() {
  return (
    <div className="page">
      <h1>Travel &amp; camping</h1>
      <section className="card">
        <h2>{TRAVEL.site}</h2>
        <p>
          Postcode <strong>{TRAVEL.postcode}</strong>. Follow yellow signs on arrival, not sat nav.
        </p>
      </section>
      <section className="card">
        <h2>Car</h2>
        <p>{TRAVEL.car}</p>
      </section>
      <section className="card">
        <h2>Train</h2>
        <p>{TRAVEL.train}</p>
      </section>
      <section className="card">
        <h2>Free station shuttle</h2>
        <p>{TRAVEL.shuttleIn}</p>
        <p>{TRAVEL.shuttleOut}</p>
      </section>
      <section className="card">
        <h2>Taxi &amp; coach</h2>
        <p>{TRAVEL.taxi}</p>
        <p>{TRAVEL.coach}</p>
      </section>
      <section className="card">
        <h2>Camping kit</h2>
        <ul>
          {CAMPING_KIT.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      {TIPS.map((t) => (
        <section className="card" key={t.q}>
          <h2>{t.q}</h2>
          <p>{t.a}</p>
        </section>
      ))}
      <p className="notice">
        Always defer to stewards and{" "}
        <a href="https://bigfeastival.com/">bigfeastival.com</a> for gates, access maps and
        ticket rules.
      </p>
    </div>
  );
}
