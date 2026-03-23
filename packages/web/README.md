# WikiCode Web UI

Next.js 15 frontend for the WikiCode codebase documentation engine. Displays AI-generated wiki pages, dependency graphs, symbol indexes, git analytics, and dead code analysis for any indexed codebase.

**Stack:** Next.js 15 (App Router) · Tailwind CSS v4 · Radix UI · SWR · D3.js · Shiki · Framer Motion

---

## File Map

### Config & Root

| File | Purpose |
|------|---------|
| `package.json` | Dependencies: Next.js 15, React 19, Tailwind v4, all Radix UI packages, SWR, D3, Shiki, Framer Motion, cmdk |
| `tsconfig.json` | Strict TypeScript, `@/*` path alias → `./src/*` |
| `next.config.ts` | Standalone output, `/api/*` proxy rewrite to `WIKICODE_API_URL`, `optimizePackageImports` |
| `postcss.config.mjs` | `@tailwindcss/postcss` plugin (Tailwind v4 CSS-first — no `tailwind.config.ts`) |
| `.gitignore` | Standard Next.js ignores |

### Styles

| File | Purpose |
|------|---------|
| `src/styles/globals.css` | Full design system — `@import "tailwindcss"` + `@theme {}` block with all CSS variables: surfaces (`--bg-base`, `--bg-surface`, `--bg-elevated`), borders, text, accent blue (`#5B9CF6`), confidence colors (fresh/stale/outdated), language colors, edge colors, typography scale, spacing, radii, z-index, animation easing. Also: prose overrides for wiki MDX content. |

### API Client (`src/lib/api/`)

| File | Purpose |
|------|---------|
| `types.ts` | All TypeScript interfaces mirroring backend schemas: `RepoResponse`, `PageResponse`, `PageVersionResponse`, `JobResponse`, `JobProgressEvent`, `SearchResultResponse`, `SymbolResponse`, `GraphExportResponse`, `GitMetadataResponse`, `HotspotResponse`, `OwnershipEntry`, `DeadCodeFindingResponse`, `HealthResponse`, `WebhookResponse`, `ApiError` |
| `client.ts` | Base fetch wrapper — `apiGet`, `apiPost`, `apiPatch`. Reads API key from `localStorage` (browser) or `WIKICODE_API_KEY` env var (server). Throws `ApiClientError` with status code on failures. |
| `repos.ts` | `listRepos`, `getRepo`, `createRepo`, `updateRepo`, `syncRepo`, `fullResyncRepo` |
| `pages.ts` | `listPages`, `getPageById` (uses `/api/pages/lookup?page_id=`), `getPageVersions`, `regeneratePage` |
| `search.ts` | `search` — supports `fts`, `semantic`, `hybrid` search types |
| `jobs.ts` | `listJobs`, `getJob`, `getJobStreamUrl` |
| `symbols.ts` | `listSymbols`, `lookupSymbolByName`, `getSymbolById` |
| `graph.ts` | `getGraph`, `getGraphPath` |
| `git.ts` | `getGitMetadata`, `getHotspots`, `getOwnership`, `getCoChanges`, `getGitSummary` |
| `dead-code.ts` | `listDeadCode`, `analyzeDeadCode`, `getDeadCodeSummary`, `patchDeadCodeFinding` |
| `health.ts` | `getHealth` |

### Hooks (`src/lib/hooks/`)

| File | Purpose |
|------|---------|
| `use-repo.ts` | `useRepos`, `useRepo` — SWR hooks with 30s background refresh |
| `use-page.ts` | `usePage`, `usePageVersions` — SWR hooks for wiki page data |
| `use-search.ts` | `useSearch` — debounced search (300ms), min 2 chars, SWR |
| `use-debounce.ts` | Generic debounce hook |
| `use-sse.ts` | SSE hook for job progress — named event handlers (progress/done/error), auto-reconnect with exponential backoff, max retries |
| `use-graph.ts` | `useGraph` — SWR with no revalidate on focus/reconnect (graph data is stable) |

### Utilities (`src/lib/utils/`)

| File | Purpose |
|------|---------|
| `cn.ts` | `cn()` — `clsx` + `tailwind-merge` combinator |
| `format.ts` | `formatNumber`, `formatTokens`, `formatCost`, `formatRelativeTime`, `formatDate`, `formatDateTime`, `formatLOC`, `truncatePath`, `formatConfidence`, `formatProgress` |
| `confidence.ts` | `FreshnessStatus` type, `scoreToStatus`, `statusColor`, `statusTextClass`, `statusBadgeClasses`, `statusLabel`, `LANGUAGE_COLORS`, `languageColor`, `EDGE_COLORS`, `edgeColor` |

