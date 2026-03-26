"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import * as d3 from "d3";
import type { SimulationNodeDatum, SimulationLinkDatum } from "d3-force";
import { SlidersHorizontal, Download, Route, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { GraphTooltip } from "./graph-tooltip";
import { GraphFilterPanel, type GraphFilters } from "./graph-filter-panel";
import { GraphMinimap } from "./graph-minimap";
import { PathFinder } from "./path-finder";
import {
  useGraph,
  useModuleGraph,
  useEgoGraph,
  useArchitectureGraph,
  useDeadCodeGraph,
  useHotFilesGraph,
} from "@/lib/hooks/use-graph";
import { languageColor } from "@/lib/utils/confidence";
import type { GraphNodeResponse } from "@/lib/api/types";

export type ViewMode = "module" | "ego" | "architecture" | "dead" | "hotfiles" | "full";

// Community colors palette (24 distinct colors)
const COMMUNITY_COLORS = [
  "#6366f1","#ec4899","#10b981","#f59e0b","#3b82f6","#a855f7",
  "#14b8a6","#f97316","#84cc16","#06b6d4","#e11d48","#8b5cf6",
  "#22c55e","#eab308","#0ea5e9","#d946ef","#ef4444","#78716c",
  "#64748b","#0891b2","#059669","#b45309","#7c3aed","#db2777",
];

// Normalized node — superset of all view-specific node types
interface NormalizedNode {
  node_id: string;
  node_type: string;
  language: string;
  symbol_count: number;
  pagerank: number;
  betweenness: number;
  community_id: number;
  is_test: boolean;
  is_entry_point: boolean;
  file_count?: number;
  doc_coverage_pct?: number;
  confidence_group?: string;
  commit_count?: number;
}

type SimNode = NormalizedNode & SimulationNodeDatum;
type SimLink = SimulationLinkDatum<SimNode> & {
  imported_names: string[];
  edge_count?: number;
};

interface HoverState {
  node: SimNode;
  x: number;
  y: number;
}

const MINIMAP_W = 160;
const MINIMAP_H = 120;

function nodeRadius(node: SimNode, viewMode: ViewMode, sizeBy: GraphFilters["sizeBy"]): number {
  if (viewMode === "module" && node.file_count !== undefined) {
    return 6 + Math.sqrt(node.file_count) * 2.5;
  }
  if (viewMode === "hotfiles" && node.commit_count !== undefined && node.commit_count > 0) {
    return 4 + Math.min(10, Math.sqrt(node.commit_count) * 1.5);
  }
  switch (sizeBy) {
    case "symbol_count":
      return 4 + Math.min(8, node.symbol_count / 10);
    case "pagerank":
      return 4 + Math.min(8, node.pagerank * 1000);
    case "betweenness":
      return 4 + Math.min(8, node.betweenness * 50);
  }
}

function nodeColor(node: SimNode, viewMode: ViewMode, colorBy: GraphFilters["colorBy"]): string {
  if (viewMode === "module" && node.doc_coverage_pct !== undefined) {
    return d3.interpolateRgb("#dc2626", "#22c55e")(node.doc_coverage_pct);
  }
  if (viewMode === "dead") {
    if (node.confidence_group === "certain") return "#dc2626";
    if (node.confidence_group === "likely") return "rgba(220,38,38,0.6)";
    return "#64748b"; // neighbor
  }
  if (node.node_id.startsWith("external:")) return "#78716c";
  switch (colorBy) {
    case "language":
      return languageColor(node.language);
    case "community":
      return COMMUNITY_COLORS[node.community_id % COMMUNITY_COLORS.length];
    case "entry_point":
      return node.is_entry_point ? "#f59e0b" : languageColor(node.language);
  }
}

export interface GraphCanvasProps {
  repoId: string;
  viewMode?: ViewMode;
  centerNodeId?: string | null;
  hops?: number;
  days?: number;
  onNodeClick?: (nodeId: string) => void;
  onNodeViewDocs?: (nodeId: string) => void;
  onViewChange?: (view: ViewMode) => void;
}

export function GraphCanvas({
  repoId,
  viewMode = "module",
  centerNodeId,
  hops = 2,
  days = 30,
  onNodeClick,
  onNodeViewDocs,
  onViewChange,
}: GraphCanvasProps) {
  const router = useRouter();

  // All hooks called unconditionally; null key = no fetch
  const { graph: fullGraph, isLoading: fullLoading, error: fullError } = useGraph(
    viewMode === "full" ? repoId : null,
  );
  const { graph: moduleGraph, isLoading: moduleLoading } = useModuleGraph(
    viewMode === "module" ? repoId : null,
  );
  const { graph: egoGraph, isLoading: egoLoading } = useEgoGraph(
    viewMode === "ego" ? repoId : null,
    viewMode === "ego" ? (centerNodeId ?? null) : null,
    hops,
  );
  const { graph: archGraph, isLoading: archLoading } = useArchitectureGraph(
    viewMode === "architecture" ? repoId : null,
  );
  const { graph: deadGraph, isLoading: deadLoading } = useDeadCodeGraph(
    viewMode === "dead" ? repoId : null,
  );
  const { graph: hotGraph, isLoading: hotLoading } = useHotFilesGraph(
    viewMode === "hotfiles" ? repoId : null,
    days,
  );

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const minimapRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const transformRef = useRef<d3.ZoomTransform>(d3.zoomIdentity);
  const simNodesRef = useRef<SimNode[]>([]);
  const simLinksRef = useRef<SimLink[]>([]);
  const animFrameRef = useRef<number | null>(null);
  const adjacencyRef = useRef<Map<string, Set<string>>>(new Map());
  const neighborhoodRef = useRef<Set<string> | null>(null);

  const [hoveredNode, setHoveredNode] = useState<HoverState | null>(null);
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 600 });
  const [showFilter, setShowFilter] = useState(false);
  const [showPathFinder, setShowPathFinder] = useState(false);
  const [highlightedPath, setHighlightedPath] = useState<Set<string>>(new Set());
  const [showFullGraphWarning, setShowFullGraphWarning] = useState(false);
  const [filters, setFilters] = useState<GraphFilters>({
    hiddenLangs: new Set(),
    hideTests: false,
    colorBy: "language",
    sizeBy: "symbol_count",
    nodeSearch: "",
  });

  // Normalize graph data to a common shape for all views
  const normalizedData = useMemo<{
    nodes: NormalizedNode[];
    links: { source: string; target: string; imported_names: string[]; edge_count?: number }[];
  } | null>(() => {
    switch (viewMode) {
      case "full":
        if (!fullGraph) return null;
        return { nodes: fullGraph.nodes, links: fullGraph.links };
      case "module":
        if (!moduleGraph) return null;
        return {
          nodes: moduleGraph.nodes.map((m) => ({
            node_id: m.module_id,
            node_type: "module",
            language: "",
            symbol_count: m.symbol_count,
            pagerank: m.avg_pagerank,
            betweenness: 0,
            community_id: 0,
            is_test: false,
            is_entry_point: false,
            file_count: m.file_count,
            doc_coverage_pct: m.doc_coverage_pct,
          })),
          links: moduleGraph.edges.map((e) => ({
            source: e.source,
            target: e.target,
            imported_names: [],
            edge_count: e.edge_count,
          })),
        };
      case "ego":
        if (!egoGraph) return null;
        return { nodes: egoGraph.nodes, links: egoGraph.links };
      case "architecture":
        if (!archGraph) return null;
        return { nodes: archGraph.nodes, links: archGraph.links };
      case "dead":
        if (!deadGraph) return null;
        return { nodes: deadGraph.nodes, links: deadGraph.links };
      case "hotfiles":
        if (!hotGraph) return null;
        return { nodes: hotGraph.nodes, links: hotGraph.links };
      default:
        return null;
    }
  }, [viewMode, fullGraph, moduleGraph, egoGraph, archGraph, deadGraph, hotGraph]);

  // Full graph warning gate
  useEffect(() => {
    if (viewMode === "full" && fullGraph && fullGraph.nodes.length > 2000) {
      const confirmed =
        typeof window !== "undefined" &&
        sessionStorage.getItem("full-graph-confirmed") === "1";
      if (!confirmed) setShowFullGraphWarning(true);
    }
  }, [viewMode, fullGraph]);

  // Resize observer
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0]!.contentRect;
      setCanvasSize({ w: Math.floor(width), h: Math.floor(height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Update hover neighborhood for dimming
  useEffect(() => {
    if (!hoveredNode) {
      neighborhoodRef.current = null;
      return;
    }
    const visited = new Set<string>([hoveredNode.node.node_id]);
    let frontier = [hoveredNode.node.node_id];
    for (let hop = 0; hop < 2; hop++) {
      const next: string[] = [];
      for (const id of frontier) {
        for (const nbr of adjacencyRef.current.get(id) ?? []) {
          if (!visited.has(nbr)) {
            visited.add(nbr);
            next.push(nbr);
          }
        }
      }
      frontier = next;
    }
    neighborhoodRef.current = visited;
  }, [hoveredNode]);

  const drawFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { w, h } = canvasSize;
    const t = transformRef.current;
    const search = filters.nodeSearch.toLowerCase();
    const neighborhood = neighborhoodRef.current;
    const hasPathFilter = highlightedPath.size > 0;

    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(t.x, t.y);
    ctx.scale(t.k, t.k);

    // Draw edges
    for (const link of simLinksRef.current) {
      const src = link.source as SimNode;
      const tgt = link.target as SimNode;
      if (src.x == null || src.y == null || tgt.x == null || tgt.y == null) continue;
      if (filters.hiddenLangs.has(src.language) || filters.hiddenLangs.has(tgt.language)) continue;

      const inNeighborhood =
        !neighborhood ||
        (neighborhood.has(src.node_id) && neighborhood.has(tgt.node_id));
      const isOnPath =
        hasPathFilter &&
        (highlightedPath.has(src.node_id) || highlightedPath.has(tgt.node_id));
      const isDynamic = link.imported_names.length === 0 && viewMode !== "module";

      ctx.beginPath();
      ctx.moveTo(src.x, src.y);
      ctx.lineTo(tgt.x, tgt.y);
      ctx.strokeStyle = isDynamic ? "rgba(150,150,150,1)" : "rgba(91,156,246,1)";
      ctx.globalAlpha = !inNeighborhood
        ? 0.05
        : hasPathFilter && !isOnPath
          ? 0.05
          : isDynamic
            ? 0.25
            : 0.4;
      ctx.lineWidth =
        viewMode === "module"
          ? (1 + Math.min(3, Math.sqrt(link.edge_count ?? 1) * 0.5)) / t.k
          : (1 + Math.min(3, link.imported_names.length * 0.4)) / t.k;
      if (isDynamic) {
        ctx.setLineDash([4 / t.k, 4 / t.k]);
      } else {
        ctx.setLineDash([]);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw nodes
    for (const node of simNodesRef.current) {
      if (node.x == null || node.y == null) continue;
      if (filters.hiddenLangs.has(node.language)) continue;
      if (filters.hideTests && node.is_test) continue;

      const r = nodeRadius(node, viewMode, filters.sizeBy);
      const color = nodeColor(node, viewMode, filters.colorBy);
      const isMatch = search ? node.node_id.toLowerCase().includes(search) : false;
      const isOnPath = hasPathFilter && highlightedPath.has(node.node_id);
      const inNbr = !neighborhood || neighborhood.has(node.node_id);
      const dimmed = (hasPathFilter && !isOnPath) || (neighborhood !== null && !inNbr);

      ctx.globalAlpha = dimmed ? 0.15 : 1.0;

      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
      ctx.fillStyle = isOnPath ? "#f97316" : color;
      ctx.fill();

      // Entry point / architecture ring
      if (node.is_entry_point && !isOnPath) {
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = (viewMode === "architecture" ? 2.5 : 2) / t.k;
        ctx.stroke();
      }
      if (viewMode === "architecture" && node.is_entry_point && !isOnPath) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 4 / t.k, 0, Math.PI * 2);
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.5 / t.k;
        ctx.stroke();
      }

      // Path highlight ring
      if (isOnPath) {
        ctx.globalAlpha = 1;
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 4 / t.k, 0, Math.PI * 2);
        ctx.strokeStyle = "#f97316";
        ctx.lineWidth = 2.5 / t.k;
        ctx.stroke();
      }

      // Search highlight
      if (isMatch && !isOnPath) {
        ctx.globalAlpha = 1;
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 3 / t.k, 0, Math.PI * 2);
        ctx.strokeStyle = "#eab308";
        ctx.lineWidth = 2 / t.k;
        ctx.stroke();
      }

      // Module label for large nodes
      if (viewMode === "module" && r > 14) {
        ctx.globalAlpha = dimmed ? 0.15 : 0.9;
        ctx.fillStyle = "#ffffff";
        ctx.font = `bold ${Math.min(12, r * 0.7) / t.k}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const label = node.node_id.length > 10 ? node.node_id.slice(0, 9) + "…" : node.node_id;
        ctx.fillText(label, node.x, node.y);
      }
    }

    ctx.globalAlpha = 1;
    ctx.restore();

    // Minimap
    const mc = minimapRef.current;
    if (mc && simNodesRef.current.length > 0) {
      const mctx = mc.getContext("2d");
      if (mctx) {
        mctx.clearRect(0, 0, MINIMAP_W, MINIMAP_H);
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        for (const n of simNodesRef.current) {
          if (n.x == null || n.y == null) continue;
          if (n.x < minX) minX = n.x;
          if (n.x > maxX) maxX = n.x;
          if (n.y < minY) minY = n.y;
          if (n.y > maxY) maxY = n.y;
        }
        if (!isFinite(minX)) return;
        const pad = 20;
        minX -= pad; maxX += pad; minY -= pad; maxY += pad;
        const worldW = maxX - minX;
        const worldH = maxY - minY;
        const scale = Math.min(MINIMAP_W / worldW, MINIMAP_H / worldH);
        const offX = (MINIMAP_W - worldW * scale) / 2 - minX * scale;
        const offY = (MINIMAP_H - worldH * scale) / 2 - minY * scale;
        for (const node of simNodesRef.current) {
          if (node.x == null || node.y == null) continue;
          mctx.beginPath();
          mctx.arc(node.x * scale + offX, node.y * scale + offY, 1.5, 0, Math.PI * 2);
          mctx.fillStyle = nodeColor(node, viewMode, filters.colorBy);
          mctx.globalAlpha = 0.7;
          mctx.fill();
        }
        mctx.globalAlpha = 1;
        const { w: cw, h: ch } = canvasSize;
        const vtx = (-t.x / t.k) * scale + offX;
        const vty = (-t.y / t.k) * scale + offY;
        const vtw = (cw / t.k) * scale;
        const vth = (ch / t.k) * scale;
        mctx.strokeStyle = "rgba(255,255,255,0.6)";
        mctx.lineWidth = 1;
        mctx.strokeRect(vtx, vty, vtw, vth);
      }
    }
  }, [canvasSize, filters, highlightedPath, viewMode]);

  // D3 simulation
  useEffect(() => {
    if (!normalizedData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const { w, h } = canvasSize;

    simNodesRef.current = normalizedData.nodes.map((n) => ({ ...n }));
    simLinksRef.current = normalizedData.links.map((l) => ({
      ...l,
      source: l.source as string,
      target: l.target as string,
    })) as SimLink[];

    // Build undirected adjacency for hover dimming
    const adj = new Map<string, Set<string>>();
    for (const link of normalizedData.links) {
      const s = link.source;
      const tgt = link.target;
      if (!adj.has(s)) adj.set(s, new Set());
      if (!adj.has(tgt)) adj.set(tgt, new Set());
      adj.get(s)!.add(tgt);
      adj.get(tgt)!.add(s);
    }
    adjacencyRef.current = adj;

    // Clustering gravity (pull same-directory nodes together)
    function clusterForce(alpha: number) {
      const centroids = new Map<string, { x: number; y: number; count: number }>();
      for (const n of simNodesRef.current) {
        if (n.x == null || n.y == null) continue;
        const dir = n.node_id.split("/")[0] ?? n.node_id;
        const c = centroids.get(dir) ?? { x: 0, y: 0, count: 0 };
        c.x += n.x;
        c.y += n.y;
        c.count++;
        centroids.set(dir, c);
      }
      for (const n of simNodesRef.current) {
        if (n.x == null || n.y == null) continue;
        const dir = n.node_id.split("/")[0] ?? n.node_id;
        const c = centroids.get(dir);
        if (!c || c.count === 0) continue;
        n.vx! += (c.x / c.count - n.x) * alpha * 0.04;
        n.vy! += (c.y / c.count - n.y) * alpha * 0.04;
      }
    }

    const isFileLevelView = viewMode === "full" || viewMode === "ego";
    const isModuleView = viewMode === "module";

    const simulation = d3
      .forceSimulation<SimNode>(simNodesRef.current)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimLink>(simLinksRef.current)
          .id((d) => d.node_id)
          .distance(isModuleView ? 120 : 60),
      )
      .force("charge", d3.forceManyBody<SimNode>().strength(isModuleView ? -500 : -150))
      .force("center", d3.forceCenter(w / 2, h / 2))
      .force("collide", d3.forceCollide<SimNode>(isModuleView ? 35 : 12))
      .alphaDecay(0.02)
      .on("tick", () => {
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = requestAnimationFrame(drawFrame);
      });

    if (isFileLevelView) {
      simulation.force("cluster", clusterForce);
    }

    const zoom = d3
      .zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.05, 20])
      .on("zoom", (event) => {
        transformRef.current = event.transform;
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = requestAnimationFrame(drawFrame);
      });

    d3.select(canvas).call(zoom);

    return () => {
      simulation.stop();
      d3.select(canvas).on(".zoom", null);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [normalizedData, canvasSize]);

  // Redraw when filters/path/hover change
  useEffect(() => { drawFrame(); }, [filters, highlightedPath, drawFrame]);
  useEffect(() => { drawFrame(); }, [hoveredNode, drawFrame]);

  const handleExportPng = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const link = document.createElement("a");
    link.download = "dependency-graph.png";
    link.href = canvas.toDataURL("image/png");
    link.click();
  }, []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      // Scale from CSS pixels to canvas pixels (accounts for any CSS/intrinsic size mismatch)
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const mxCSS = e.clientX - rect.left;
      const myCSS = e.clientY - rect.top;
      const mx = mxCSS * scaleX;
      const my = myCSS * scaleY;
      const t = transformRef.current;
      const wx = (mx - t.x) / t.k;
      const wy = (my - t.y) / t.k;

      let closest: SimNode | null = null;
      let minDist = Infinity;

      for (const node of simNodesRef.current) {
        if (node.x == null || node.y == null) continue;
        if (filters.hiddenLangs.has(node.language)) continue;
        if (filters.hideTests && node.is_test) continue;
        const r = nodeRadius(node, viewMode, filters.sizeBy);
        const dx = node.x - wx;
        const dy = node.y - wy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        // Hit threshold: node radius + 4 CSS pixels of margin (4/t.k converts to world space)
        if (dist < r + 4 / t.k && dist < minDist) {
          closest = node;
          minDist = dist;
        }
      }

      // Store CSS pixel coords for tooltip positioning
      setHoveredNode(closest ? { node: closest, x: mxCSS, y: myCSS } : null);
    },
    [filters, viewMode],
  );

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const mx = (e.clientX - rect.left) * scaleX;
      const my = (e.clientY - rect.top) * scaleY;
      const t = transformRef.current;
      const wx = (mx - t.x) / t.k;
      const wy = (my - t.y) / t.k;

      // Find the closest node within threshold (same logic as hover)
      let closest: SimNode | null = null;
      let minDist = Infinity;
      for (const node of simNodesRef.current) {
        if (node.x == null || node.y == null) continue;
        const r = nodeRadius(node, viewMode, filters.sizeBy);
        const dx = node.x - wx;
        const dy = node.y - wy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < r + 4 / t.k && dist < minDist) {
          closest = node;
          minDist = dist;
        }
      }

      if (closest) {
        if (viewMode === "module") {
          onNodeClick?.(closest.node_id);
        } else {
          // Open doc panel for the clicked node
          onNodeViewDocs?.(closest.node_id);
        }
      }
    },
    [filters, viewMode, onNodeClick, onNodeViewDocs],
  );

  const isLoading =
    viewMode === "full" ? fullLoading :
    viewMode === "module" ? moduleLoading :
    viewMode === "ego" ? egoLoading :
    viewMode === "architecture" ? archLoading :
    viewMode === "dead" ? deadLoading :
    viewMode === "hotfiles" ? hotLoading : false;

  const error = viewMode === "full" ? fullError : null;

  const availableLangs = Array.from(
    new Set((normalizedData?.nodes ?? []).map((n) => n.language).filter(Boolean)),
  ).sort();

  const nodeCount = normalizedData?.nodes.length ?? 0;
  const linkCount = normalizedData?.links.length ?? 0;

  if (isLoading) {
    return <Skeleton className="h-full w-full rounded-lg" />;
  }

  if ((!normalizedData || error) && !showFullGraphWarning) {
    return (
      <EmptyState
        title={viewMode === "ego" && !centerNodeId ? "Select a node" : "No data"}
        description={
          viewMode === "ego" && !centerNodeId
            ? "Search for a file above or click a module node to explore its neighborhood."
            : "Check that the backend is running and this repo has been indexed."
        }
      />
    );
  }

  return (
    <div ref={containerRef} className="relative w-full h-full">
      <canvas
        ref={canvasRef}
        width={canvasSize.w}
        height={canvasSize.h}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredNode(null)}
        onClick={handleClick}
        className="w-full h-full cursor-crosshair"
      />

      {hoveredNode && (
        <GraphTooltip
          node={hoveredNode.node as GraphNodeResponse}
          x={hoveredNode.x}
          y={hoveredNode.y}
          canvasWidth={canvasSize.w}
          canvasHeight={canvasSize.h}
        />
      )}

      {/* Toolbar */}
      <div className="absolute top-3 right-3 flex flex-wrap gap-2 justify-end">
        {viewMode === "full" && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => { setShowPathFinder((s) => !s); setShowFilter(false); }}
            className="h-8 gap-1.5"
          >
            <Route className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Path</span>
          </Button>
        )}
        <Button
          size="sm"
          variant="secondary"
          onClick={() => { setShowFilter((s) => !s); setShowPathFinder(false); }}
          className="h-8 gap-1.5"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Filter</span>
        </Button>
        <Button size="sm" variant="secondary" onClick={handleExportPng} className="h-8 gap-1.5">
          <Download className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Export</span>
        </Button>
      </div>

      {showPathFinder && viewMode === "full" && (
        <div className="absolute top-12 right-3">
          <PathFinder
            repoId={repoId}
            onPathFound={(nodes) => setHighlightedPath(new Set(nodes))}
            onClear={() => setHighlightedPath(new Set())}
          />
        </div>
      )}

      {showFilter && (
        <div className="absolute top-12 right-3">
          <GraphFilterPanel
            filters={filters}
            onChange={setFilters}
            availableLangs={availableLangs}
          />
        </div>
      )}

      <div className="absolute bottom-3 right-3">
        <GraphMinimap ref={minimapRef} />
      </div>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 rounded-md border border-[var(--color-border-default)] bg-[var(--color-bg-overlay)]/80 backdrop-blur-sm p-2 text-xs text-[var(--color-text-tertiary)] space-y-1">
        <div className="font-medium text-[var(--color-text-secondary)] mb-1">
          {nodeCount} nodes · {linkCount} edges
        </div>
        {viewMode === "module" ? (
          <>
            <div className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-green-500" />High doc coverage</div>
            <div className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-red-500" />Low doc coverage</div>
          </>
        ) : viewMode === "dead" ? (
          <>
            <div className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-red-600" />Certain dead</div>
            <div className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-red-400" />Likely dead</div>
          </>
        ) : (
          <>
            <div className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-white border border-gray-400" />Entry point</div>
            <div className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full border-2 border-yellow-400 bg-transparent" />Search match</div>
          </>
        )}
      </div>

      {/* Full graph warning dialog */}
      <Dialog
        open={showFullGraphWarning}
        onOpenChange={(open) => {
          if (!open) {
            setShowFullGraphWarning(false);
            onViewChange?.("module");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-400" />
              Large Graph Warning
            </DialogTitle>
            <DialogDescription>
              Rendering {nodeCount} nodes may be slow. This view works best for small repos.
              Continue anyway?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="secondary"
              onClick={() => {
                setShowFullGraphWarning(false);
                onViewChange?.("module");
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (typeof window !== "undefined") {
                  sessionStorage.setItem("full-graph-confirmed", "1");
                }
                setShowFullGraphWarning(false);
              }}
            >
              Continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
