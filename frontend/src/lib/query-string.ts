export type Params = Record<string, string | number | boolean | null | undefined>;

/** Build "?a=1&b=2", skipping empty values. Returns "" when nothing is left. */
export function buildQuery(params: Params): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "" || value === false) continue;
    sp.set(key, String(value));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}
