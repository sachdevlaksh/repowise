"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { SymbolResponse } from "@/lib/api/types";

interface SymbolDrawerProps {
  symbol: SymbolResponse | null;
  onClose: () => void;
}

export function SymbolDrawer({ symbol, onClose }: SymbolDrawerProps) {
  return (
    <Dialog open={symbol !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        {symbol && (
          <>
            <DialogHeader>
              <DialogTitle className="font-mono text-base">{symbol.name}</DialogTitle>
              <DialogDescription className="font-mono text-xs text-[var(--color-text-tertiary)]">
                {symbol.file_path}:{symbol.start_line}
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-wrap gap-1.5 my-1">
              <Badge variant="accent">{symbol.kind}</Badge>
              <Badge variant="outline">{symbol.language}</Badge>
              {symbol.visibility && symbol.visibility !== "public" && (
                <Badge variant="default">{symbol.visibility}</Badge>
              )}
              {symbol.is_async && <Badge variant="default">async</Badge>}
              {symbol.complexity_estimate > 10 && (
                <Badge variant="stale">complexity {symbol.complexity_estimate}</Badge>
              )}
            </div>

            <ScrollArea className="max-h-64 rounded-md border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)]">
              <pre className="p-4 text-xs font-mono text-[var(--color-text-primary)] whitespace-pre-wrap break-all">
                <code>{symbol.signature || symbol.name}</code>
              </pre>
            </ScrollArea>

            {symbol.docstring && (
              <div className="rounded-md border border-[var(--color-border-default)] bg-[var(--color-bg-surface)] p-3">
                <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-1.5">
                  Docstring
                </p>
                <p className="text-sm text-[var(--color-text-secondary)] whitespace-pre-wrap">
                  {symbol.docstring}
                </p>
              </div>
            )}

            {symbol.parent_name && (
              <p className="text-xs text-[var(--color-text-tertiary)]">
                Parent: <span className="font-mono text-[var(--color-text-secondary)]">{symbol.parent_name}</span>
              </p>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
