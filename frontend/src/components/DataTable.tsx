"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";

export type Column<T> = {
  key: string;
  header: string;
  align?: "left" | "right";
  sortValue?: (row: T) => number | string;
  render: (row: T) => ReactNode;
};

export function DataTable<T>({
  rows,
  columns,
  empty = "Nothing to show.",
}: {
  rows: T[];
  columns: Column<T>[];
  empty?: string;
}) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    const value = column?.sortValue;
    if (!value) return rows;
    return [...rows].sort((a, b) => {
      const x = value(a);
      const y = value(b);
      return (x < y ? -1 : x > y ? 1 : 0) * sort.dir;
    });
  }, [rows, columns, sort]);

  function toggle(key: string) {
    setSort((s) => (s && s.key === key ? (s.dir === 1 ? { key, dir: -1 } : null) : { key, dir: 1 }));
  }

  if (rows.length === 0) return <p className="py-4 text-sm text-slate-500">{empty}</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800">
            {columns.map((c) => {
              const active = sort?.key === c.key;
              const arrow = active ? (sort?.dir === 1 ? " \u2191" : " \u2193") : "";
              return (
                <th
                  key={c.key}
                  className={`px-3 py-2 font-medium ${c.align === "right" ? "text-right" : ""}`}
                  aria-sort={active ? (sort?.dir === 1 ? "ascending" : "descending") : "none"}
                >
                  {c.sortValue ? (
                    <button type="button" onClick={() => toggle(c.key)} className="uppercase hover:text-slate-900 dark:hover:text-slate-100">
                      {c.header}
                      {arrow}
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i} className="border-b border-slate-100 last:border-0 dark:border-slate-800/60">
              {columns.map((c) => (
                <td key={c.key} className={`px-3 py-2 align-top ${c.align === "right" ? "text-right tabular-nums" : ""}`}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
