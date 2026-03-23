"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/utils/cn";

interface GraphMinimapProps {
  className?: string;
}

export const GraphMinimap = forwardRef<HTMLCanvasElement, GraphMinimapProps>(
  ({ className }, ref) => {
    return (
      <canvas
        ref={ref}
        width={160}
        height={120}
        className={cn(
          "rounded-lg border border-[var(--color-border-default)] bg-[var(--color-bg-surface)]",
          className,
        )}
      />
    );
  },
);
GraphMinimap.displayName = "GraphMinimap";
