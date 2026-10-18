import { useId } from "preact/hooks";

export const MARK_RUNE = "M12.5 7.5v17M12.5 8.5l7.5 4.6M12.5 14.6l7.5 4.6";
export const MARK_GOLD = ["#f8e3a0", "#e2b24a", "#b8862a"] as const;

export function Emblem({ class: cls = "" }: { class?: string }) {
  const id = `mark${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg class={`emblem ${cls}`} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2=".35" y2="1">
          <stop offset="0" stop-color={MARK_GOLD[0]} />
          <stop offset=".55" stop-color={MARK_GOLD[1]} />
          <stop offset="1" stop-color={MARK_GOLD[2]} />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${id})`} />
      <rect x=".75" y=".75" width="30.5" height="30.5" rx="7.25" fill="none" stroke="#fff6d6" stroke-opacity=".55" stroke-width="1.5" />
      <path d={MARK_RUNE} fill="none" stroke="#fff3c8" stroke-opacity=".5" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" transform="translate(0 .8)" />
      <path d={MARK_RUNE} fill="none" stroke="#1d1607" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  );
}

export function Seer({ text, size = "md" }: { text?: string; size?: "sm" | "md" | "lg" }) {
  return (
    <span class={`seer seer-${size}`}>
      <span class="spinner" aria-hidden="true" />
      {text && <span class="seer-text">{text}</span>}
    </span>
  );
}
