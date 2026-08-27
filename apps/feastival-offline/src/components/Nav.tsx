import { toHash, type Route } from "../lib/routes";

const LINKS: { route: Route; label: string }[] = [
  { route: { name: "home" }, label: "Home" },
  { route: { name: "timetable" }, label: "Times" },
  { route: { name: "lineup" }, label: "Line-up" },
  { route: { name: "map" }, label: "Map" },
  { route: { name: "food" }, label: "Food" },
  { route: { name: "plan" }, label: "My plan" },
];

export function Nav({ current }: { current: Route["name"] }) {
  return (
    <nav className="nav" aria-label="Primary">
      {LINKS.map((link) => (
        <a
          key={link.label}
          href={toHash(link.route)}
          className={current === link.route.name ? "active" : undefined}
        >
          {link.label}
        </a>
      ))}
    </nav>
  );
}
