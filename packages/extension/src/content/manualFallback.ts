type SyncConfidence = "high" | "low";
type FallbackSource = "espn" | "yahoo";
type FallbackReason = "selector_failure" | "sync_confidence_low";

type EscalationInput = {
  selectorFailureCount: number;
  syncConfidence: SyncConfidence;
};

type FallbackSignalInput = {
  reason: FallbackReason;
  source: FallbackSource;
};

export function shouldEscalateToManualFallback(input: EscalationInput): boolean {
  return input.selectorFailureCount > 0 || input.syncConfidence === "low";
}

export function buildFallbackSignal(input: FallbackSignalInput): {
  type: "manual_fallback";
  reason: FallbackReason;
  source: FallbackSource;
  mode: "manual";
  silent: false;
  observability:
    | ["selector_fallback", "manual_fallback_activated"]
    | ["manual_fallback_activated"];
} {
  const observability: ["selector_fallback", "manual_fallback_activated"] | ["manual_fallback_activated"] =
    input.reason === "selector_failure"
      ? ["selector_fallback", "manual_fallback_activated"]
      : ["manual_fallback_activated"];

  return {
    type: "manual_fallback",
    reason: input.reason,
    source: input.source,
    mode: "manual",
    silent: false,
    observability,
  };
}

export function toManualFallbackState(input: FallbackSignalInput): {
  mode: "manual";
  indicator: "degraded";
  source: FallbackSource;
  message: string;
} {
  return {
    mode: "manual",
    indicator: "degraded",
    source: input.source,
    message: `Manual fallback active: ${input.reason}`,
  };
}
