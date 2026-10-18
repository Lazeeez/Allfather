import { Emblem } from "./Emblem.tsx";
import { RUNES } from "./RuneRing.tsx";
import { LOAD_STEPS, runesLit, stepOf } from "../lib/progress.ts";

const SLOTS = LOAD_STEPS.reduce((n, s) => n + s.runes + 1, 0);
const LAYOUT = LOAD_STEPS.flatMap((s, step) => [
  { step, gap: true, index: -1 },
  ...Array.from({ length: s.runes }, (_, index) => ({ step, gap: false, index })),
]);

export function RuneProgress({ fraction, label, phase, size = "lg" }: { fraction?: number | null; label?: string; phase?: string; size?: "sm" | "lg" }) {
  const f = fraction == null ? null : Math.max(0, Math.min(1, fraction));
  const lit = f == null ? LOAD_STEPS.map(() => 0) : runesLit(f);
  const now = stepOf(f, phase);
  let rune = 0;
  return (
    <div class={`rune-progress rp-${size}${f == null ? " busy" : ""}`} role="progressbar" aria-label={label ?? "Loading"}
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={f == null ? undefined : Math.round(100 * f)}>
      <svg viewBox="-100 -100 200 200" aria-hidden="true">
        {size === "sm" && (
          <>
            <circle class="rp-track" r="92" />
            <circle class="rp-arc" r="92" pathLength={1} style={{ strokeDashoffset: f == null ? undefined : 1 - f }} transform="rotate(-90)" />
          </>
        )}
        {size === "lg" && LAYOUT.map((slot, i) => {
          const turn = `rotate(${(i * 360) / SLOTS})`;
          if (slot.gap) return <circle key={i} class={`rp-gap${slot.step <= now ? " reached" : ""}`} r="2.2" cy="-76" transform={turn} />;
          const d = RUNES[rune++ % RUNES.length];
          const state = slot.index < lit[slot.step] ? "on" : slot.step === now ? "now" : slot.step < now ? "on" : "";
          return (
            <g key={i} class={state} style={{ "--i": slot.index }} transform={`${turn} translate(0 -76) scale(1.25) translate(-4 -8)`}>
              <path d={d} />
            </g>
          );
        })}
      </svg>
      <span class="rp-eye"><Emblem live /></span>
    </div>
  );
}

export function LoadSteps({ fraction, phase }: { fraction?: number | null; phase?: string }) {
  const now = stepOf(fraction ?? null, phase);
  return (
    <ol class="load-steps" aria-hidden="true">
      {LOAD_STEPS.map((s, i) => <li key={s.phase} class={i < now ? "done" : i === now ? "now" : ""}>{s.label}</li>)}
    </ol>
  );
}
