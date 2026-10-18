const LIT = ".feature, .tile, .steps > li, .ecard, .tried > li, .bug-card";

export function spotlight(): () => void {
  if (!matchMedia("(hover: hover) and (pointer: fine)").matches) return () => {};
  const move = (e: PointerEvent) => {
    const card = (e.target as Element | null)?.closest?.<HTMLElement>(LIT);
    if (!card) return;
    const r = card.getBoundingClientRect();
    card.style.setProperty("--mx", `${e.clientX - r.left}px`);
    card.style.setProperty("--my", `${e.clientY - r.top}px`);
  };
  addEventListener("pointermove", move, { passive: true });
  return () => removeEventListener("pointermove", move);
}
