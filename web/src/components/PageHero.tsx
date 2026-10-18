import type { ComponentChildren } from "preact";

export function PageHero({ kicker, title, children }: { kicker: string; title: string; children?: ComponentChildren }) {
  return (
    <header class="page-hero">
      <p class="kicker">{kicker}</p>
      <h1>{title}</h1>
      {children && <div class="page-hero-lede">{children}</div>}
    </header>
  );
}
