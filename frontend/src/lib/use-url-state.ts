"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

type Updates = Record<string, string | number | null | undefined>;

/** Read and update the page's query string. Empty values remove the key. */
export function useUrlState() {
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const sp = useSearchParams();

  const get = (key: string, fallback = "") => sp.get(key) ?? fallback;

  const set = useCallback(
    (updates: Updates) => {
      const next = new URLSearchParams(sp.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === undefined || value === "") next.delete(key);
        else next.set(key, String(value));
      }
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [router, pathname, sp],
  );

  return { get, set };
}
