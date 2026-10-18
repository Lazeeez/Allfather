import { Emblem } from "./Emblem.tsx";

export function ProgressRing({ fraction, label, size = "lg" }: { fraction?: number | null; label?: string; size?: "sm" | "lg" }) {
  const f = fraction == null ? null : Math.max(0, Math.min(1, fraction));
  return (
    <div class={`progress-ring pr-${size}${f == null ? " busy" : ""}`} role="progressbar" aria-label={label ?? "Loading"}
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={f == null ? undefined : Math.round(100 * f)}>
      <svg viewBox="-50 -50 100 100" aria-hidden="true">
        <circle class="pr-track" r="44" />
        <circle class="pr-arc" r="44" pathLength={1} style={{ strokeDashoffset: f == null ? undefined : 1 - f }} transform="rotate(-90)" />
      </svg>
      {size === "lg" && (
        <span class="pr-center" aria-hidden="true">
          {f == null ? <Emblem /> : <span class="pr-value">{Math.round(100 * f)}%</span>}
        </span>
      )}
    </div>
  );
}
