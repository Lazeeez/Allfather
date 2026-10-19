import { Emblem } from "../components/Emblem.tsx";
import { href } from "../lib/router.ts";

export function NotFound() {
  return (
    <div class="container narrow center not-found">
      <Emblem />
      <h1>This page doesn't exist</h1>
      <p class="section-lede">The link may be mistyped, or the page has moved.</p>
      <div class="case-links">
        <a class="btn primary" href={href("search")}>Search a repository</a>
        <a class="btn" href={href("home")}>Go to the home page</a>
      </div>
    </div>
  );
}
