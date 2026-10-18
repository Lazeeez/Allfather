import { type RefObject } from "preact";
import { useLayoutEffect, useRef } from "preact/hooks";
import { reducedMotion } from "./reveal.ts";

export function useFlip(list: RefObject<HTMLElement>, version: unknown, animate: boolean) {
  const tops = useRef(new Map<string, number>());
  const seen = useRef<unknown>(version);
  useLayoutEffect(() => {
    const el = list.current;
    const rows = el ? [...el.querySelectorAll<HTMLElement>(":scope > li[data-flip]")] : [];
    const now = new Map(rows.map((r) => [r.dataset.flip!, r.offsetTop]));
    if (version !== seen.current && animate && !reducedMotion()) {
      for (const r of rows) {
        const before = tops.current.get(r.dataset.flip!);
        const dy = before == null ? 0 : before - now.get(r.dataset.flip!)!;
        if (Math.abs(dy) > 1) {
          r.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 700, easing: "cubic-bezier(.2, .7, .2, 1)" });
        }
      }
    }
    seen.current = version;
    tops.current = now;
  });
}
