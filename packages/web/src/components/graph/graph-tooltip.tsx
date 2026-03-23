import { formatNumber } from "@/lib/utils/format";
import type { GraphNodeResponse } from "@/lib/api/types";

interface GraphTooltipProps {
  node: GraphNodeResponse;
  x: number;
  y: number;
  canvasWidth: number;
  canvasHeight: number;
}

export function GraphTooltip({ node, x, y, canvasWidth, canvasHeight }: GraphTooltipProps) {
  const tooltipW = 200;
  const tooltipH = 130;
  const left = x + 16 + tooltipW > canvasWidth ? x - tooltipW - 8 : x + 16;
  const top = y + tooltipH > canvasHeight ? y - tooltipH : y;

  return (
    <div
      className="absolute pointer-events-none z-10 rounded-lg border border-[var(--color-border-default)] bg-[var(--color-bg-overlay)] p-3 shadow-lg text-xs"
      style={{ left, top, width: tooltipW }}
    >
      <p className="font-mono font-semibold text-[var(--color-text-primary)] mb-2 truncate">
        {node.node_id}
      </p>
      <div className="space-y-1 text-[var(--color-text-secondary)]">
        <div className="flex justify-between">
          <span>Language</span>
          <span className="font-medium text-[var(--color-text-primary)]">{node.language}</span>
        </div>
        <div className="flex justify-between">
          <span>Symbols</span>
          <span className="font-medium text-[var(--color-text-primary)] tabular-nums">
            {formatNumber(node.symbol_count)}
          </span>
        </div>
        <div className="flex justify-between">
          <span>PageRank</span>
          <span className="font-medium text-[var(--color-text-primary)] tabular-nums">
            {node.pagerank.toFixed(4)}
          </span>
        </div>
        <div className="flex justify-between">
          <span>Community</span>
          <span className="font-medium text-[var(--color-text-primary)] tabular-nums">
            {node.community_id}
          </span>
        </div>
        {node.is_entry_point && (
          <span className="inline-block mt-1 rounded border border-[var(--color-accent-primary)] bg-[var(--color-accent-muted)] px-1.5 py-0.5 text-xs text-[var(--color-accent-primary)]">
            Entry Point
          </span>
        )}
      </div>
    </div>
  );
}
