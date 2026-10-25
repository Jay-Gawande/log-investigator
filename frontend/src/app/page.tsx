"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { OverviewChart } from "@/components/charts/OverviewChart";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Skeleton, inputCls } from "@/components/ui";
import { fmtNumber, fmtTs, fromInputValue, inputFromTs } from "@/lib/format";
import { useMeta, useOverview } from "@/lib/hooks";
import { buildQuery } from "@/lib/query-string";

const BUCKETS = [
  { value: 0, label: "Auto" },
  { value: 1, label: "1 min" },
  { value: 5, label: "5 min" },
  { value: 15, label: "15 min" },
  { value: 60, label: "60 min" },
];

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </Card>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const meta = useMeta();
  const m = meta.data;

  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [service, setService] = useState("");
  const [bucket, setBucket] = useState(0);
  const [zoomed, setZoomed] = useState(false);

  const fullStart = m?.min_ts ? inputFromTs(m.min_ts) : "";
  const fullEnd = m?.max_ts ? inputFromTs(m.max_ts, true) : "";

  // default the range to everything in the database, once the meta info arrives
  useEffect(() => {
    if (fullStart && fullEnd && !start && !end) {
      setStart(fullStart);
      setEnd(fullEnd);
    }
  }, [fullStart, fullEnd, start, end]);

  const rangeValid = Boolean(start && end && end > start);
  const overview = useOverview(
    {
      start: fromInputValue(start),
      end: fromInputValue(end),
      bucket_minutes: bucket || undefined,
      service: service || undefined,
    },
    rangeValid,
  );

  function resetZoom() {
    setStart(fullStart);
    setEnd(fullEnd);
    setZoomed(false);
  }

  if (meta.isPending) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <Skeleton className="h-72" />
      </div>
    );
  }
  if (meta.isError) return <ErrorBanner error={meta.error} />;

  if (!m || m.total_rows === 0) {
    return (
      <EmptyState title="No logs in the database yet">
        <p>Generate sample data, then reload:</p>
        <pre className="mt-2 inline-block rounded bg-slate-100 px-3 py-2 text-left font-mono text-xs dark:bg-slate-800">
          uv run python -m app.generator --n 20000 --kind db_failure --truncate
        </pre>
      </EmptyState>
    );
  }

  return (
    <div className="animate-fade-in space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Errors and warnings over time. Drag across the chart to zoom, then investigate that period.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Log lines" value={fmtNumber(m.total_rows)} />
        <Stat label="First log" value={fmtTs(m.min_ts).slice(0, 19)} />
        <Stat label="Last log" value={fmtTs(m.max_ts).slice(0, 19)} />
        <Card>
          <p className="text-xs uppercase tracking-wide text-slate-500">Services</p>
          <div className="mt-2 flex flex-wrap gap-1">
            {m.services.map((s) => (
              <Badge key={s} tone="teal">
                {s}
              </Badge>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="From" htmlFor="from">
            <input id="from" type="datetime-local" className={inputCls} value={start} onChange={(e) => setStart(e.target.value)} />
          </Field>
          <Field label="To" htmlFor="to" error={start && end && end <= start ? "End must be after start" : undefined}>
            <input id="to" type="datetime-local" className={inputCls} value={end} onChange={(e) => setEnd(e.target.value)} />
          </Field>
          <Field label="Service" htmlFor="service">
            <select id="service" className={inputCls} value={service} onChange={(e) => setService(e.target.value)}>
              <option value="">All services</option>
              {m.services.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Bucket size" htmlFor="bucket">
            <select id="bucket" className={inputCls} value={bucket} onChange={(e) => setBucket(Number(e.target.value))}>
              {BUCKETS.map((b) => (
                <option key={b.value} value={b.value}>
                  {b.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        {overview.isError && <ErrorBanner error={overview.error} />}
        {overview.isPending && rangeValid && <Skeleton className="h-64" />}
        {overview.data && (
          <OverviewChart
            points={overview.data.points}
            bucketMinutes={overview.data.bucket_minutes}
            onSelect={(r) => {
              setStart(inputFromTs(r.start));
              setEnd(inputFromTs(r.end, true));
              setZoomed(true);
            }}
          />
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button
            disabled={!rangeValid}
            onClick={() => router.push(`/investigate${buildQuery({ start, end })}`)}
          >
            Investigate this period
          </Button>
          <Button
            variant="secondary"
            disabled={!rangeValid}
            onClick={() => router.push(`/logs${buildQuery({ start, end, service })}`)}
          >
            View logs
          </Button>
          {zoomed && (
            <Button variant="ghost" onClick={resetZoom}>
              Reset zoom
            </Button>
          )}
          {overview.data && (
            <span className="text-xs text-slate-500">{overview.data.bucket_minutes}-minute buckets</span>
          )}
        </div>
      </Card>
    </div>
  );
}
