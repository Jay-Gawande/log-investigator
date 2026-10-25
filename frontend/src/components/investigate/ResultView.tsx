"use client";

import { useState } from "react";
import { OverviewChart } from "@/components/charts/OverviewChart";
import { Badge, Card, EmptyState, Skeleton, Tabs } from "@/components/ui";
import { fmtTs, pct } from "@/lib/format";
import { useOverview } from "@/lib/hooks";
import type { InvestigationResult, OkResult } from "@/lib/types";
import {
  AttemptsPanel,
  RawJsonPanel,
  ReportPanel,
  ServicesPanel,
  TimelinePanel,
  TracesPanel,
  VerificationPanel,
} from "./panels";

type TabId = "timeline" | "verification" | "attempts" | "services" | "traces" | "report" | "raw";

const TABS: { id: TabId; label: string }[] = [
  { id: "timeline", label: "Timeline" },
  { id: "verification", label: "Verification" },
  { id: "attempts", label: "Attempts" },
  { id: "services", label: "Services and errors" },
  { id: "traces", label: "Traces" },
  { id: "report", label: "Report" },
  { id: "raw", label: "Raw JSON" },
];

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-sm font-medium tabular-nums">{value}</p>
    </div>
  );
}

function ResultHeader({ result }: { result: OkResult }) {
  const h = result.hypothesis;
  const v = result.verification;
  return (
    <Card className="animate-fade-in">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={v.verified ? "green" : "red"}>{v.verified ? "Verified" : "Not verified"}</Badge>
        {typeof h.confidence === "number" && <Badge tone="blue">Confidence {pct(h.confidence)}</Badge>}
        {h.source === "llm" && <Badge tone="teal">LLM</Badge>}
        {h.source === "rule_based_fallback" && <Badge tone="amber">Rule-based fallback</Badge>}
      </div>
      <p className="mt-3 text-xs uppercase tracking-wide text-slate-500">Root cause</p>
      <h2 className="text-2xl font-semibold">{h.root_cause_service}</h2>
      <p className="font-mono text-sm text-slate-600 dark:text-slate-400">{h.root_cause_error_type}</p>

      {h.propagation_path && h.propagation_path.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2" aria-label="Propagation path">
          {h.propagation_path.map((s, i) => (
            <span key={`${s}-${i}`} className="flex items-center gap-2">
              {i > 0 && <span className="text-slate-400" aria-hidden="true">&rsaquo;</span>}
              <Badge tone={i === 0 ? "teal" : "gray"}>{s}</Badge>
            </span>
          ))}
        </div>
      )}
      {h.explanation && <p className="mt-3 text-sm leading-relaxed">{h.explanation}</p>}
    </Card>
  );
}

function PeriodSection({ result }: { result: OkResult }) {
  const p = result.period;
  const overview = useOverview({
    start: result.requested_range.start,
    end: result.requested_range.end,
  });
  return (
    <Card>
      <h3 className="mb-3 font-semibold">Detected period</h3>
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Start" value={fmtTs(p.start).slice(0, 19)} />
        <Stat label="End" value={fmtTs(p.end).slice(0, 19)} />
        <Stat label="Bad lines" value={p.bad_lines_in_window.toLocaleString()} />
        <Stat label="Peak per minute" value={String(p.peak_bad_per_minute)} />
        <Stat label="Baseline per minute" value={String(p.baseline_bad_per_minute)} />
        <Stat label="Other windows" value={String(p.other_windows_found)} />
      </div>
      {overview.isPending && <Skeleton className="h-56" />}
      {overview.data && (
        <OverviewChart
          points={overview.data.points}
          bucketMinutes={overview.data.bucket_minutes}
          highlight={{ start: p.start, end: p.end }}
          height={224}
        />
      )}
    </Card>
  );
}

export function ResultView({ result }: { result: InvestigationResult }) {
  const [tab, setTab] = useState<TabId>("timeline");

  if (result.status === "no_anomaly_found") {
    return (
      <EmptyState title="No anomalous period found">
        <p>
          Nothing in {fmtTs(result.requested_range.start)} to {fmtTs(result.requested_range.end)} stood out from the
          baseline. Try a wider range, or check that logs exist for these dates on the Dashboard.
        </p>
      </EmptyState>
    );
  }

  return (
    <div className="space-y-4">
      <ResultHeader result={result} />
      <PeriodSection result={result} />
      <Card className="animate-fade-in">
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
        <div className="pt-4" role="tabpanel" aria-labelledby={`tab-${tab}`}>
          {tab === "timeline" && <TimelinePanel result={result} />}
          {tab === "verification" && <VerificationPanel result={result} />}
          {tab === "attempts" && <AttemptsPanel result={result} />}
          {tab === "services" && <ServicesPanel result={result} />}
          {tab === "traces" && <TracesPanel result={result} />}
          {tab === "report" && <ReportPanel result={result} />}
          {tab === "raw" && <RawJsonPanel result={result} />}
        </div>
      </Card>
    </div>
  );
}
