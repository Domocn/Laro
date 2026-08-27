import { registerSW } from "virtual:pwa-register";
import { Nav } from "./components/Nav";
import { useOnline, useRoute } from "./lib/hooks";
import { FoodPage } from "./pages/FoodPage";
import { HomePage } from "./pages/HomePage";
import { InfoPage } from "./pages/InfoPage";
import { LineupPage } from "./pages/LineupPage";
import { MapPage } from "./pages/MapPage";
import { PlanPage } from "./pages/PlanPage";
import { TimetablePage } from "./pages/TimetablePage";

registerSW({ immediate: true });

export function App() {
  const route = useRoute();
  const online = useOnline();

  let body = <HomePage />;
  if (route.name === "timetable") {
    body = <TimetablePage day={route.day} stage={route.stage} q={route.q} />;
  } else if (route.name === "lineup") {
    body = <LineupPage q={route.q} kind={route.kind} />;
  } else if (route.name === "map") {
    body = <MapPage cat={route.cat} />;
  } else if (route.name === "food") {
    body = <FoodPage q={route.q} />;
  } else if (route.name === "info") {
    body = <InfoPage />;
  } else if (route.name === "plan") {
    body = <PlanPage />;
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <strong>Feastival Pocket</strong>
          <span>Unofficial 2026 companion</span>
        </div>
        <span className={`chip ${online ? "online" : "offline"}`} style={{ marginLeft: "auto" }}>
          {online ? "Online" : "Offline — cached"}
        </span>
      </header>
      <main>{body}</main>
      <Nav current={route.name} />
    </div>
  );
}
