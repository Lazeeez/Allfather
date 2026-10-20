import { useEffect, useState } from "preact/hooks";
import { getJSON } from "./data.ts";

export interface FrozenRun {
  issues: number;
  "hit@1": number;
  "hit@5": number;
  "hit@10": number;
  "all@10": number;
  mrr: number;
  "hit@10_ci95": [number, number];
}

export interface Holdout {
  adr: string;
  runs: Record<"holdout_function" | "holdout_file" | "lite_function" | "lite_file", FrozenRun>;
}

export function useHoldout(): Holdout | null {
  const [data, setData] = useState<Holdout | null>(null);
  useEffect(() => {
    getJSON<Holdout>("data/holdout.json").then(setData, () => {});
  }, []);
  return data;
}
