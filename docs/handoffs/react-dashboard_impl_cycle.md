# Handoff Cycle: React Dashboard — Implementation Review

- **Phase:** react-dashboard
- **Type:** impl
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/react-dashboard.md](../phases/react-dashboard.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Implementation of Phase 5 (React Dashboard) complete. All files created per the approved plan.

**Project config (`frontend/`):**
- `package.json` — React 18, React Router 6, TanStack Query 5, D3 7, Recharts 2, Tailwind 3, Vitest 2, Testing Library
- `tsconfig.json` — strict TypeScript, ES2020 target, `react-jsx`
- `vite.config.ts` — conditional `base`: `"/static/"` for build, `"/"` for dev. Proxy `/api` to Django `:8000`. Vitest config with jsdom + setup file.
- `tailwind.config.js` — content paths for all TSX files
- `postcss.config.js` — tailwindcss + autoprefixer
- `index.html` — minimal entry point

**Source files (`frontend/src/`):**
- `main.tsx` — React entry: `StrictMode`, `QueryClientProvider` (30s staleTime, 1 retry), `BrowserRouter`, renders `App`
- `App.tsx` — Routes: Layout wrapping 5 page routes (`/`, `/search`, `/graph`, `/analytics`, `/settings`)
- `index.css` — Tailwind directives

**Types (`src/types/index.ts`):**
- `Memory`, `CreateMemoryRequest`, `UpdateMemoryRequest`, `SearchRequest`, `SearchResult` (with `rrf_score`), `Stats`, `TagCount`, `HealthStatus` — matching REST API serializer shapes

**API Client (`src/api/client.ts`):**
- `getCsrfToken()` reads `csrftoken` cookie from `document.cookie`
- `request<T>()` includes `credentials: "same-origin"`, `X-CSRFToken` on unsafe methods, JSON Content-Type
- `api` object: `health`, `listMemories`, `getMemory`, `createMemory`, `updateMemory`, `deleteMemory`, `search`, `stats`, `tags`

**Components (`src/components/`):**
- `Layout.tsx` — sidebar nav with 5 text links, responsive (collapses to hamburger on mobile), `Outlet` for page content. `NavLink` with `end` prop on Home to avoid always-active.
- `MemoryCard.tsx` — truncated content (200 chars), source badge, `TagBadge` chips, importance/views/date row, Edit/Delete buttons. Edit toggles inline `MemoryForm`. Delete uses `window.confirm` + mutation.
- `MemoryForm.tsx` — controlled form: textarea (content), text input (tags, comma-separated), range slider (importance 0-1), source input (create only). Handles both create and update via separate mutations with query invalidation.
- `SearchFilters.tsx` — collapsible panel: semantic weight slider (Keyword <-> Semantic), tag chips from `/api/tags/` (toggleable, active = blue-600), source dropdown from stats, date range inputs.
- `TagBadge.tsx` — pill chip with optional click handler.

**Pages (`src/pages/`):**
- `HomePage.tsx` — `useQuery(["memories"])`, `MemoryForm` at top, `MemoryCard` feed, loading/error/empty states.
- `SearchPage.tsx` — debounced query (300ms), `SearchFilters`, `useQuery(["search", request])` enabled when query non-empty. Results as `MemoryCard` with `showScore`. Tag click adds to filter.
- `GraphPage.tsx` — D3.js force-directed: `buildGraphData()` computes nodes (sized by importance, colored by source) and links (shared tags, weighted). `d3.forceSimulation` with link/charge/center forces. Zoom, drag, click-to-select, title tooltips. Side panel shows memory detail. Cleanup on unmount (`simulation.stop()`).
- `AnalyticsPage.tsx` — Summary cards (total, sources, date range). Recharts `PieChart` (source distribution with `Cell` colors) and `BarChart` (top 10 tags).
- `SettingsPage.tsx` — Health status with green/red indicators (30s refetch), system info (total memories, sources), Swagger UI link.

**Tests (`src/__tests__/`):**
- `setup.ts` — imports `@testing-library/jest-dom/vitest`
- `client.test.ts` — 4 tests: `listMemories` returns array, `createMemory` sends POST with `X-CSRFToken` and `credentials: "same-origin"`, `deleteMemory` returns void on 204, error handling throws on non-OK response.
- `MemoryCard.test.tsx` — 6 tests: renders content, source badge, tags, importance/views, rrf_score when provided, edit/delete buttons. Uses `QueryClientProvider` wrapper.

**Django integration:**
- `openbrain/views.py` — `FrontendView(TemplateView)` serving `index.html`
- `openbrain/urls.py` — added `re_path(r"^(?!api/|admin/|static/).*$", FrontendView)` catch-all after API routes
- `openbrain/settings/base.py` — added `BASE_DIR / "frontend" / "dist"` to both `TEMPLATES.DIRS` and `STATICFILES_DIRS`

### Reviewer

**Action:** REQUEST_CHANGES

Implementation coverage is good, but there are blocking verification and routing issues that must be fixed before approval.

**Blocking issues:**
1. Frontend tests fail (`npm --prefix frontend run test`) with 4 failing `MemoryCard` tests because previous renders remain in the DOM, causing `getByText(...)` to match multiple elements.
   - Assertions failing in [frontend/src/__tests__/MemoryCard.test.tsx](/Users/jackblacketter/projects/openbrain/frontend/src/__tests__/MemoryCard.test.tsx:42), [frontend/src/__tests__/MemoryCard.test.tsx](/Users/jackblacketter/projects/openbrain/frontend/src/__tests__/MemoryCard.test.tsx:47), [frontend/src/__tests__/MemoryCard.test.tsx](/Users/jackblacketter/projects/openbrain/frontend/src/__tests__/MemoryCard.test.tsx:53), [frontend/src/__tests__/MemoryCard.test.tsx](/Users/jackblacketter/projects/openbrain/frontend/src/__tests__/MemoryCard.test.tsx:66)
   - Setup currently only imports jest-dom in [frontend/src/__tests__/setup.ts](/Users/jackblacketter/projects/openbrain/frontend/src/__tests__/setup.ts:1), with no cleanup hook.
2. Frontend build fails (`npm --prefix frontend run build`) with a TypeScript error in the D3 drag call typing.
   - Failing code in [frontend/src/pages/GraphPage.tsx](/Users/jackblacketter/projects/openbrain/frontend/src/pages/GraphPage.tsx:110)
3. SPA catch-all route regex still captures bare namespace paths (`/api`, `/admin`, `/static`) because the negative lookahead only excludes `api/|admin/|static/`.
   - Regex in [openbrain/urls.py](/Users/jackblacketter/projects/openbrain/openbrain/urls.py:13)
   - Example: current pattern matches `api` but should not.

**Required changes:**
1. Add deterministic RTL cleanup between tests (e.g., `afterEach(cleanup)` in setup) or otherwise ensure no render leakage across test cases, then re-run frontend tests.
2. Fix `GraphPage` D3 typing so TypeScript build passes cleanly.
3. Update catch-all regex to exclude both bare and slash-prefixed API/admin/static roots (for example, `^(?!(api|admin|static)(/|$)).*$`).
4. Re-run and report:
   - `npm --prefix frontend run test`
   - `npm --prefix frontend run build`

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

All 3 blocking issues fixed:

1. **Test cleanup** (`frontend/src/__tests__/setup.ts`): Added `import { cleanup } from "@testing-library/react"` and `afterEach(cleanup)` so RTL cleans up the DOM between every test case. All 10 tests now pass (6 MemoryCard + 4 client).

2. **D3 drag typing** (`frontend/src/pages/GraphPage.tsx:100`): Changed `g.selectAll("circle")` to `g.selectAll<SVGCircleElement, GraphNode>("circle")` so the selection carries the correct element and datum types, making `.call(d3.drag<SVGCircleElement, GraphNode>())` type-compatible. TypeScript build now passes cleanly.

3. **SPA catch-all regex** (`openbrain/urls.py:13`): Updated from `r"^(?!api/|admin/|static/).*$"` to `r"^(?!(api|admin|static)(/|$)).*$"` so both bare paths (`/api`) and slash-prefixed paths (`/api/...`) are excluded from the catch-all.

**Verification output:**
- `npm --prefix frontend run test` — 2 files, 10 tests passed, 0 failures
- `npm --prefix frontend run build` — `tsc` clean, Vite build succeeds (dist/index.html + assets)

### Reviewer

**Action:** APPROVE

Approved. All round-1 blockers are resolved and verified:
- Test isolation fixed via cleanup hook in [frontend/src/__tests__/setup.ts](/Users/jackblacketter/projects/openbrain/frontend/src/__tests__/setup.ts:1), and frontend test suite now passes (`10/10`).
- D3 typing issue fixed in [frontend/src/pages/GraphPage.tsx](/Users/jackblacketter/projects/openbrain/frontend/src/pages/GraphPage.tsx:101), and frontend build now succeeds.
- SPA catch-all regex fixed in [openbrain/urls.py](/Users/jackblacketter/projects/openbrain/openbrain/urls.py:13); bare and slash-prefixed `api/admin/static` roots are excluded correctly.

Verification run:
- `npm --prefix frontend run test` ✅
- `npm --prefix frontend run build` ✅

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 2
STATE: approved
```
