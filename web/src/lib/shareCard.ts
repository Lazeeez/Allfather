import { MARK_RUNE } from "../components/Emblem.tsx";

export interface CardHit {
  qualname: string;
  path: string;
  line: number;
}

export interface CardInput {
  repo: string;
  query: string;
  hits: CardHit[];
  stage: string;
  site: string;
}

const W = 1200;
const H = 630;
const COLORS = { bg: "#0f1424", panel: "#171f36", gold: "#e2b24a", ink: "#f2ebdc", muted: "#a9b0c3", line: "#2a3658", onGold: "#1d1607" };

const fit = (ctx: CanvasRenderingContext2D, text: string, width: number): string => {
  if (ctx.measureText(text).width <= width) return text;
  let lo = 0;
  let hi = text.length;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (ctx.measureText(`${text.slice(0, mid)}…`).width <= width) lo = mid;
    else hi = mid - 1;
  }
  return `${text.slice(0, lo)}…`;
};

export const cardTitle = (query: string): string => {
  const first = query.replace(/\r/g, "").split("\n").find((l) => l.trim()) ?? "";
  return first.trim().replace(/\s+/g, " ");
};

export async function drawCard(input: CardInput): Promise<Blob> {
  await document.fonts?.ready;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;
  const css = getComputedStyle(document.documentElement);
  const sans = css.getPropertyValue("--sans").trim() || "sans-serif";
  const mono = css.getPropertyValue("--mono").trim() || "monospace";

  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = COLORS.gold;
  ctx.fillRect(0, 0, W, 6);

  ctx.save();
  ctx.translate(64, 56);
  ctx.scale(1.5, 1.5);
  ctx.fillStyle = COLORS.gold;
  ctx.beginPath();
  ctx.roundRect(0, 0, 32, 32, 8);
  ctx.fill();
  ctx.strokeStyle = COLORS.onGold;
  ctx.lineWidth = 2.6;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.stroke(new Path2D(MARK_RUNE));
  ctx.restore();

  ctx.fillStyle = COLORS.ink;
  ctx.font = `700 32px ${sans}`;
  ctx.fillText("Allfather", 130, 92);
  const brand = ctx.measureText("Allfather").width;
  ctx.fillStyle = COLORS.muted;
  ctx.font = `500 22px ${sans}`;
  ctx.fillText(fit(ctx, `Where to fix it in ${input.repo}`, W - 200 - brand), 150 + brand, 90);

  ctx.fillStyle = COLORS.ink;
  ctx.font = `600 34px ${sans}`;
  ctx.fillText(fit(ctx, cardTitle(input.query), W - 128), 64, 160);

  input.hits.slice(0, 3).forEach((h, i) => {
    const y = 214 + i * 104;
    ctx.fillStyle = COLORS.panel;
    ctx.beginPath();
    ctx.roundRect(64, y, W - 128, 88, 12);
    ctx.fill();
    ctx.strokeStyle = i === 0 ? COLORS.gold : COLORS.line;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = COLORS.gold;
    ctx.font = `600 34px ${mono}`;
    ctx.fillText(String(i + 1), 88, y + 58);
    ctx.fillStyle = COLORS.ink;
    ctx.font = `600 30px ${mono}`;
    ctx.fillText(fit(ctx, h.qualname, W - 260), 144, y + 40);
    ctx.fillStyle = COLORS.muted;
    ctx.font = `400 22px ${mono}`;
    ctx.fillText(fit(ctx, `${h.path}:${h.line}`, W - 260), 144, y + 72);
  });

  ctx.fillStyle = COLORS.muted;
  ctx.font = `400 20px ${sans}`;
  ctx.fillText(fit(ctx, input.stage, W - 420), 64, H - 56);
  ctx.fillStyle = COLORS.gold;
  ctx.font = `600 22px ${sans}`;
  ctx.textAlign = "right";
  ctx.fillText(input.site, W - 64, H - 56);

  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("could not draw the card"))), "image/png"));
}

export async function shareCard(input: CardInput, link: string): Promise<"shared" | "downloaded"> {
  const blob = await drawCard(input);
  const file = new File([blob], `allfather-${input.repo.replace("/", "-")}.png`, { type: "image/png" });
  const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean };
  if (nav.share && nav.canShare?.({ files: [file] })) {
    try {
      await nav.share({ files: [file], title: `Allfather on ${input.repo}`, text: cardTitle(input.query), url: link });
      return "shared";
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return "shared";
    }
  }
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: file.name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return "downloaded";
}
