import { pct } from "../lib/format.ts";

export function Tile({ label, value, note }: { label: string; value: number | null; note: string }) {
  return (
    <div class="tile frame bracket">
      <span class="tile-label">{label}</span>
      <span class="tile-value">{value != null ? pct(value) : "–"}</span>
      <span class="tile-note">{note}</span>
    </div>
  );
}
