import { pct } from "../lib/format.ts";

export function Tile({ label, value, note, ci }: { label: string; value: number | null; note: string; ci?: [number, number] }) {
  return (
    <div class="tile frame bracket">
      <span class="tile-label">{label}</span>
      <span class="tile-value">{value != null ? pct(value) : "–"}</span>
      <span class="tile-note">{note}{ci ? ` · 95% interval ${pct(ci[0])} to ${pct(ci[1])}` : ""}</span>
    </div>
  );
}
