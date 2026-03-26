"use client";

import { use } from "react";
import { DocsExplorer } from "@/components/docs/docs-explorer";

export default function DocsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: repoId } = use(params);

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="shrink-0 px-4 sm:px-6 py-3 border-b border-[var(--color-border-default)]">
        <h1 className="text-lg font-semibold text-[var(--color-text-primary)]">
          Documentation
        </h1>
        <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
          Browse AI-generated documentation for every file, module, and symbol.
        </p>
      </div>

      {/* Explorer */}
      <div className="flex-1 min-h-0">
        <DocsExplorer repoId={repoId} />
      </div>
    </div>
  );
}
