"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import {
  getHealth,
  getLogs,
  getMeta,
  getOverview,
  getTrace,
  investigate,
  renderReport,
  type LogsParams,
  type OverviewParams,
} from "./api";
import type { InvestigationResult } from "./types";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 15000,
    retry: false,
  });
}

export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: getMeta });
}

export function useOverview(params: OverviewParams, enabled = true) {
  return useQuery({
    queryKey: ["overview", params],
    queryFn: () => getOverview(params),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useLogs(params: LogsParams, enabled = true) {
  return useQuery({
    queryKey: ["logs", params],
    queryFn: () => getLogs(params),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useTrace(id: string) {
  return useQuery({ queryKey: ["trace", id], queryFn: () => getTrace(id) });
}

export function useInvestigate() {
  return useMutation({ mutationFn: investigate });
}

/** Markdown for a result that is already on screen. Deterministic, so cached for good. */
export function useRenderReport(result: InvestigationResult) {
  const signature = JSON.stringify([
    result.incident,
    result.requested_range,
    result.status === "ok" ? [result.hypothesis, result.verification, result.attempts.length] : null,
  ]);
  return useQuery({
    queryKey: ["report", signature],
    queryFn: () => renderReport(result),
    staleTime: Infinity,
  });
}
