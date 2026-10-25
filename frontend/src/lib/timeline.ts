import { tsToMs } from "./format";
import type { OverviewPoint, TimelineRow } from "./types";

export type PreparedRow = TimelineRow & {
  isFirst: boolean;
  offsetMs: number;   // how long after the earliest onset this error first appeared
  left: number;       // percent, start of the active span
  width: number;      // percent, length of the active span
  onsetPct: number;   // percent, length of the onset bar (scaled to the largest offset)
};

export type PreparedTimeline = {
  rows: PreparedRow[];
  minMs: number;
  maxMs: number;
  spanMs: number;
  maxOffsetMs: number;
};

/** Sort by first appearance and compute positions for the onset and active-span views. */
export function prepareTimeline(rows: TimelineRow[]): PreparedTimeline {
  if (rows.length === 0) return { rows: [], minMs: 0, maxMs: 0, spanMs: 1, maxOffsetMs: 0 };

  const sorted = [...rows].sort((a, b) => tsToMs(a.first_seen) - tsToMs(b.first_seen));
  const minMs = tsToMs(sorted[0].first_seen);
  const maxMs = Math.max(...sorted.map((r) => tsToMs(r.last_seen)), minMs);
  const spanMs = Math.max(maxMs - minMs, 1);
  const maxOffsetMs = Math.max(...sorted.map((r) => tsToMs(r.first_seen) - minMs));

  return {
    minMs,
    maxMs,
    spanMs,
    maxOffsetMs,
    rows: sorted.map((r, i) => {
      const first = tsToMs(r.first_seen);
      const last = Math.max(tsToMs(r.last_seen), first);
      const offsetMs = first - minMs;
      const left = (offsetMs / spanMs) * 100;
      const width = Math.min(Math.max(((last - first) / spanMs) * 100, 0.8), 100 - left);
      const onsetPct = maxOffsetMs > 0 ? Math.max((offsetMs / maxOffsetMs) * 100, 2) : 2;
      return { ...r, isFirst: i === 0, offsetMs, left, width, onsetPct };
    }),
  };
}

/** Bucket timestamp that contains `ts` (the last bucket starting at or before it). */
export function snapToBucket(points: OverviewPoint[], ts: string): string | null {
  if (points.length === 0) return null;
  const target = tsToMs(ts);
  let found = points[0].ts;
  for (const p of points) {
    if (tsToMs(p.ts) <= target) found = p.ts;
    else break;
  }
  return found;
}

/** Chart band for a detected period: from its first bucket to the bucket holding its last second. */
export function highlightBand(
  points: OverviewPoint[],
  start: string,
  end: string,
): { x1: string; x2: string } | null {
  const x1 = snapToBucket(points, start);
  const endMs = tsToMs(end) - 1; // the period end is exclusive
  const x2 = snapToBucket(points, new Date(endMs).toISOString().slice(0, 23));
  if (!x1 || !x2) return null;
  return tsToMs(x2) >= tsToMs(x1) ? { x1, x2 } : { x1, x2: x1 };
}
