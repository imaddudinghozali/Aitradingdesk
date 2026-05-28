import type { LadderCell, QuarterLadderResponse } from "@/lib/types";

// Daye quarter colouring (1-4): accumulation / manipulation / distribution / continuation.
const QUARTER_STYLES: Record<number, string> = {
  1: "bg-slate-500/35 text-slate-100",
  2: "bg-rose-500/35 text-rose-100",
  3: "bg-emerald-500/35 text-emerald-100",
  4: "bg-sky-500/35 text-sky-100",
};
const CURRENT_STYLES: Record<number, string> = {
  1: "bg-slate-400/80 text-slate-950",
  2: "bg-rose-400/80 text-rose-950",
  3: "bg-emerald-400/80 text-emerald-950",
  4: "bg-sky-400/80 text-sky-950",
};

function span(start: string, end: string, axisStart: number, axisEnd: number) {
  const total = axisEnd - axisStart || 1;
  const s = new Date(start).getTime();
  const e = new Date(end).getTime();
  const left = Math.max(0, Math.min(1, (s - axisStart) / total));
  const right = Math.max(0, Math.min(1, (e - axisStart) / total));
  return { left: left * 100, width: Math.max(0, (right - left) * 100) };
}

function Cell({
  cell,
  axisStart,
  axisEnd,
  showLabel,
}: {
  cell: LadderCell;
  axisStart: number;
  axisEnd: number;
  showLabel: boolean;
}) {
  const { left, width } = span(cell.start_utc, cell.end_utc, axisStart, axisEnd);
  if (width <= 0) return null;
  const style = cell.is_current
    ? CURRENT_STYLES[cell.quarter_index]
    : QUARTER_STYLES[cell.quarter_index];
  return (
    <div
      title={`${cell.label} · ${cell.sub_label}`}
      style={{ left: `${left}%`, width: `${width}%` }}
      className={`absolute inset-y-0 flex items-center justify-center overflow-hidden whitespace-nowrap border-r border-shadow-bg/60 text-[10px] font-mono ${style} ${
        cell.is_current ? "z-10 font-semibold ring-1 ring-shadow-accent" : ""
      }`}
    >
      {(showLabel || cell.is_current) && width > 3 ? cell.label : ""}
    </div>
  );
}

export default function QuarterLadder({
  ladder,
}: {
  ladder: QuarterLadderResponse;
}) {
  const axisStart = new Date(ladder.window_start_utc).getTime();
  const axisEnd = new Date(ladder.window_end_utc).getTime();

  return (
    <div className="relative">
      <div className="space-y-1.5">
        {ladder.rows.map((row) => (
          <div
            key={row.cycle}
            className="relative h-9 overflow-hidden rounded border border-shadow-border bg-shadow-bg/40"
          >
            {row.cells.map((cell) => (
              <Cell
                key={cell.start_utc}
                cell={cell}
                axisStart={axisStart}
                axisEnd={axisEnd}
                showLabel={row.cells.length <= 20}
              />
            ))}
            <div className="pointer-events-none absolute left-1.5 top-1 z-20 rounded bg-shadow-bg/80 px-1.5 py-0.5 text-[10px] font-semibold text-shadow-ink">
              {row.cycle}
            </div>
          </div>
        ))}
      </div>
      <div
        className="pointer-events-none absolute inset-y-0 z-30 border-l border-dashed border-shadow-accent"
        style={{ left: `${ladder.now_ratio * 100}%` }}
      >
        <span className="absolute -top-4 -translate-x-1/2 text-[9px] font-semibold text-shadow-accent">
          now
        </span>
      </div>
    </div>
  );
}
