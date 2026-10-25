"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtAxis, fmtTs, msToTs, tsToMs } from "@/lib/format";
import { highlightBand } from "@/lib/timeline";
import type { OverviewPoint } from "@/lib/types";
import { EmptyState } from "@/components/ui";

type Chart2Event = { activeLabel?: string } | null;

export function OverviewChart({
  points,
  bucketMinutes,
  highlight,
  onSelect,
  height = 256,
}: {
  points: OverviewPoint[];
  bucketMinutes: number;
  /** Detected period to shade on the chart. */
  highlight?: { start: string; end: string } | null;
  /** Called with a time range when the user drags across the chart. */
  onSelect?: (range: { start: string; end: string }) => void;
  height?: number;
}) {
  const [drag, setDrag] = useState<{ a: string; b: string } | null>(null);

  const multiDay = useMemo(
    () => points.length > 1 && points[0].ts.slice(0, 10) !== points[points.length - 1].ts.slice(0, 10),
    [points],
  );
  const band = useMemo(
    () => (highlight ? highlightBand(points, highlight.start, highlight.end) : null),
    [points, highlight],
  );

  if (points.length === 0) return <EmptyState title="No data in this range" />;

  const interactive = Boolean(onSelect);

  function down(e: Chart2Event) {
    if (e?.activeLabel) setDrag({ a: String(e.activeLabel), b: String(e.activeLabel) });
  }
  function move(e: Chart2Event) {
    if (drag && e?.activeLabel) setDrag({ a: drag.a, b: String(e.activeLabel) });
  }
  function up() {
    if (drag && drag.a !== drag.b && onSelect) {
      const lo = Math.min(tsToMs(drag.a), tsToMs(drag.b));
      const hi = Math.max(tsToMs(drag.a), tsToMs(drag.b));
      onSelect({ start: msToTs(lo), end: msToTs(hi + bucketMinutes * 60000) });
    }
    setDrag(null);
  }

  return (
    <div className="select-none text-slate-500 dark:text-slate-400" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={points}
          margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
          barCategoryGap={0}
          onMouseDown={interactive ? down : undefined}
          onMouseMove={interactive ? move : undefined}
          onMouseUp={interactive ? up : undefined}
          onMouseLeave={interactive ? () => setDrag(null) : undefined}
        >
          <CartesianGrid stroke="currentColor" strokeOpacity={0.15} vertical={false} />
          <XAxis
            dataKey="ts"
            tick={{ fill: "currentColor", fontSize: 11 }}
            tickFormatter={(v: string) => fmtAxis(v, multiDay)}
            minTickGap={40}
            interval="preserveStartEnd"
          />
          <YAxis tick={{ fill: "currentColor", fontSize: 11 }} allowDecimals={false} width={36} />
          <Tooltip
            labelFormatter={(label) => fmtTs(String(label))}
            contentStyle={{ borderRadius: 8, fontSize: 12 }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="errors" name="Errors" stackId="a" fill="#dc2626" />
          <Bar dataKey="warns" name="Warnings" stackId="a" fill="#f59e0b" />
          {band && (
            <ReferenceArea x1={band.x1} x2={band.x2} fill="#0d9488" fillOpacity={0.15} stroke="#0d9488" strokeOpacity={0.6} />
          )}
          {drag && <ReferenceArea x1={drag.a} x2={drag.b} fill="#2563eb" fillOpacity={0.2} />}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
