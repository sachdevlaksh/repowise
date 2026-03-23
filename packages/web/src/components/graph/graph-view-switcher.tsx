"use client";

import { useState, useCallback, useEffect } from "react";
import { Search, RotateCcw, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useDebounce } from "@/lib/hooks/use-debounce";
import { searchNodes } from "@/lib/api/graph";
import type { NodeSearchResult } from "@/lib/api/types";

export type ViewMode = "module" | "ego" | "architecture" | "dead" | "hotfiles" | "full";

const VIEWS: { id: ViewMode; label: string; warn?: boolean }[] = [
  { id: "module", label: "Module" },
  { id: "ego", label: "Neighborhood" },
  { id: "architecture", label: "Architecture" },
  { id: "dead", label: "Dead Code" },
  { id: "hotfiles", label: "Hot Files" },
  { id: "full", label: "Full Graph", warn: true },
];

interface GraphViewSwitcherProps {
  repoId: string;
  view: ViewMode;
  hops: number;
  days: number;
  onViewChange: (view: ViewMode) => void;
  onNodeSelect: (nodeId: string) => void;
  onHopsChange: (hops: number) => void;
  onDaysChange: (days: number) => void;
}

export function GraphViewSwitcher({
  repoId,
  view,
  hops,
  days,
  onViewChange,
  onNodeSelect,
  onHopsChange,
  onDaysChange,
}: GraphViewSwitcherProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<NodeSearchResult[]>([]);
  const [showResults, setShowResults] = useState(false);

  const debouncedSearch = useDebounce(searchQuery, 300);

  useEffect(() => {
    if (!debouncedSearch.trim()) {
      setSearchResults([]);
      setShowResults(false);
      return;
    }
    searchNodes(repoId, debouncedSearch, 10)
      .then((results) => {
        setSearchResults(results);
        setShowResults(results.length > 0);
      })
      .catch(() => setSearchResults([]));
  }, [debouncedSearch, repoId]);

  const handleSelectNode = useCallback(
    (nodeId: string) => {
      onNodeSelect(nodeId);
      setSearchQuery("");
      setShowResults(false);
    },
    [onNodeSelect],
  );

  const showSearch = view === "ego" || view === "module";

  return (
    <div className="shrink-0 flex items-center gap-2 px-4 py-2 border-b border-[var(--color-border-default)] bg-[var(--color-bg-surface)] flex-wrap">
      {/* View tabs */}
      <div className="flex items-center gap-1">
        {VIEWS.map((v) => (
          <Button
            key={v.id}
            size="sm"
            variant={view === v.id ? "default" : "ghost"}
            onClick={() => onViewChange(v.id)}
            className="h-7 px-2.5 text-xs gap-1"
          >
            {v.warn && <AlertTriangle className="h-3 w-3 text-amber-400" />}
            {v.label}
          </Button>
        ))}
      </div>

      <div className="h-4 w-px bg-[var(--color-border-default)]" />

      {/* File search */}
      {showSearch && (
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--color-text-tertiary)]" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => searchResults.length > 0 && setShowResults(true)}
            onBlur={() => setTimeout(() => setShowResults(false), 150)}
            placeholder="Search file…"
            className="h-7 pl-7 pr-3 w-48 text-xs"
          />
          {showResults && (
            <div className="absolute top-full left-0 mt-1 z-50 w-72 rounded-md border border-[var(--color-border-default)] bg-[var(--color-bg-overlay)] shadow-lg py-1">
              {searchResults.map((r) => (
                <button
                  key={r.node_id}
                  className="w-full px-3 py-1.5 text-left text-xs hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)]"
                  onMouseDown={() => handleSelectNode(r.node_id)}
                >
                  <span className="font-mono">{r.node_id}</span>
                  <span className="ml-2 text-[var(--color-text-tertiary)]">{r.language}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Hop depth (ego view) */}
      {view === "ego" && (
        <Select value={String(hops)} onValueChange={(v) => onHopsChange(Number(v))}>
          <SelectTrigger className="h-7 w-20 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="1">1 hop</SelectItem>
            <SelectItem value="2">2 hops</SelectItem>
            <SelectItem value="3">3 hops</SelectItem>
          </SelectContent>
        </Select>
      )}

      {/* Days selector (hot files) */}
      {view === "hotfiles" && (
        <Select value={String(days)} onValueChange={(v) => onDaysChange(Number(v))}>
          <SelectTrigger className="h-7 w-20 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">7 days</SelectItem>
            <SelectItem value="30">30 days</SelectItem>
            <SelectItem value="90">90 days</SelectItem>
          </SelectContent>
        </Select>
      )}

      <div className="ml-auto">
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onViewChange("module")}
          className="h-7 px-2 text-xs gap-1"
          title="Reset to module view"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset
        </Button>
      </div>
    </div>
  );
}
