import * as React from "react";
import { cn } from "@/lib/utils/cn";
import { Card, CardContent } from "@/components/ui/card";

interface StatCardProps {
  label: string;
  value: string | number;
  description?: string;
  trend?: { value: string; positive: boolean };
  icon?: React.ReactNode;
  className?: string;
  href?: string;
}

export function StatCard({
  label,
  value,
  description,
  icon,
  className,
}: StatCardProps) {
  return (
    <Card className={cn("transition-colors hover:border-[var(--color-border-hover)]", className)}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider">
              {label}
            </p>
            <p className="text-2xl font-bold text-[var(--color-text-primary)] tabular-nums">
              {value}
            </p>
            {description && (
              <p className="text-xs text-[var(--color-text-secondary)]">{description}</p>
            )}
          </div>
          {icon && (
            <div className="rounded-md bg-[var(--color-bg-elevated)] p-2 text-[var(--color-text-secondary)]">
              {icon}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
