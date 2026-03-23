"use client";

import { useState } from "react";
import { Route, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getGraphPath } from "@/lib/api/graph";
import type { GraphPathResponse } from "@/lib/api/types";

interface PathFinderProps {
  repoId: string;
  onPathFound: (path: string[]) => void;
  onClear: () => void;
}

export function PathFinder({ repoId, onPathFound, onClear }: PathFinderProps) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GraphPathResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFind() {
    if (!from.trim() || !to.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    onClear();
    try {
      const res = await getGraphPath(repoId, from.trim(), to.trim());
      setResult(res);
      onPathFound(res.path.map((step) => step.node));
    } catch {
      setError("No path found between these nodes.");
    } finally {
      setLoading(false);
    }
  }

  function handleClear() {
    setFrom("");
    setTo("");
    setResult(null);
    setError(null);
    onClear();
  }

  return (
    <div className="rounded-lg border border-[var(--color-border-default)] bg-[var(--color-bg-overlay)]/90 backdrop-blur-sm p-3 space-y-2 w-64">
      <div className="flex items-center gap-1.5">
        <Route className="h-3.5 w-3.5 text-[var(--color-accent-primary)] shrink-0" />
        <span className="text-xs font-medium text-[var(--color-text-primary)]">Path Finder</span>
      </div>

      <div className="space-y-1.5">
        <Input
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          placeholder="From node (file path)"
          className="h-7 text-xs font-mono"
          onKeyDown={(e) => e.key === "Enter" && handleFind()}
        />
        <Input
          value={to}
          onChange={(e) => setTo(e.target.value)}
          placeholder="To node (file path)"
          className="h-7 text-xs font-mono"
          onKeyDown={(e) => e.key === "Enter" && handleFind()}
        />
      </div>

      <div className="flex gap-1.5">
        <Button
          size="sm"
          onClick={handleFind}
          disabled={!from.trim() || !to.trim() || loading}
          className="flex-1 h-7 text-xs gap-1"
        >
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Route className="h-3 w-3" />
          )}
          Find
        </Button>
        {(result || error) && (
          <Button size="sm" variant="ghost" onClick={handleClear} className="h-7 w-7 p-0" aria-label="Clear path">
            <X className="h-3 w-3" />
          </Button>
        )}
      </div>

      {result && (
        <div className="text-xs text-[var(--color-text-secondary)] space-y-1">
          <p className="font-medium text-[var(--color-confidence-fresh)]">
            Path found — {result.distance} hops
          </p>
          <div className="max-h-24 overflow-auto space-y-0.5">
            {result.path.map((step, i) => (
              <div key={i} className="font-mono truncate text-[var(--color-text-tertiary)]">
                {i > 0 && <span className="text-[var(--color-accent-primary)] mr-1">→</span>}
                {step.node}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <p className="text-xs text-[var(--color-confidence-outdated)]">{error}</p>
      )}
    </div>
  );
}
