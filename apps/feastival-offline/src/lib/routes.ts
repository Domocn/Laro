export type Route =
  | { name: "home" }
  | { name: "timetable"; day?: string; stage?: string; q?: string }
  | { name: "lineup"; q?: string; kind?: string }
  | { name: "map"; cat?: string }
  | { name: "food"; q?: string }
  | { name: "info" }
  | { name: "plan" };

function params(search: string): URLSearchParams {
  return new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
}

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, "") || "/";
  const [path, search = ""] = raw.split("?");
  const p = params(search);
  const segs = path.split("/").filter(Boolean);
  const head = segs[0] ?? "home";
  if (head === "timetable") {
    return {
      name: "timetable",
      day: p.get("day") ?? undefined,
      stage: p.get("stage") ?? undefined,
      q: p.get("q") ?? undefined,
    };
  }
  if (head === "lineup") {
    return { name: "lineup", q: p.get("q") ?? undefined, kind: p.get("kind") ?? undefined };
  }
  if (head === "map") return { name: "map", cat: p.get("cat") ?? undefined };
  if (head === "food") return { name: "food", q: p.get("q") ?? undefined };
  if (head === "info") return { name: "info" };
  if (head === "plan") return { name: "plan" };
  return { name: "home" };
}

export function toHash(route: Route): string {
  const q = new URLSearchParams();
  if (route.name === "timetable") {
    if (route.day) q.set("day", route.day);
    if (route.stage) q.set("stage", route.stage);
    if (route.q) q.set("q", route.q);
    const s = q.toString();
    return s ? `#/timetable?${s}` : "#/timetable";
  }
  if (route.name === "lineup") {
    if (route.q) q.set("q", route.q);
    if (route.kind) q.set("kind", route.kind);
    const s = q.toString();
    return s ? `#/lineup?${s}` : "#/lineup";
  }
  if (route.name === "map") {
    if (route.cat) q.set("cat", route.cat);
    const s = q.toString();
    return s ? `#/map?${s}` : "#/map";
  }
  if (route.name === "food") {
    if (route.q) q.set("q", route.q);
    const s = q.toString();
    return s ? `#/food?${s}` : "#/food";
  }
  if (route.name === "info") return "#/info";
  if (route.name === "plan") return "#/plan";
  return "#/";
}

export function go(route: Route): void {
  window.location.hash = toHash(route).replace(/^#/, "");
}
