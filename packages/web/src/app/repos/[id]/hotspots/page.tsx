import type { Metadata } from "next";
import { Flame } from "lucide-react";
import { StatCard } from "@/components/shared/stat-card";
import { HotspotTable } from "@/components/git/hotspot-table";
import { ContributorBar } from "@/components/git/contributor-bar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getHotspots, getGitSummary } from "@/lib/api/git";
import { formatNumber } from "@/lib/utils/format";

export const metadata: Metadata = { title: "Hotspots" };

export default async function HotspotsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let hotspots: Awaited<ReturnType<typeof getHotspots>> = [];
  let summary: Awaited<ReturnType<typeof getGitSummary>> | null = null;

  try {
    [hotspots, summary] = await Promise.all([
      getHotspots(id, 50),
      getGitSummary(id),
    ]);
  } catch {
    // API unavailable
  }

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-6xl">
      <div>
        <h1 className="text-xl font-semibold text-[var(--color-text-primary)] mb-1 flex items-center gap-2">
          <Flame className="h-5 w-5 text-red-500" />
          Hotspots
        </h1>
        <p className="text-sm text-[var(--color-text-secondary)]">
          High-churn files — where the most risky code lives.
        </p>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            label="Hotspot Files"
            value={formatNumber(summary.hotspot_count)}
            description="high-churn files"
          />
          <StatCard
            label="Stable Files"
            value={formatNumber(summary.stable_count)}
            description="low-churn files"
          />
          <StatCard
            label="Total Files"
            value={formatNumber(summary.total_files)}
            description="with git history"
          />
          <StatCard
            label="Avg Churn"
            value={`${Math.round(summary.average_churn_percentile)}%`}
            description="percentile"
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <HotspotTable hotspots={hotspots} />
        </div>

        {/* Top owners leaderboard */}
        {summary && summary.top_owners.length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Top Owners</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <ContributorBar owners={summary.top_owners} />
              <div className="mt-3 space-y-1.5">
                {summary.top_owners.slice(0, 5).map((o) => (
                  <div key={o.email || `owner-${o.name}`} className="flex items-center justify-between text-xs">
                    <span className="text-[var(--color-text-secondary)] truncate">{o.name}</span>
                    <span className="text-[var(--color-text-tertiary)] tabular-nums ml-2">
                      {formatNumber(o.file_count)} files ({Math.round(o.pct * 100)}%)
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
