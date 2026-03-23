import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { EmptyState } from "@/components/shared/empty-state";
import { truncatePath } from "@/lib/utils/format";
import type { OwnershipEntry } from "@/lib/api/types";

interface OwnershipTableProps {
  entries: OwnershipEntry[];
}

export function OwnershipTable({ entries }: OwnershipTableProps) {
  if (entries.length === 0) {
    return (
      <EmptyState
        title="No ownership data"
        description="Run a sync to populate ownership information."
      />
    );
  }

  return (
    <div className="rounded-lg border border-[var(--color-border-default)] overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border-default)] bg-[var(--color-bg-elevated)]">
            <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">
              Module / File
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">
              Owner
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider w-36">
              Ownership
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider w-16">
              Files
            </th>
            <th className="px-4 py-2.5 w-20" />
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr
              key={entry.module_path}
              className="border-b border-[var(--color-border-default)] hover:bg-[var(--color-bg-elevated)] transition-colors last:border-0"
            >
              <td className="px-4 py-2.5 font-mono text-xs text-[var(--color-text-primary)] max-w-xs truncate">
                {truncatePath(entry.module_path, 60)}
              </td>
              <td className="px-4 py-2.5 text-xs text-[var(--color-text-secondary)]">
                {entry.primary_owner ?? "—"}
              </td>
              <td className="px-4 py-2.5">
                {entry.owner_pct !== null ? (
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 rounded-full bg-[var(--color-bg-elevated)]">
                      <div
                        className="h-1.5 rounded-full bg-[var(--color-accent-primary)]"
                        style={{ width: `${Math.min(100, entry.owner_pct * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-[var(--color-text-tertiary)] tabular-nums w-8">
                      {Math.round(entry.owner_pct * 100)}%
                    </span>
                  </div>
                ) : (
                  <span className="text-[var(--color-text-tertiary)]">—</span>
                )}
              </td>
              <td className="px-4 py-2.5 text-xs text-[var(--color-text-tertiary)] tabular-nums">
                {entry.file_count}
              </td>
              <td className="px-4 py-2.5">
                {entry.is_silo && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <Badge variant="stale">Silo</Badge>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>Bus factor risk</TooltipContent>
                  </Tooltip>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
