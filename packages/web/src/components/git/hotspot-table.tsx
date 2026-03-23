import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/empty-state";
import { ChurnBar } from "./churn-bar";
import { truncatePath } from "@/lib/utils/format";
import type { HotspotResponse } from "@/lib/api/types";

interface HotspotTableProps {
  hotspots: HotspotResponse[];
}

export function HotspotTable({ hotspots }: HotspotTableProps) {
  if (hotspots.length === 0) {
    return (
      <EmptyState
        title="No hotspots found"
        description="All files look stable — great work!"
      />
    );
  }

  return (
    <div className="rounded-lg border border-[var(--color-border-default)] overflow-x-auto">
      <table className="w-full min-w-[560px] text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border-default)] bg-[var(--color-bg-elevated)]">
            <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider w-8">
              #
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">
              File
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider w-28">
              Commits 90d
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider w-36">
              Churn
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">
              Owner
            </th>
            <th className="px-4 py-2.5 w-16" />
          </tr>
        </thead>
        <tbody>
          {hotspots.map((h, i) => (
            <tr
              key={h.file_path}
              className="border-b border-[var(--color-border-default)] hover:bg-[var(--color-bg-elevated)] transition-colors last:border-0"
            >
              <td className="px-4 py-2.5 text-[var(--color-text-tertiary)] tabular-nums text-xs">
                {i + 1}
              </td>
              <td className="px-4 py-2.5 font-mono text-xs text-[var(--color-text-primary)] max-w-xs truncate">
                {truncatePath(h.file_path, 60)}
              </td>
              <td className="px-4 py-2.5 tabular-nums text-[var(--color-text-secondary)] text-xs">
                {h.commit_count_90d}
              </td>
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <ChurnBar percentile={h.churn_percentile} className="w-20" />
                  <span className="text-xs text-[var(--color-text-tertiary)] tabular-nums w-8">
                    {Math.round(h.churn_percentile)}%
                  </span>
                </div>
              </td>
              <td className="px-4 py-2.5 text-xs text-[var(--color-text-secondary)]">
                {h.primary_owner ?? "—"}
              </td>
              <td className="px-4 py-2.5">
                {h.is_hotspot && <Badge variant="outdated">Hot</Badge>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
