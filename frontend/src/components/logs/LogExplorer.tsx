"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Skeleton, inputCls } from "@/components/ui";
import { fmtTs, fromInputValue, inputFromTs, levelTone, serviceColor } from "@/lib/format";
import { useLogs, useMeta } from "@/lib/hooks";
import { useUrlState } from "@/lib/use-url-state";

const PAGE_SIZES = [50, 100, 200];

/** Text input whose value is pushed to the URL after a short pause, without fighting the user's typing. */
function useDebouncedParam(value: string, push: (v: string) => void) {
  const [local, setLocal] = useState(value);
  const lastPushed = useRef(value);

  useEffect(() => {
    if (value !== lastPushed.current) {
      lastPushed.current = value;
      setLocal(value);
    }
  }, [value]);

  useEffect(() => {
    if (local === lastPushed.current) return;
    const id = setTimeout(() => {
      lastPushed.current = local;
      push(local);
    }, 400);
    return () => clearTimeout(id);
  }, [local, push]);

  return [local, setLocal] as const;
}

export function LogExplorer() {
  const { get, set } = useUrlState();
  const meta = useMeta();
  const m = meta.data;

  const start = get("start");
  const end = get("end");
  const service = get("service");
  const level = get("level");
  const errorType = get("error_type");
  const requestId = get("request_id");
  const q = get("q");
  const order = get("order", "asc") === "desc" ? "desc" : "asc";
  const limit = PAGE_SIZES.includes(Number(get("limit"))) ? Number(get("limit")) : 100;
  const offset = Math.max(Number(get("offset", "0")) || 0, 0);

  // default the time range to everything in the database
  useEffect(() => {
    if (!start && !end && m?.min_ts && m.max_ts) {
      set({ start: inputFromTs(m.min_ts), end: inputFromTs(m.max_ts, true) });
    }
  }, [start, end, m, set]);

  const pushQ = useCallback((v: string) => set({ q: v, offset: null }), [set]);
  const pushRid = useCallback((v: string) => set({ request_id: v.trim(), offset: null }), [set]);
  const [qLocal, setQLocal] = useDebouncedParam(q, pushQ);
  const [ridLocal, setRidLocal] = useDebouncedParam(requestId, pushRid);

  const ready = Boolean(start && end && end > start);
  const logs = useLogs(
    {
      start: fromInputValue(start),
      end: fromInputValue(end),
      service: service || undefined,
      level: level || undefined,
      error_type: errorType || undefined,
      request_id: requestId || undefined,
      q: q || undefined,
      order,
      limit,
      offset,
    },
    ready,
  );

  const [expanded, setExpanded] = useState<number | null>(null);
  const items = logs.data?.items ?? [];

  function clearFilters() {
    setQLocal("");
    setRidLocal("");
    set({ service: null, level: null, error_type: null, request_id: null, q: null, offset: null });
  }

  const select = (key: string, value: string, options: string[], label: string, id: string) => (
    <Field label={label} htmlFor={id}>
      <select id={id} className={inputCls} value={value} onChange={(e) => set({ [key]: e.target.value, offset: null })}>
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </Field>
  );

  return (
    <div className="animate-fade-in space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Log explorer</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">Filter raw log lines. Filters are kept in the URL, so views can be shared.</p>
      </div>

      <Card>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="From" htmlFor="log-from">
            <input id="log-from" type="datetime-local" className={inputCls} value={start} onChange={(e) => set({ start: e.target.value, offset: null })} />
          </Field>
          <Field label="To" htmlFor="log-to" error={start && end && end <= start ? "End must be after start" : undefined}>
            <input id="log-to" type="datetime-local" className={inputCls} value={end} onChange={(e) => set({ end: e.target.value, offset: null })} />
          </Field>
          {select("service", service, m?.services ?? [], "Service", "f-service")}
          {select("level", level, m?.levels ?? [], "Level", "f-level")}
          {select("error_type", errorType, m?.error_types ?? [], "Error type", "f-error")}
          <Field label="Request id" htmlFor="f-rid">
            <input id="f-rid" className={`${inputCls} font-mono`} placeholder="UUID" value={ridLocal} onChange={(e) => setRidLocal(e.target.value)} />
          </Field>
          <Field label="Message contains" htmlFor="f-q">
            <input id="f-q" className={inputCls} placeholder="text to find" value={qLocal} onChange={(e) => setQLocal(e.target.value)} />
          </Field>
          <Field label="Order" htmlFor="f-order">
            <select id="f-order" className={inputCls} value={order} onChange={(e) => set({ order: e.target.value, offset: null })}>
              <option value="asc">Oldest first</option>
              <option value="desc">Newest first</option>
            </select>
          </Field>
        </div>
        <div className="mt-3">
          <Button variant="ghost" onClick={clearFilters}>
            Clear filters
          </Button>
        </div>
      </Card>

      {logs.isError && <ErrorBanner error={logs.error} />}
      {ready && logs.isPending && <Skeleton className="h-64" />}
      {!ready && !meta.isPending && <EmptyState title="Choose a valid time range" />}

      {logs.data && (
        <Card className={logs.isPlaceholderData ? "opacity-60 transition-opacity" : "transition-opacity"}>
          {items.length === 0 ? (
            <EmptyState title="No log lines match these filters" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800">
                    <th className="px-3 py-2 font-medium">Time</th>
                    <th className="px-3 py-2 font-medium">Level</th>
                    <th className="px-3 py-2 font-medium">Service</th>
                    <th className="px-3 py-2 font-medium">Error type</th>
                    <th className="px-3 py-2 font-medium">Message</th>
                    <th className="px-3 py-2 font-medium">Request</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => {
                    const open = expanded === row.id;
                    return (
                      <Fragment key={row.id}>
                        <tr
                          className="cursor-pointer border-b border-slate-100 transition hover:bg-slate-50 dark:border-slate-800/60 dark:hover:bg-slate-800/50"
                          onClick={() => setExpanded(open ? null : row.id)}
                          aria-expanded={open}
                        >
                          <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{fmtTs(row.ts)}</td>
                          <td className="px-3 py-2">
                            <Badge tone={levelTone(row.level)}>{row.level}</Badge>
                          </td>
                          <td className="whitespace-nowrap px-3 py-2">
                            <span style={{ color: serviceColor(row.service) }} className="font-medium">
                              {row.service}
                            </span>
                          </td>
                          <td className="px-3 py-2 font-mono text-xs">{row.error_type ?? "-"}</td>
                          <td className="max-w-md truncate px-3 py-2">{row.message}</td>
                          <td className="px-3 py-2">
                            <Link
                              href={`/requests/${row.request_id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="font-mono text-xs text-teal-700 hover:underline dark:text-teal-400"
                            >
                              {row.request_id.slice(0, 8)}
                            </Link>
                          </td>
                        </tr>
                        {open && (
                          <tr className="border-b border-slate-100 bg-slate-50 dark:border-slate-800/60 dark:bg-slate-800/30">
                            <td colSpan={6} className="px-3 py-3 text-sm">
                              <p className="whitespace-pre-wrap break-words">{row.message}</p>
                              <p className="mt-2 font-mono text-xs text-slate-500">
                                id {row.id} · request {row.request_id}
                                {row.latency_ms != null && <> · latency {row.latency_ms} ms</>}
                              </p>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs text-slate-500">
              {items.length > 0 ? `Rows ${offset + 1} to ${offset + items.length}` : "No rows"}
            </span>
            <div className="flex items-center gap-2">
              <label htmlFor="page-size" className="text-xs text-slate-500">
                Per page
              </label>
              <select
                id="page-size"
                className={`${inputCls} !w-auto`}
                value={limit}
                onChange={(e) => set({ limit: e.target.value, offset: null })}
              >
                {PAGE_SIZES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <Button variant="secondary" disabled={offset === 0} onClick={() => set({ offset: Math.max(offset - limit, 0) || null })}>
                Previous
              </Button>
              <Button variant="secondary" disabled={!logs.data.has_more} onClick={() => set({ offset: offset + limit })}>
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
