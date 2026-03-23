import { GitCommit, User } from "lucide-react";
import { formatRelativeTime, truncatePath } from "@/lib/utils/format";
import type { GitMetadataResponse } from "@/lib/api/types";

interface GitHistoryPanelProps {
  git: GitMetadataResponse;
}

function AuthorAvatar({ name }: { name: string }) {
  const initials = name
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");

  // Deterministic color from name
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  const colors = [
    "bg-blue-500", "bg-purple-500", "bg-green-500", "bg-yellow-500",
    "bg-pink-500", "bg-indigo-500", "bg-teal-500", "bg-orange-500",
  ];
  const color = colors[Math.abs(hash) % colors.length];

  return (
    <div
      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-semibold text-white ${color}`}
      aria-label={name}
      title={name}
    >
      {initials || <User className="h-3 w-3" />}
    </div>
  );
}

export function GitHistoryPanel({ git }: GitHistoryPanelProps) {
  const commits = git.significant_commits ?? [];

  return (
    <div className="space-y-4">
      {/* Top authors */}
      {git.top_authors && git.top_authors.length > 0 && (
        <div>
          <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-2">
            Authors
          </p>
          <div className="space-y-1.5">
            {git.top_authors.slice(0, 4).map((author) => (
              <div key={author.email} className="flex items-center gap-2 text-xs">
                <AuthorAvatar name={author.name} />
                <span className="flex-1 truncate text-[var(--color-text-secondary)]">
                  {author.name}
                </span>
                <span className="text-[var(--color-text-tertiary)] tabular-nums shrink-0">
                  {Math.round(author.pct * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent commits */}
      {commits.length > 0 && (
        <div>
          <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-2">
            Recent Commits
          </p>
          <ul className="space-y-2.5">
            {commits.slice(0, 6).map((commit) => (
              <li key={commit.sha} className="flex gap-2 min-w-0">
                <div className="flex flex-col items-center shrink-0">
                  <GitCommit className="h-3.5 w-3.5 text-[var(--color-text-tertiary)] mt-0.5" />
                  <div className="w-px flex-1 bg-[var(--color-border-default)] mt-1" />
                </div>
                <div className="min-w-0 pb-2">
                  <p className="text-xs text-[var(--color-text-secondary)] leading-snug line-clamp-2 break-words">
                    {commit.message}
                  </p>
                  <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                    <span className="font-mono text-[10px] text-[var(--color-accent-primary)]">
                      {commit.sha.slice(0, 7)}
                    </span>
                    <span className="text-[10px] text-[var(--color-text-tertiary)] truncate max-w-[80px]">
                      {commit.author}
                    </span>
                    <span className="text-[10px] text-[var(--color-text-tertiary)]">
                      {formatRelativeTime(commit.date)}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {commits.length === 0 && (
        <p className="text-xs text-[var(--color-text-tertiary)]">No commit history available.</p>
      )}
    </div>
  );
}
