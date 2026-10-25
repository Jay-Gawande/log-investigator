"use client";

import { Suspense } from "react";
import { LogExplorer } from "@/components/logs/LogExplorer";
import { Skeleton } from "@/components/ui";

export default function LogsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <LogExplorer />
    </Suspense>
  );
}