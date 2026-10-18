const RUNES = [
  "M2 0V16M2 5 8 1M2 9 8 5",
  "M1 16V0L7 5V16",
  "M2 0V16M2 4 7 8 2 12",
  "M2 0V16M2 1 8 5M2 6 8 10",
  "M2 16V0L7 4 2 8 8 16",
  "M7 3 2 8 7 13",
  "M1 2 7 14M7 2 1 14",
  "M2 16V0L7 4 2 8",
  "M1 0V16M7 0V16M1 5 7 11",
  "M4 0V16M1 5 7 11",
  "M4 0V16",
  "M4 1 1 5 4 9M4 7 7 11 4 15",
  "M4 0V16M4 0 7 3M4 16 1 13",
  "M1 16V0L4 5 7 0V16",
  "M1 16V0L7 8M7 16V0L1 8",
  "M2 16V0L7 5",
  "M4 3 7.5 8 4 13 0.5 8Z",
  "M1 2V14L7 2V14L1 2",
  "M2 0V16M2 0 7 4 2 8 7 12 2 16",
];

const RING = [...RUNES, ...RUNES];
const STEP = 360 / RING.length;

export function RuneRing() {
  return (
    <div class="rune-ring" aria-hidden="true">
      <svg class="ring-outer" viewBox="-200 -200 400 400">
        <circle r="197" pathLength={1} class="draw" />
        {RING.map((d, i) => (
          <g key={i} class="rune" style={{ "--i": i }} transform={`rotate(${i * STEP}) translate(0 -174) scale(1.25) translate(-4 -8)`}>
            <path d={d} />
          </g>
        ))}
        <circle r="152" pathLength={1} class="draw" />
      </svg>
      <svg class="ring-inner" viewBox="-200 -200 400 400">
        {Array.from({ length: 72 }, (_, i) => (
          <line key={i} transform={`rotate(${i * 5})`} y1={-140} y2={i % 6 ? -136 : -130} />
        ))}
      </svg>
    </div>
  );
}
