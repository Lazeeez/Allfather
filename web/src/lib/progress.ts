/**
 * Where each loading phase sits on one overall 0..1 scale, so a load's progress only moves
 * forward: listing is quick, downloading and parsing is nearly all of it, indexing is the end.
 * The phase names are the ones engine/repo.ts reports.
 */
const PHASES: Record<string, [from: number, to: number]> = {
  "Listing files": [0, 0.05],
  "Downloading and parsing": [0.05, 0.95],
  "Building the index": [0.95, 1],
};

export function overallProgress(phase: string, done: number, total: number): number {
  const [from, to] = PHASES[phase] ?? [0, 1];
  return from + (to - from) * (total > 0 ? Math.min(1, done / total) : 0);
}

export const LOAD_STEPS = [
  { phase: "Listing files", label: "List the files", runes: 4 },
  { phase: "Downloading and parsing", label: "Download and parse", runes: 16 },
  { phase: "Building the index", label: "Build the index", runes: 4 },
] as const;

export function stepOf(fraction: number | null, phase?: string): number {
  const named = LOAD_STEPS.findIndex((s) => s.phase === phase);
  if (named >= 0) return named;
  const reached = LOAD_STEPS.findIndex((s) => (fraction ?? 0) < PHASES[s.phase][1]);
  return reached < 0 ? LOAD_STEPS.length - 1 : reached;
}

export function runesLit(fraction: number): number[] {
  return LOAD_STEPS.map((s) => {
    const [from, to] = PHASES[s.phase];
    return Math.floor(s.runes * Math.max(0, Math.min(1, (fraction - from) / (to - from))) + 1e-9);
  });
}
