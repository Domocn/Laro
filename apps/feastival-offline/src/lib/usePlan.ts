import { useEffect, useState } from "react";
import { loadPlan, savePlan, togglePlan } from "./plan";

export function usePlan() {
  const [ids, setIds] = useState<string[]>(() => loadPlan());
  useEffect(() => {
    savePlan(ids);
  }, [ids]);
  return {
    ids,
    has: (id: string) => ids.includes(id),
    toggle: (id: string) => setIds((prev) => togglePlan(prev, id)),
  };
}
