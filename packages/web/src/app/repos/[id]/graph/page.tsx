"use client";

import { use, useCallback } from "react";
import { useQueryState, parseAsString, parseAsInteger } from "nuqs";
import { GraphCanvas, type ViewMode } from "@/components/graph/graph-canvas";
import { GraphViewSwitcher } from "@/components/graph/graph-view-switcher";
import { GraphEgoSidebar } from "@/components/graph/graph-ego-sidebar";
import { useEgoGraph } from "@/lib/hooks/use-graph";
import { searchNodes } from "@/lib/api/graph";

export default function GraphPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: repoId } = use(params);

  const [view, setView] = useQueryState("view", parseAsString.withDefault("module"));
  const [node, setNode] = useQueryState("node");
  const [hops, setHops] = useQueryState("hops", parseAsInteger.withDefault(2));
  const [days, setDays] = useQueryState("days", parseAsInteger.withDefault(30));

  const viewMode = view as ViewMode;

  // Fetch ego graph data so we can show the sidebar
  const { graph: egoGraph } = useEgoGraph(
    viewMode === "ego" ? repoId : null,
    viewMode === "ego" ? node : null,
    hops,
  );

  const handleNodeClick = useCallback(
    async (nodeId: string) => {
      if (viewMode === "module") {
        try {
          // Fetch many candidates so we can pick the most representative code file
          const results = await searchNodes(repoId, nodeId + "/", 40);
          // Exclude config/doc files that have no symbols; prefer actual code
          const NON_CODE = new Set(["markdown", "json", "yaml", "toml", "text", "plaintext", "xml", "ini", ""]);
          const codeFiles = results.filter(
            (r) => !NON_CODE.has(r.language.toLowerCase()) && r.symbol_count > 0,
          );
          // Fall back to any non-doc file, then any file if nothing else
          const candidates = codeFiles.length > 0
            ? codeFiles
            : results.filter((r) => !NON_CODE.has(r.language.toLowerCase()));
          const pool = candidates.length > 0 ? candidates : results;
          // Pick the file with the most symbols (most substantive)
          const best = pool.sort((a, b) => b.symbol_count - a.symbol_count)[0];
          const targetNode = best?.node_id ?? nodeId;
          await setView("ego");
          await setNode(targetNode);
        } catch {
          await setView("ego");
          await setNode(nodeId);
        }
      } else {
        await setView("ego");
        await setNode(nodeId);
      }
    },
    [viewMode, repoId, setView, setNode],
  );

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="shrink-0 px-4 sm:px-6 py-3 border-b border-[var(--color-border-default)]">
        <h1 className="text-lg font-semibold text-[var(--color-text-primary)]">
          Dependency Graph
        </h1>
        <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
          {viewMode === "module" && "Module overview — click a node to explore its neighborhood"}
          {viewMode === "ego" && `Neighborhood of ${node ?? "…"}`}
          {viewMode === "architecture" && "Entry-point reachable subgraph (3 hops)"}
          {viewMode === "dead" && "Dead code — unreachable files and unused exports"}
          {viewMode === "hotfiles" && `Most-committed files (${days}d)`}
          {viewMode === "full" && "Full dependency graph — scroll to zoom, drag to pan"}
        </p>
      </div>

      {/* View switcher */}
      <GraphViewSwitcher
        repoId={repoId}
        view={viewMode}
        hops={hops}
        days={days}
        onViewChange={(v) => void setView(v)}
        onNodeSelect={(nodeId) => void handleNodeClick(nodeId)}
        onHopsChange={(h) => void setHops(h)}
        onDaysChange={(d) => void setDays(d)}
      />

      {/* Canvas area */}
      <div className="flex-1 overflow-hidden p-3">
        <div className="h-full w-full rounded-lg border border-[var(--color-border-default)] overflow-hidden relative">
          <GraphCanvas
            repoId={repoId}
            viewMode={viewMode}
            centerNodeId={node}
            hops={hops}
            days={days}
            onNodeClick={(nodeId) => void handleNodeClick(nodeId)}
            onViewChange={(v) => void setView(v)}
          />

          {/* Ego sidebar */}
          {viewMode === "ego" && egoGraph && (
            <GraphEgoSidebar
              graph={egoGraph}
              onClose={() => void setView("module")}
              onNavigateToNode={(nodeId) => void setNode(nodeId)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
