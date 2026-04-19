import { describe, expect, it } from "vitest";

import {
  buildFallbackSignal,
  shouldEscalateToManualFallback,
  toManualFallbackState,
} from "../content/manualFallback";

describe("manual fallback escalation", () => {
  it("escalates when selector parsing fails", () => {
    expect(shouldEscalateToManualFallback({ selectorFailureCount: 1, syncConfidence: "high" })).toBe(true);
  });

  it("escalates when sync confidence drops", () => {
    expect(shouldEscalateToManualFallback({ selectorFailureCount: 0, syncConfidence: "low" })).toBe(true);
  });

  it("does not escalate when selectors are healthy and sync confidence is high", () => {
    expect(shouldEscalateToManualFallback({ selectorFailureCount: 0, syncConfidence: "high" })).toBe(false);
  });

  it("builds an explicit manual fallback signal rather than silent no-op", () => {
    expect(buildFallbackSignal({ reason: "selector_failure", source: "espn" })).toEqual(
      expect.objectContaining({
        type: "manual_fallback",
        reason: "selector_failure",
        source: "espn",
        mode: "manual",
        silent: false,
      }),
    );
  });

  it("maps sync-health state to manual fallback visibility", () => {
    expect(toManualFallbackState({ reason: "sync_confidence_low", source: "yahoo" })).toEqual({
      mode: "manual",
      indicator: "degraded",
      source: "yahoo",
      message: "Manual fallback active: sync_confidence_low",
    });
  });

  it("observability: includes selector and manual-fallback activation signals", () => {
    expect(buildFallbackSignal({ reason: "selector_failure", source: "espn" })).toEqual(
      expect.objectContaining({
        observability: ["selector_fallback", "manual_fallback_activated"],
      }),
    );
  });

  it("observability: omits selector fallback when reason is sync confidence low", () => {
    expect(buildFallbackSignal({ reason: "sync_confidence_low", source: "yahoo" })).toEqual(
      expect.objectContaining({
        observability: ["manual_fallback_activated"],
      }),
    );
  });
});
