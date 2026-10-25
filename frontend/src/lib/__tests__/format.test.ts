import { describe, expect, it } from "vitest";
import {
  addMinutes,
  fmtAxis,
  fmtClock,
  fmtDuration,
  fmtOffset,
  fmtTs,
  fromInputValue,
  inputFromTs,
  msToTs,
  pct,
  serviceColor,
  toInputValue,
  tsToMs,
} from "@/lib/format";

describe("timestamp arithmetic never depends on the local timezone", () => {
  it("round-trips a naive timestamp", () => {
    expect(msToTs(tsToMs("2026-10-01T14:05:00.060"))).toBe("2026-10-01T14:05:00.060");
  });

  it("accepts a space separator and missing parts", () => {
    expect(tsToMs("2026-10-01 14:05:00")).toBe(tsToMs("2026-10-01T14:05:00.000"));
    expect(tsToMs("2026-10-01T14:05")).toBe(tsToMs("2026-10-01T14:05:00"));
  });

  it("measures differences exactly", () => {
    const diff = tsToMs("2026-10-01T14:05:03.150") - tsToMs("2026-10-01T14:05:00.060");
    expect(diff).toBe(3090);
  });

  it("handles microsecond fractions by keeping milliseconds", () => {
    expect(tsToMs("2026-10-01T14:05:00.123456")).toBe(tsToMs("2026-10-01T14:05:00.123"));
  });

  it("returns NaN for garbage", () => {
    expect(Number.isNaN(tsToMs("not a time"))).toBe(true);
  });

  it("adds minutes across midnight", () => {
    expect(addMinutes("2026-10-01T23:50:00.000", 20)).toBe("2026-10-02T00:10:00.000");
  });
});

describe("display helpers", () => {
  it("formats timestamps", () => {
    expect(fmtTs("2026-10-01T14:05:00.060")).toBe("2026-10-01 14:05:00.060");
    expect(fmtTs(null)).toBe("-");
    expect(fmtClock("2026-10-01 14:05:00.060")).toBe("14:05:00.060");
    expect(fmtClock(undefined)).toBe("-");
  });

  it("formats chart axis labels", () => {
    expect(fmtAxis("2026-10-01T14:05:00.000", false)).toBe("14:05");
    expect(fmtAxis("2026-10-01T14:05:00.000", true)).toBe("10-01 14:05");
  });

  it("formats durations", () => {
    expect(fmtDuration(250)).toBe("250 ms");
    expect(fmtDuration(3040)).toBe("3.04 s");
    expect(fmtDuration(125000)).toBe("2 min 5 s");
  });

  it("formats onset offsets", () => {
    expect(fmtOffset(0)).toBe("first");
    expect(fmtOffset(3040)).toBe("+3.04 s");
  });

  it("formats percentages", () => {
    expect(pct(0.9)).toBe("90%");
    expect(pct(undefined)).toBe("-");
  });

  it("gives every service a stable color", () => {
    expect(serviceColor("db-service")).toBe(serviceColor("db-service"));
    expect(serviceColor("some-new-service")).toMatch(/^#[0-9a-f]{6}$/);
  });
});

describe("datetime-local values", () => {
  it("converts to and from the input format", () => {
    expect(toInputValue("2026-10-01 14:05:00.060")).toBe("2026-10-01T14:05");
    expect(fromInputValue("2026-10-01T14:05")).toBe("2026-10-01T14:05:00");
    expect(fromInputValue("2026-10-01T14:05:30")).toBe("2026-10-01T14:05:30");
  });

  it("floors by default and ceils to the next minute on request", () => {
    expect(inputFromTs("2026-10-01T23:59:58.410")).toBe("2026-10-01T23:59");
    expect(inputFromTs("2026-10-01T23:59:58.410", true)).toBe("2026-10-02T00:00");
  });

  it("does not move a timestamp that is already on a whole minute", () => {
    expect(inputFromTs("2026-10-01T14:05:00.000", true)).toBe("2026-10-01T14:05");
  });
});
