"use client";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DataTable } from "@/components/DataTable";
import type { Column } from "@/components/DataTable";
import { Badge, Button, CopyButton, ErrorBanner, Skeleton } from "@/components/ui";
import {
  fmtClock,
  fmtDuration,
  fmtOffset,
  fmtTs,
  inputFromTs,
  levelBarClass,
  levelTone,
  pct,
  serviceColor,
} from "@/lib/format";
import { useRenderReport } from "@/lib/hooks";
import { buildQuery } from "@/lib/query-string";
import { prepareTimeline } from "@/lib/timeline";
import type {
  Attempt,
  ErrorGroup,
  Hypothesis,
  InvestigationResult,
  OkResult,
  ServiceRow,
  Verification,
} from "@/lib/types";

const GRID = "grid grid-cols-[minmax(0,13rem)_minmax(0,1fr)_5.5rem] items-center gap-3";

function ServiceLabel({ service, sub }: { service: string; sub: string }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: serviceColor(service) }} />
        <span className="truncate text-sm font-medium">{service}</span>
      </div>
      <div className="truncate pl-4 font-mono text-xs text-slate-500">{sub}</div>
    </div>
  );
}

// ---------------------------------------------------------------- timeline

export function TimelinePanel({ result }: { result: OkResult }) {
  const t = prepareTimeline(result.timeline);
  if (t.rows.length === 0) return <p className="text-sm text-slate-500">No errors recorded in the window.</p>;

  return (
    <div className="space-y-8">
      <section>
        <h3 className="font-semibold">Onset order</h3>
        <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
          When each error first appeared, relative to the earliest one. The root cause usually starts first and
          the others follow as symptoms.
        </p>
        <div className="space-y-2">
          {t.rows.map((r) => (
            <div key={`${r.service}|${r.level}|${r.error_type}`} className={GRID}>
              <ServiceLabel service={r.service} sub={`${r.error_type ?? "-"} · ${r.level}`} />
              <div className="h-4 rounded bg-slate-100 dark:bg-slate-800">
                <div
                  className={`h-4 rounded ${r.isFirst ? "bg-teal-600" : levelBarClass(r.level)} transition-all`}
                  style={{ width: `${r.onsetPct}%` }}
                />
              </div>
              <div className="text-right text-xs tabular-nums">
                {r.isFirst ? <Badge tone="teal">first</Badge> : fmtOffset(r.offsetMs)}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="font-semibold">Active span</h3>
        <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
          From first to last occurrence on a shared time axis. Total span: {fmtDuration(t.spanMs)}.
        </p>
        <div className="space-y-2">
          {t.rows.map((r) => (
            <div
              key={`${r.service}|${r.level}|${r.error_type}`}
              className={GRID}
              title={`${r.service} ${r.error_type ?? ""}\n${fmtTs(r.first_seen)} to ${fmtTs(r.last_seen)}\n${r.occurrences} occurrences`}
            >
              <ServiceLabel service={r.service} sub={`${r.error_type ?? "-"} · ${r.level}`} />
              <div className="relative h-4 rounded bg-slate-100 dark:bg-slate-800">
                <div
                  className={`absolute top-0 h-4 rounded ${levelBarClass(r.level)}`}
                  style={{ left: `${r.left}%`, width: `${r.width}%` }}
                />
              </div>
              <div className="text-right text-xs tabular-nums text-slate-500">{r.occurrences.toLocaleString()} lines</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- verification

function CheckRow({ label, ok, detail }: { label: string; ok: boolean | undefined; detail?: string }) {
  const tone = ok === undefined ? "gray" : ok ? "green" : "red";
  const text = ok === undefined ? "Not evaluated" : ok ? "Pass" : "Fail";
  return (
    <li className="flex items-start justify-between gap-4 border-b border-slate-100 py-3 last:border-0 dark:border-slate-800">
      <div>
        <p className="text-sm font-medium">{label}</p>
        {detail && <p className="text-xs text-slate-500">{detail}</p>}
      </div>
      <Badge tone={tone}>{text}</Badge>
    </li>
  );
}

export function VerificationChecks({ v }: { v: Partial<Verification> }) {
  return (
    <ul>
      <CheckRow label="The claimed error occurs in the window" ok={v.error_exists_in_window} />
      <CheckRow label="It appeared first among the significant errors" ok={v.appeared_first} />
      <CheckRow
        label="It is present in at least 50% of failing requests"
        ok={v.coverage_ok}
        detail={v.coverage_of_failing_requests !== undefined ? `Observed ${pct(v.coverage_of_failing_requests)}` : undefined}
      />
    </ul>
  );
}

export function VerificationPanel({ result }: { result: OkResult }) {
  const v = result.verification;
  return (
    <div>
      <div className="mb-2 flex items-center gap-3">
        <h3 className="font-semibold">Verdict</h3>
        <Badge tone={v.verified ? "green" : "red"}>{v.verified ? "Verified" : "Not verified"}</Badge>
      </div>
      <p className="mb-2 text-sm text-slate-600 dark:text-slate-400">
        The hypothesis is tested against the raw logs. All three checks must pass.
      </p>
      {v.reason && <p className="mb-2 text-sm">{v.reason}</p>}
      <VerificationChecks v={v} />
    </div>
  );
}

// ---------------------------------------------------------------- attempts

function AttemptCard({ attempt, isLast }: { attempt: Attempt; isLast: boolean }) {
  const hyp = (attempt.hypothesis ?? {}) as Partial<Hypothesis>;
  const ver = (attempt.verification ?? {}) as Partial<Verification>;
  const label = attempt.attempt === "fallback" ? "Fallback (rule-based)" : `Attempt ${attempt.attempt} (LLM)`;
  const outcome = attempt.error
    ? { tone: "red" as const, text: "Error" }
    : ver.verified
      ? { tone: "green" as const, text: "Verified" }
      : { tone: "amber" as const, text: "Rejected" };

  return (
    <details open={isLast} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
      <summary className="flex cursor-pointer items-center gap-3">
        <span className="font-medium">{label}</span>
        <Badge tone={outcome.tone}>{outcome.text}</Badge>
        {hyp.root_cause_service && (
          <span className="truncate font-mono text-xs text-slate-500">
            {hyp.root_cause_service} / {hyp.root_cause_error_type}
          </span>
        )}
      </summary>
      <div className="mt-3 space-y-3 text-sm">
        {attempt.error && (
          <pre className="overflow-x-auto rounded bg-red-50 p-2 font-mono text-xs text-red-800 dark:bg-red-950 dark:text-red-200">
            {attempt.error}
          </pre>
        )}
        {hyp.root_cause_service && (
          <div>
            <p>
              <span className="font-medium">Proposed:</span> {hyp.root_cause_service},{" "}
              <span className="font-mono">{hyp.root_cause_error_type}</span>
              {typeof hyp.confidence === "number" && <> (confidence {pct(hyp.confidence)})</>}
            </p>
            {hyp.explanation && <p className="mt-1 text-slate-600 dark:text-slate-400">{hyp.explanation}</p>}
          </div>
        )}
        {attempt.verification && <VerificationChecks v={ver} />}
        {outcome.text === "Rejected" && !isLast && (
          <p className="text-xs text-slate-500">
            This verdict was sent back to the model as feedback for the next attempt.
          </p>
        )}
      </div>
    </details>
  );
}

export function AttemptsPanel({ result }: { result: OkResult }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600 dark:text-slate-400">
        The model proposes a cause, the logs are used to check it, and a rejected proposal is retried once with
        the failure details. If that also fails, a rule-based answer is used.
      </p>
      {result.attempts.map((a, i) => (
        <AttemptCard key={String(a.attempt) + i} attempt={a} isLast={i === result.attempts.length - 1} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- services and error groups

export function ServicesPanel({ result }: { result: OkResult }) {
  const serviceCols: Column<ServiceRow>[] = [
    {
      key: "service",
      header: "Service",
      sortValue: (r) => r.service,
      render: (r) => <ServiceLabel service={r.service} sub="" />,
    },
    { key: "errors", header: "Errors", align: "right", sortValue: (r) => r.errors, render: (r) => r.errors.toLocaleString() },
    { key: "warns", header: "Warnings", align: "right", sortValue: (r) => r.warns, render: (r) => r.warns.toLocaleString() },
    { key: "total", header: "Lines", align: "right", sortValue: (r) => r.total_lines, render: (r) => r.total_lines.toLocaleString() },
    {
      key: "first",
      header: "First error",
      sortValue: (r) => r.first_error ?? "~",
      render: (r) => <span className="font-mono text-xs">{fmtClock(r.first_error)}</span>,
    },
    {
      key: "latency",
      header: "Avg latency",
      align: "right",
      sortValue: (r) => r.avg_latency_ms ?? -1,
      render: (r) => (r.avg_latency_ms == null ? "-" : `${Math.round(r.avg_latency_ms)} ms`),
    },
  ];

  const logsHref = (g: ErrorGroup) =>
    `/logs${buildQuery({
      service: g.service,
      level: g.level,
      error_type: g.error_type ?? undefined,
      start: inputFromTs(result.period.start),
      end: inputFromTs(result.period.end, true),
    })}`;

  const groupCols: Column<ErrorGroup>[] = [
    { key: "service", header: "Service", sortValue: (g) => g.service, render: (g) => g.service },
    { key: "level", header: "Level", render: (g) => <Badge tone={levelTone(g.level)}>{g.level}</Badge> },
    { key: "type", header: "Error type", sortValue: (g) => g.error_type ?? "", render: (g) => <span className="font-mono text-xs">{g.error_type ?? "-"}</span> },
    { key: "pattern", header: "Message pattern", render: (g) => <span className="text-slate-600 dark:text-slate-400">{g.pattern}</span> },
    { key: "count", header: "Count", align: "right", sortValue: (g) => g.count, render: (g) => g.count.toLocaleString() },
    { key: "first", header: "First seen", sortValue: (g) => g.first_seen, render: (g) => <span className="font-mono text-xs">{fmtClock(g.first_seen)}</span> },
    {
      key: "logs",
      header: "",
      render: (g) => (
        <Link href={logsHref(g)} className="text-teal-700 hover:underline dark:text-teal-400">
          View logs
        </Link>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-1 font-semibold">Services in the window</h3>
        <DataTable rows={result.services} columns={serviceCols} />
      </section>
      <section>
        <h3 className="mb-1 font-semibold">Error groups</h3>
        <DataTable rows={result.error_groups} columns={groupCols} empty="No error groups." />
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- traces

export function TracesPanel({ result }: { result: OkResult }) {
  const { common_paths, sample_traces, requests_sampled } = result.traces;
  const max = Math.max(...common_paths.map((p) => p.count), 1);

  return (
    <div className="space-y-6">
      <section>
        <h3 className="font-semibold">Most common failing paths</h3>
        <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
          Sampled {requests_sampled.toLocaleString()} failing requests and grouped them by the sequence of services
          and levels they went through.
        </p>
        {common_paths.length === 0 && <p className="text-sm text-slate-500">No failing requests sampled.</p>}
        <div className="space-y-3">
          {common_paths.map((p) => (
            <div key={p.path}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="break-all font-mono text-xs">{p.path}</span>
                <span className="shrink-0 tabular-nums text-slate-500">{p.count}</span>
              </div>
              <div className="mt-1 h-2 rounded bg-slate-100 dark:bg-slate-800">
                <div className="h-2 rounded bg-teal-600" style={{ width: `${(p.count / max) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      </section>

      {sample_traces.length > 0 && (
        <section>
          <h3 className="mb-2 font-semibold">Example traces</h3>
          <div className="space-y-3">
            {sample_traces.map((t) => (
              <div key={t.request_id} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                <Link href={`/requests/${t.request_id}`} className="font-mono text-xs text-teal-700 hover:underline dark:text-teal-400">
                  {t.request_id}
                </Link>
                <ul className="mt-2 space-y-1 text-sm">
                  {t.events.map((e, i) => (
                    <li key={i} className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-slate-500">{fmtClock(e.ts)}</span>
                      <span style={{ color: serviceColor(e.service) }} className="font-medium">
                        {e.service}
                      </span>
                      <Badge tone={levelTone(e.level)}>{e.level}</Badge>
                      <span className="text-slate-600 dark:text-slate-400">{e.message}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- report and raw JSON

function downloadText(text: string, filename: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ReportPanel({ result }: { result: InvestigationResult }) {
  const q = useRenderReport(result);
  if (q.isPending) return <Skeleton className="h-64" />;
  if (q.isError) return <ErrorBanner error={q.error} />;
  return (
    <div>
      <div className="mb-3 flex gap-2">
        <CopyButton text={q.data} label="Copy Markdown" />
        <Button variant="secondary" onClick={() => downloadText(q.data, "incident-report.md")}>
          Download .md
        </Button>
      </div>
      <article className="md rounded-lg border border-slate-200 p-4 dark:border-slate-800">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{q.data}</ReactMarkdown>
      </article>
    </div>
  );
}

export function RawJsonPanel({ result }: { result: InvestigationResult }) {
  const text = JSON.stringify(result, null, 2);
  return (
    <div>
      <div className="mb-3">
        <CopyButton text={text} label="Copy JSON" />
      </div>
      <pre className="max-h-[32rem] overflow-auto rounded-lg bg-slate-100 p-3 font-mono text-xs dark:bg-slate-800">
        {text}
      </pre>
    </div>
  );
}
