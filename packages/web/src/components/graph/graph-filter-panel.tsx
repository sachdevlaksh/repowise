"use client";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils/cn";
import { LANGUAGE_COLORS } from "@/lib/utils/confidence";

export type ColorBy = "language" | "community" | "entry_point";
export type SizeBy = "symbol_count" | "pagerank" | "betweenness";

export interface GraphFilters {
  hiddenLangs: Set<string>;
  hideTests: boolean;
  colorBy: ColorBy;
  sizeBy: SizeBy;
  nodeSearch: string;
}

interface GraphFilterPanelProps {
  filters: GraphFilters;
  onChange: (filters: GraphFilters) => void;
  availableLangs: string[];
}

export function GraphFilterPanel({ filters, onChange, availableLangs }: GraphFilterPanelProps) {
  const update = (patch: Partial<GraphFilters>) => onChange({ ...filters, ...patch });

  const toggleLang = (lang: string) => {
    const next = new Set(filters.hiddenLangs);
    if (next.has(lang)) next.delete(lang);
    else next.add(lang);
    update({ hiddenLangs: next });
  };

  return (
    <div className="w-52 rounded-lg border border-[var(--color-border-default)] bg-[var(--color-bg-overlay)] p-3 shadow-lg space-y-4 text-xs">
      <div>
        <p className="font-semibold text-[var(--color-text-primary)] mb-2 uppercase tracking-wider text-[10px]">
          Node Search
        </p>
        <Input
          value={filters.nodeSearch}
          onChange={(e) => update({ nodeSearch: e.target.value })}
          placeholder="Highlight nodes…"
          className="h-7 text-xs"
        />
      </div>

      <div>
        <p className="font-semibold text-[var(--color-text-primary)] mb-2 uppercase tracking-wider text-[10px]">
          Languages
        </p>
        <div className="space-y-1">
          {availableLangs.map((lang) => {
            const hidden = filters.hiddenLangs.has(lang);
            return (
              <label key={lang} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={!hidden}
                  onChange={() => toggleLang(lang)}
                  className="rounded border-[var(--color-border-default)]"
                />
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{
                    background:
                      LANGUAGE_COLORS[lang.toLowerCase()] ?? LANGUAGE_COLORS.other,
                  }}
                />
                <span className="text-[var(--color-text-secondary)] capitalize">{lang}</span>
              </label>
            );
          })}
        </div>
      </div>

      <label className="flex items-center gap-2 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={filters.hideTests}
          onChange={(e) => update({ hideTests: e.target.checked })}
          className="rounded border-[var(--color-border-default)]"
        />
        <span className="text-[var(--color-text-secondary)]">Hide test files</span>
      </label>

      <div>
        <p className="font-semibold text-[var(--color-text-primary)] mb-2 uppercase tracking-wider text-[10px]">
          Color By
        </p>
        <div className="space-y-1">
          {(["language", "community", "entry_point"] as ColorBy[]).map((v) => (
            <label key={v} className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="radio"
                checked={filters.colorBy === v}
                onChange={() => update({ colorBy: v })}
                name="colorBy"
                className="border-[var(--color-border-default)]"
              />
              <span className="text-[var(--color-text-secondary)] capitalize">
                {v.replace(/_/g, " ")}
              </span>
            </label>
          ))}
        </div>
      </div>

      <div>
        <p className="font-semibold text-[var(--color-text-primary)] mb-2 uppercase tracking-wider text-[10px]">
          Size By
        </p>
        <div className="space-y-1">
          {(["symbol_count", "pagerank", "betweenness"] as SizeBy[]).map((v) => (
            <label key={v} className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="radio"
                checked={filters.sizeBy === v}
                onChange={() => update({ sizeBy: v })}
                name="sizeBy"
                className="border-[var(--color-border-default)]"
              />
              <span className="text-[var(--color-text-secondary)] capitalize">
                {v.replace(/_/g, " ")}
              </span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
