"use client";

import { useEffect } from "react";

import { RankingsTable } from "@/components/RankingsTable";
import { SourceWeightSelector } from "@/components/SourceWeightSelector";
import { fetchSources } from "@/lib/api/sources";
import { computeRankings } from "@/lib/api/rankings";
import { useStore } from "@/store";

export default function DashboardPage() {
  const {
    sources,
    weights,
    rankings,
    loading,
    error,
    cached,
    season,
    setSources,
    setWeight,
    resetWeights,
    activeWeights,
    setRankings,
    setLoading,
    setError,
  } = useStore();

  useEffect(() => {
    fetchSources().then(setSources).catch(() => {});
  }, []);

  async function handleCompute() {
    setLoading(true);
    try {
      // TODO: replace hardcoded scoring_config_id and platform with user-selected values
      const result = await computeRankings({ season, source_weights: activeWeights(), scoring_config_id: "default", platform: "espn" });
      setRankings(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold tracking-tight">Fantasy Rankings</h1>

      {sources.length > 0 && (
        <section className="mb-6 rounded-lg border border-slate-200 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Source Weights
          </h2>
          <SourceWeightSelector
            sources={sources}
            weights={weights}
            setWeight={setWeight}
            onReset={resetWeights}
            disabled={loading}
          />
        </section>
      )}

      <div className="mb-6 flex items-center gap-4">
        <button
          type="button"
          onClick={handleCompute}
          disabled={loading}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Compute Rankings
        </button>

        {loading && (
          <span role="status" className="text-sm text-slate-500">
            Computing…
          </span>
        )}

        {cached && !loading && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
            Cached
          </span>
        )}
      </div>

      {error && (
        <p className="mb-4 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      {rankings.length > 0 && (
        <RankingsTable rankings={rankings} sources={sources} />
      )}
    </main>
  );
}
