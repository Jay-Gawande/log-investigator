import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getLogs, getMeta, getOverview, investigate, parseDetail, renderReport } from "@/lib/api";

function stubFetch(impl: (url: string, init?: RequestInit) => Promise<Response> | Response) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => impl(url, init));
  vi.stubGlobal("fetch", fn);
  return fn;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("parseDetail", () => {
  it("passes a string detail through", () => {
    expect(parseDetail("end must be after start")).toEqual({ message: "end must be after start", fields: {} });
  });

  it("maps FastAPI validation errors to form fields", () => {
    const detail = [
      { loc: ["body", "end"], msg: "Value error, end must be after start", type: "value_error" },
      { loc: ["body", "description"], msg: "String should have at least 1 character" },
    ];
    const out = parseDetail(detail);
    expect(out.fields).toEqual({
      end: "end must be after start",
      description: "String should have at least 1 character",
    });
    expect(out.message).toContain("end: end must be after start");
  });

  it("handles errors without a field", () => {
    const out = parseDetail([{ loc: ["body"], msg: "Input should be a valid dictionary" }]);
    expect(out.fields).toEqual({});
    expect(out.message).toBe("Input should be a valid dictionary");
  });

  it("keeps the first message when a field fails twice", () => {
    const out = parseDetail([
      { loc: ["query", "limit"], msg: "first" },
      { loc: ["query", "limit"], msg: "second" },
    ]);
    expect(out.fields.limit).toBe("first");
  });

  it("falls back for unknown shapes", () => {
    expect(parseDetail(null).message).toBe("Request failed");
    expect(parseDetail({ nope: 1 }).message).toBe("Request failed");
  });
});

describe("requests", () => {
  it("prefixes /api and returns JSON", async () => {
    const fetchMock = stubFetch(() => json({ total_rows: 5 }));
    const meta = await getMeta();
    expect(meta).toEqual({ total_rows: 5 });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/meta");
  });

  it("turns a network failure into a readable ApiError", async () => {
    stubFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    await expect(getMeta()).rejects.toMatchObject({ name: "ApiError", status: 0 });
    await expect(getMeta()).rejects.toThrow(/backend/i);
  });

  it("maps a 422 response to field errors", async () => {
    stubFetch(() =>
      json({ detail: [{ loc: ["body", "end"], msg: "Value error, end must be after start" }] }, 422),
    );
    const err = await investigate({ description: "x", start: "a", end: "b" }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.fieldErrors.end).toBe("end must be after start");
  });

  it("uses the string detail of an HTTP error", async () => {
    stubFetch(() => json({ detail: "No request with this id" }, 404));
    await expect(getMeta()).rejects.toMatchObject({ status: 404, message: "No request with this id" });
  });

  it("describes a 500 without a JSON body", async () => {
    stubFetch(() => new Response("<html>boom</html>", { status: 500 }));
    await expect(getMeta()).rejects.toMatchObject({ status: 500, message: "Server error (500)" });
  });

  it("builds the overview query and normalises the timestamp separator", async () => {
    const fetchMock = stubFetch(() => json({ bucket_minutes: 5, points: [] }));
    await getOverview({ start: "2026-10-01 00:00:00", end: "2026-10-01 23:59:59", bucket_minutes: 5, service: "db-service" });
    const url = fetchMock.mock.calls[0][0];
    expect(url).toContain("/api/logs/overview?");
    expect(url).toContain("start=2026-10-01T00%3A00%3A00");
    expect(url).toContain("bucket_minutes=5");
    expect(url).toContain("service=db-service");
  });

  it("omits empty log filters from the query", async () => {
    const fetchMock = stubFetch(() => json({ items: [], limit: 100, offset: 0, has_more: false }));
    await getLogs({ start: "2026-10-01T00:00:00", end: "2026-10-01T23:59:59", service: "", q: undefined, limit: 100 });
    const url = fetchMock.mock.calls[0][0];
    expect(url).not.toContain("service=");
    expect(url).not.toContain("q=");
    expect(url).toContain("limit=100");
  });

  it("posts the investigation as JSON", async () => {
    const fetchMock = stubFetch(() => json({ status: "no_anomaly_found" }));
    await investigate({ description: "x", start: "s", end: "e" });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ description: "x", start: "s", end: "e" });
  });

  it("returns the report as text", async () => {
    stubFetch(() => new Response("# Report", { status: 200 }));
    const text = await renderReport({
      status: "no_anomaly_found",
      incident: "x",
      requested_range: { start: "a", end: "b" },
    });
    expect(text).toBe("# Report");
  });
});
