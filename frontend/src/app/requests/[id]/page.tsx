"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge, Card, CopyButton, EmptyState, ErrorBanner, Skeleton } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { fmtClock, fmtDuration, fmtOffset, fmtTs, levelTone, serviceColor } from "@/lib/format";
import { useTrace } from "@/lib/hooks";

export default function RequestTracePage() {
  const params = useParams<{ id: string }>();
  const id = String(params?.id ?? "");
  const trace = useTrace(id);

  if (trace.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-72" />
      </div>
    );
  }

  if (trace.isError) {
    const notFound = trace.error instanceof ApiError && trace.error.status === 404;
    return (
      <div className="space-y-4">
        {notFound ? (
          <EmptyState title="No request with this id">
            <p className="font-mono text-xs">{id}</p>
          </EmptyState>
        ) : (
          <ErrorBanner error={trace.error} />
        )}
        <Link href="/logs" className="text-sm text-teal-700 hover:underline dark:text-teal-400">
          Back to the log explorer
        </Link>
      </div>
    );
  }

  const t = trace.data;
  return (
    <div className="animate-fade-in space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Request trace</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">Every log line of one request, across services.</p>
      </div>

      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <span className="break-all font-mono text-sm">{t.request_id}</span>
          <CopyButton text={t.request_id} />
          <Badge tone={t.has_errors ? "red" : "green"}>{t.has_errors ? "Has errors" : "No errors"}</Badge>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Duration</dt>
            <dd className="text-sm font-medium">{fmtDuration(t.duration_ms)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Started</dt>
            <dd className="text-sm font-medium">{fmtTs(t.start)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Events</dt>
            <dd className="text-sm font-medium">{t.events.length}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Services</dt>
            <dd className="mt-1 flex flex-wrap gap-1">
              {t.services.map((s) => (
                <span key={s} className="flex items-center gap-1 text-xs">
                  <span className="h-2 w-2 rounded-full" style={{ background: serviceColor(s) }} />
                  {s}
                </span>
              ))}
            </dd>
          </div>
        </dl>
      </Card>

      <Card>
        <ol className="relative ml-3 border-l border-slate-300 dark:border-slate-700">
          {t.events.map((e) => (
            <li key={e.id} className="relative mb-5 ml-6 last:mb-0">
              <span
                className="absolute -left-[1.95rem] top-1.5 h-3 w-3 rounded-full ring-4 ring-white dark:ring-slate-900"
                style={{ background: serviceColor(e.service) }}
                aria-hidden="true"
              />
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-slate-500">{fmtOffset(e.offset_ms) === "first" ? "+0 ms" : fmtOffset(e.offset_ms)}</span>
                <span className="font-medium" style={{ color: serviceColor(e.service) }}>
                  {e.service}
                </span>
                <Badge tone={levelTone(e.level)}>{e.level}</Badge>
                {e.error_type && <span className="font-mono text-xs">{e.error_type}</span>}
                {e.latency_ms != null && <span className="text-xs text-slate-500">{e.latency_ms} ms</span>}
              </div>
              <p className="mt-1 text-sm">{e.message}</p>
              <p className="font-mono text-xs text-slate-400">{fmtClock(e.ts)}</p>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}