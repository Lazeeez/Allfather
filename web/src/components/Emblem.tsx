export const MARK_RUNE = "M12.5 7.5v17M12.5 8.5l7.5 4.6M12.5 14.6l7.5 4.6";

export function Emblem({ class: cls = "" }: { class?: string }) {
  return (
    <svg class={`emblem ${cls}`} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="var(--mark-bg, #e9b949)" />
      <path d={MARK_RUNE} fill="none" stroke="var(--mark-ink, #17130a)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
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
