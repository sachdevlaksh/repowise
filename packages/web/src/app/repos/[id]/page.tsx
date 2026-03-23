import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  FileText,
  Clock,
  Hash,
  Code2,
  AlertTriangle,
  Network,
  BookOpen,
  Flame,
  Target,
  TrendingDown,
} from "lucide-react";
import { getRepo, getRepoStats } from "@/lib/api/repos";
import { listPages } from "@/lib/api/pages";
import { listDeadCode } from "@/lib/api/dead-code";
import { getHotspots } from "@/lib/api/git";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { StatCard } from "@/components/shared/stat-card";
import { OperationsPanel } from "@/components/repos/operations-panel";
import { formatNumber } from "@/lib/utils/format";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  try {
    const repo = await getRepo(id);
    return { title: repo.name };
  } catch {
    return { title: "Repository" };
  }
}

export default async function RepoOverviewPage({ params }: Props) {
  const { id } = await params;

  let repo;
  try {
    repo = await getRepo(id);
  } catch {
    notFound();
  }

  const [statsResult, lowConfPagesResult, deadExportsResult, hotspotsResult] =
    await Promise.allSettled([
      getRepoStats(id),
      listPages(id, { sort_by: "confidence", order: "asc", limit: 5 }),
      listDeadCode(id, { kind: "unused_export", limit: 5 }),
      getHotspots(id, 5),
    ]);

  const stats = statsResult.status === "fulfilled" ? statsResult.value : null;
  const lowConfPages = lowConfPagesResult.status === "fulfilled" ? lowConfPagesResult.value : [];
  const deadExports = deadExportsResult.status === "fulfilled" ? deadExportsResult.value : [];
  const hotspots = hotspotsResult.status === "fulfilled" ? hotspotsResult.value : [];

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
            {repo.name}
          </h1>
          <p className="text-xs font-mono text-[var(--color-text-tertiary)] mt-0.5">
            {repo.local_path}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {repo.head_commit && (
            <Badge variant="outline">
              <Hash className="h-3 w-3" />
              {repo.head_commit.slice(0, 7)}
            </Badge>
          )}
          <Badge variant="outline">{repo.default_branch}</Badge>
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard
          label="Files"
          value={stats ? formatNumber(stats.file_count) : "—"}
          icon={<FileText className="h-4 w-4" />}
        />
        <StatCard
          label="Symbols"
          value={stats ? formatNumber(stats.symbol_count) : "—"}
          icon={<Code2 className="h-4 w-4" />}
        />
        <StatCard
          label="Entry Points"
          value={stats ? formatNumber(stats.entry_point_count) : "—"}
          icon={<Target className="h-4 w-4" />}
        />
        <StatCard
          label="Doc Coverage"
          value={stats ? `${stats.doc_coverage_pct.toFixed(0)}%` : "—"}
          icon={<BookOpen className="h-4 w-4" />}
        />
        <StatCard
          label="Freshness"
          value={stats ? `${stats.freshness_score.toFixed(0)}%` : "—"}
          icon={<Clock className="h-4 w-4" />}
        />
        <StatCard
          label="Dead Exports"
          value={stats ? formatNumber(stats.dead_export_count) : "—"}
          icon={<TrendingDown className="h-4 w-4" />}
        />
      </div>

      {/* Operations panel */}
      <OperationsPanel repoId={id} repoName={repo.name} />

      {/* Two-column content */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Left: Needs Attention */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-400" />
                Needs Attention
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Low confidence pages */}
              <div>
                <p className="text-xs text-[var(--color-text-tertiary)] mb-2 uppercase tracking-wider font-medium">
                  Low-confidence docs
                </p>
                {lowConfPages.length === 0 ? (
                  <p className="text-xs text-[var(--color-text-secondary)]">All pages look good.</p>
                ) : (
                  <div className="space-y-1">
                    {lowConfPages.map((page) => (
                      <Link
                        key={page.id}
                        href={`/repos/${id}/wiki/${encodeURIComponent(page.target_path)}`}
                        className="flex items-center justify-between py-1 px-2 rounded hover:bg-[var(--color-bg-elevated)] group transition-colors"
                      >
                        <span className="font-mono text-xs text-[var(--color-text-secondary)] group-hover:text-[var(--color-text-primary)] truncate">
                          {page.target_path}
                        </span>
                        <span
                          className="ml-2 shrink-0 text-xs tabular-nums font-medium"
                          style={{
                            color: page.confidence < 0.5 ? "#ef4444" : "#f59e0b",
                          }}
                        >
                          {(page.confidence * 100).toFixed(0)}%
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              {/* Dead exports */}
              <div>
                <p className="text-xs text-[var(--color-text-tertiary)] mb-2 uppercase tracking-wider font-medium">
                  Unused exports
                </p>
                {deadExports.length === 0 ? (
                  <p className="text-xs text-[var(--color-text-secondary)]">No unused exports found.</p>
                ) : (
                  <div className="space-y-1">
                    {deadExports.map((finding) => (
                      <Link
                        key={finding.id}
                        href={`/repos/${id}/dead-code`}
                        className="flex items-center justify-between py-1 px-2 rounded hover:bg-[var(--color-bg-elevated)] group transition-colors"
                      >
                        <div className="flex-1 min-w-0">
                          <span className="font-mono text-xs text-[var(--color-text-secondary)] group-hover:text-[var(--color-text-primary)] truncate block">
                            {finding.file_path}
                          </span>
                          {finding.symbol_name && (
                            <span className="font-mono text-xs text-[var(--color-text-tertiary)]">
                              {finding.symbol_name}
                            </span>
                          )}
                        </div>
                        <span className="ml-2 shrink-0 text-xs tabular-nums text-[var(--color-text-tertiary)]">
                          {(finding.confidence * 100).toFixed(0)}%
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Most Active */}
        <div>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Flame className="h-4 w-4 text-orange-400" />
                Most Active (30d)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {hotspots.length === 0 ? (
                <p className="text-xs text-[var(--color-text-secondary)]">
                  No git activity data yet.
                </p>
              ) : (
                <div className="space-y-1">
                  {hotspots.map((hs) => (
                    <div
                      key={hs.file_path}
                      className="flex items-center justify-between py-1 px-2 rounded"
                    >
                      <div className="flex-1 min-w-0">
                        <span className="font-mono text-xs text-[var(--color-text-secondary)] truncate block">
                          {hs.file_path}
                        </span>
                        {hs.primary_owner && (
                          <span className="text-xs text-[var(--color-text-tertiary)]">
                            {hs.primary_owner}
                          </span>
                        )}
                      </div>
                      <div className="ml-2 shrink-0 text-right">
                        <span className="text-xs tabular-nums font-medium text-[var(--color-text-primary)]">
                          {hs.commit_count_90d}
                        </span>
                        <span className="text-xs text-[var(--color-text-tertiary)] ml-1">commits</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* CTA buttons */}
      <div className="flex flex-wrap gap-3">
        <Button asChild>
          <Link href={`/repos/${id}/graph`}>
            <Network className="h-4 w-4 mr-2" />
            Explore Graph →
          </Link>
        </Button>
        <Button variant="secondary" asChild>
          <Link href={`/repos/${id}/dead-code`}>
            <TrendingDown className="h-4 w-4 mr-2" />
            View Dead Code →
          </Link>
        </Button>
        <Button variant="secondary" asChild>
          <Link href={`/repos/${id}/wiki`}>
            <BookOpen className="h-4 w-4 mr-2" />
            Browse Docs →
          </Link>
        </Button>
      </div>
    </div>
  );
}
