"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { InvestigateForm } from "@/components/investigate/InvestigateForm";
import type { FormValues } from "@/components/investigate/InvestigateForm";
import { ResultView } from "@/components/investigate/ResultView";
import { Card, ErrorBanner, Skeleton } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { fromInputValue, inputFromTs, msToTs, tsToMs } from "@/lib/format";
import { useInvestigate, useMeta, useOverview } from "@/lib/hooks";
import { useUrlState } from "@/lib/use-url-state";

const STAGES = [
  "Detecting the anomalous period...",
  "Collecting evidence from the logs...",
  "Asking the model for a hypothesis...",
  "Verifying the hypothesis against the logs...",
];

function Progress() {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 3000);
    return () => clearInterval(id);
  }, []);
  return (
    <Card>
      <p className="mb-3 text-sm font-medium" aria-live="polite">
        {STAGES[stage]}
      </p>
      <div className="space-y-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-48" />
      </div>
    </Card>
  );
}

function InvestigateInner() {
  const { get, set } = useUrlState();
  const meta = useMeta();
  const m = meta.data;
  const mutation = useInvestigate();

  const [values, setValues] = useState<FormValues>({
    description: get("description"),
    start: get("start"),
    end: get("end"),
  });
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});

  // fill empty dates with the full data range once it is known
  const lo = m?.min_ts ?? null;
  const hi = m?.max_ts ?? null;
  useEffect(() => {
    if (lo && hi) {
      setValues((v) => ({ ...v, start: v.start || inputFromTs(lo), end: v.end || inputFromTs(hi, true) }));
    }
  }, [lo, hi]);

  // the full-range overview is only needed for the "Around peak" preset
  const fullStart = lo ? fromInputValue(inputFromTs(lo)) : "";
  const fullEnd = hi ? fromInputValue(inputFromTs(hi, true)) : "";
  const full = useOverview({ start: fullStart, end: fullEnd }, Boolean(lo && hi));

  function aroundPeak() {
    const points = full.data?.points ?? [];
    if (points.length === 0) return;
    let best = points[0];
    for (const p of points) if (p.errors + p.warns > best.errors + best.warns) best = p;
    const ms = tsToMs(best.ts);
    setValues((v) => ({
      ...v,
      start: inputFromTs(msToTs(ms - 30 * 60000)),
      end: inputFromTs(msToTs(ms + 30 * 60000), true),
    }));
  }

  function validate(v: FormValues) {
    const errs: Record<string, string> = {};
    if (!v.description.trim()) errs.description = "Describe the incident.";
    if (!v.start) errs.start = "Required.";
    if (!v.end) errs.end = "Required.";
    if (v.start && v.end && fromInputValue(v.end) <= fromInputValue(v.start)) errs.end = "End must be after start.";
    return errs;
  }

  function run() {
    const errs = validate(values);
    setClientErrors(errs);
    if (Object.keys(errs).length > 0) return;
    set({ description: values.description, start: values.start, end: values.end, run: null });
    mutation.mutate({
      description: values.description.trim(),
      start: fromInputValue(values.start),
      end: fromInputValue(values.end),
    });
  }

  // a shared link with run=1 starts the investigation by itself
  const autoRan = useRef(false);
  useEffect(() => {
    if (autoRan.current) return;
    if (get("run") === "1" && values.description && values.start && values.end) {
      autoRan.current = true;
      run();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const serverFields = mutation.error instanceof ApiError ? mutation.error.fieldErrors : {};
  const errors = { ...serverFields, ...clientErrors };
  const showBanner = mutation.isError && Object.keys(serverFields).length === 0;

  return (
    <div className="animate-fade-in space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Investigate an incident</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Describe what happened and pick a time range. The system finds the anomalous period, gathers evidence,
          proposes a root cause and checks it against the logs.
        </p>
      </div>

      <InvestigateForm
        values={values}
        onChange={(next) => {
          setValues(next);
          setClientErrors({});
        }}
        onSubmit={run}
        pending={mutation.isPending}
        errors={errors}
        presets={[
          {
            label: "Full data range",
            disabled: !lo || !hi,
            onClick: () => lo && hi && setValues((v) => ({ ...v, start: inputFromTs(lo), end: inputFromTs(hi, true) })),
          },
          { label: "Around the peak", disabled: !full.data, onClick: aroundPeak },
        ]}
      />

      {showBanner && <ErrorBanner error={mutation.error} />}
      {mutation.isPending && <Progress />}
      {mutation.data && !mutation.isPending && (
        <>
          <p className="text-xs text-slate-500">
            Re-running the same investigation can give a slightly different model answer.
          </p>
          <ResultView result={mutation.data} />
        </>
      )}
    </div>
  );
}

export default function InvestigatePage() {
  return (
    <Suspense fallback={null}>
      <InvestigateInner />
    </Suspense>
  );
}