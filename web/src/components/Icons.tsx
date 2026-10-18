export const ICONS = {
  repo: "M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5M5 4.5v15A1.5 1.5 0 0 0 6.5 21H19v-3M9 7h6",
  report: "M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5ZM14 3v5h5M8.5 13h7M8.5 17h5",
  vector: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3ZM18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z",
  lock: "M6 11h12v10H6ZM8.5 11V7.5a3.5 3.5 0 0 1 7 0V11M12 15v2.5",
  download: "M12 3v12M7 10l5 5 5-5M4 20h16",
  code: "M8 7l-5 5 5 5M16 7l5 5-5 5M13.5 4l-3 16",
  search: "M10.5 4.5a6 6 0 1 0 0 12 6 6 0 0 0 0-12ZM15 15l5 5",
  rank: "M4 20h16M6.5 16v-4M12 16V8M17.5 16V5",
  layers: "M12 3l9 5-9 5-9-5 9-5ZM3 13l9 5 9-5",
  chip: "M7 7h10v10H7ZM10 10h4v4h-4ZM9.5 3v4M14.5 3v4M9.5 17v4M14.5 17v4M3 9.5h4M3 14.5h4M17 9.5h4M17 14.5h4",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 7.5V12l3 2",
  issue: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 10.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z",
  check: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM8 12.5l2.7 2.7L16 9.8",
} as const;

export type IconName = keyof typeof ICONS;

export const Icon = ({ name }: { name: IconName }) => (
  <svg class="line-icon" viewBox="0 0 24 24" aria-hidden="true"><path d={ICONS[name]} /></svg>
);