### UI Primitives (`src/components/ui/`)

All built on Radix UI with WikiCode design tokens:

| File | Component |
|------|-----------|
| `button.tsx` | CVA variants: default/destructive/outline/secondary/ghost/link × sm/md/lg/icon sizes |
| `badge.tsx` | CVA variants: default/fresh/stale/outdated/accent/outline |
| `card.tsx` | `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter` |
| `separator.tsx` | Radix Separator |
| `input.tsx` | Styled text input |
| `skeleton.tsx` | `animate-pulse` loading skeleton |
| `tabs.tsx` | Radix Tabs |
| `tooltip.tsx` | Radix Tooltip with portal |
| `dialog.tsx` | Radix Dialog with overlay and close button |
| `scroll-area.tsx` | Radix ScrollArea with styled scrollbar |
| `select.tsx` | Full Radix Select with all sub-components |

### Shared Components (`src/components/shared/`)

| File | Component |
|------|-----------|
| `stat-card.tsx` | Dashboard stat card — label, value, description, optional icon |
| `empty-state.tsx` | Empty state — icon, title, description, optional action button |

### Wiki Components (`src/components/wiki/`)

| File | Component |
|------|-----------|
| `confidence-badge.tsx` | Freshness badge — fresh/stale/outdated states, animated pulse on stale, tooltip with date |

### Layout (`src/components/layout/`)

| File | Component |
|------|-----------|
| `sidebar.tsx` | Global sidebar — WikiCode logo, nav links (Dashboard, Settings), collapsible per-repo tree with all wiki pages, active state highlighting |

### Pages (`src/app/`)

| Route | File | Status |
|-------|------|--------|
| `/` | `page.tsx` | **Built** — stat cards, repo list, recent jobs |
| `layout.tsx` | Root layout | **Built** — Geist fonts, TooltipProvider, sidebar |
| `/repos/[id]` | `repos/[id]/page.tsx` | **Built** — git stats, head commit, overview content |
| `/repos/[id]/layout.tsx` | Repo layout | **Built** |
| `/repos/[id]/wiki/[...slug]` | `wiki/[...slug]/page.tsx` | **Built** — MDX pipeline with Shiki highlighting, Mermaid diagrams, sticky ToC, regenerate button |
| `/repos/[id]/search` | `search/page.tsx` | **Built** — debounce, type toggle, cmdk palette, result cards |
| `/repos/[id]/graph` | `graph/page.tsx` | **Built** — D3 canvas, zoom/pan, tooltips, filter panel, minimap |
| `/repos/[id]/symbols` | `symbols/page.tsx` | **Built** — sortable table, kind/language filters, detail drawer |
| `/repos/[id]/coverage` | `coverage/page.tsx` | **Built** — donut chart, freshness table, per-file regenerate |
| `/repos/[id]/ownership` | `ownership/page.tsx` | **Built** — granularity toggle, silo badges, contributor chart |
| `/repos/[id]/hotspots` | `hotspots/page.tsx` | **Built** — ranked table, churn bars, owner leaderboard |
| `/repos/[id]/dead-code` | `dead-code/page.tsx` | **Built** — tabs, row actions, bulk select, analyze trigger |
| `/settings` | `settings/page.tsx` | **Built** — connection, provider, webhook, MCP sections |

---

## Development

```powershell
# From repo root
$env:WIKICODE_API_URL = "http://localhost:7337"
npm run dev --workspace packages/web
# Open http://localhost:3000
```

Requires the WikiCode API server running on port 7337. See `TESTING_GUIDE.md` in the repo root.

```powershell
# Type check
npm run type-check --workspace packages/web

# Lint
npm run lint --workspace packages/web
```

---

## Architecture Notes

**Server vs Client components:** Default to RSC. Add `"use client"` only for interactivity (D3, command palette, SSE hooks, form state). Data fetching in RSC via direct `apiGet()` calls; client-side revalidation via SWR hooks.

**API proxy:** `next.config.ts` rewrites `/api/*` → `WIKICODE_API_URL/api/*` so the frontend never hard-codes the backend URL and CORS is handled at the proxy layer.

**Design tokens:** Everything uses CSS variables defined in `globals.css`. Changing the design means changing one file. No Tailwind config needed (v4 CSS-first).

**Embedder for search:** The backend uses `MockEmbedder` by default. Set `WIKICODE_EMBEDDER=gemini` when starting the server to activate real semantic search via `gemini-embedding-001`.
