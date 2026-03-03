# Phase 5: React Dashboard

## Summary

React + TypeScript + Vite frontend for browsing, searching, and visualizing memories. Consumes the REST API from Phase 4. Includes a D3.js knowledge graph, analytics charts, and full memory CRUD. Django serves the production build; Vite dev server proxies to Django in development.

## Scope

- Vite + React 18 + TypeScript + Tailwind CSS project in `frontend/`
- Typed API client for all REST API endpoints
- 5 pages: Home (recent feed + create), Search (filters + weight slider), Graph (D3.js force-directed), Analytics (charts from stats/tags), Settings (health + system info)
- TanStack Query for server state management
- React Router for client-side navigation
- D3.js force-directed knowledge graph (nodes = memories, edges = shared tags)
- Recharts for analytics charts (source distribution, top tags)
- Django integration: catch-all view serves `index.html` in production, `STATICFILES_DIRS` picks up built assets
- Vitest + React Testing Library tests for API client and key components

## Technical Approach

### Project Setup

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── vite.config.ts
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    │   └── client.ts
    ├── components/
    │   ├── Layout.tsx
    │   ├── MemoryCard.tsx
    │   ├── MemoryForm.tsx
    │   ├── SearchFilters.tsx
    │   └── TagBadge.tsx
    ├── pages/
    │   ├── HomePage.tsx
    │   ├── SearchPage.tsx
    │   ├── GraphPage.tsx
    │   ├── AnalyticsPage.tsx
    │   └── SettingsPage.tsx
    ├── types/
    │   └── index.ts
    └── __tests__/
        ├── client.test.ts
        └── MemoryCard.test.tsx
```

**Dependencies:**
- `react`, `react-dom` (^18)
- `react-router-dom` (^6)
- `@tanstack/react-query` (^5)
- `d3` (^7) + `@types/d3`
- `recharts` (^2)
- `tailwindcss`, `postcss`, `autoprefixer`
- Dev: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`

### Vite Config

```typescript
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "build" ? "/static/" : "/",
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
}));
```

**Dev mode:** `base: "/"` — Vite serves its own assets directly. The proxy forwards `/api` to Django on `:8000`.

**Production build:** `base: "/static/"` — built `index.html` references assets at `/static/assets/main.<hash>.js`. Django's `STATIC_URL = "static/"` serves these via `STATICFILES_DIRS`.

### TypeScript Types (`src/types/index.ts`)

```typescript
export interface Memory {
  id: string;
  content: string;
  source: string;
  tags: string[];
  metadata: Record<string, unknown>;
  importance: number;
  decay_factor: number;
  access_count: number;
  last_accessed: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateMemoryRequest {
  content: string;
  source?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
  importance?: number;
}

export interface UpdateMemoryRequest {
  content?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
  importance?: number;
}

export interface SearchRequest {
  query: string;
  limit?: number;
  tags?: string[];
  source?: string;
  after?: string;
  before?: string;
  semantic_weight?: number;
}

export interface SearchResult extends Pick<Memory, "id" | "content" | "source" | "tags" | "metadata" | "importance" | "created_at" | "updated_at"> {
  rrf_score: number;
}

export interface Stats {
  total: number;
  by_source: Record<string, number>;
  top_tags: { tag: string; count: number }[];
  date_range: { earliest: string | null; latest: string | null } | null;
}

export interface TagCount {
  tag: string;
  count: number;
}

export interface HealthStatus {
  status: string;
  database: boolean;
}
```

### API Client (`src/api/client.ts`)

Typed `fetch` wrapper with CSRF token handling for session-authenticated writes.

```typescript
const API_BASE = "/api";

function getCsrfToken(): string {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : "";
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  // Include CSRF token for unsafe methods (required by SessionAuthentication)
  if (options?.method && options.method !== "GET") {
    headers["X-CSRFToken"] = getCsrfToken();
  }

  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "same-origin", // Include session + CSRF cookies
    headers: { ...headers, ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(error.error || error.detail || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  // Health
  health: () => request<HealthStatus>("/health/"),

  // Memories
  listMemories: () => request<Memory[]>("/memories/"),
  getMemory: (id: string) => request<Memory>(`/memories/${id}/`),
  createMemory: (data: CreateMemoryRequest) =>
    request<Memory>("/memories/", { method: "POST", body: JSON.stringify(data) }),
  updateMemory: (id: string, data: UpdateMemoryRequest) =>
    request<Memory>(`/memories/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteMemory: (id: string) =>
    request<void>(`/memories/${id}/`, { method: "DELETE" }),

  // Search
  search: (data: SearchRequest) =>
    request<SearchResult[]>("/search/", { method: "POST", body: JSON.stringify(data) }),

  // Stats & Tags
  stats: () => request<Stats>("/stats/"),
  tags: () => request<TagCount[]>("/tags/"),
};
```

**CSRF strategy:**
- `getCsrfToken()` reads the `csrftoken` cookie set by Django (CSRF_COOKIE_HTTPONLY defaults to `False`, so JS can read it)
- `X-CSRFToken` header is included on all unsafe methods (POST, PATCH, DELETE)
- `credentials: "same-origin"` ensures session and CSRF cookies are sent with every request
- DRF's `SessionAuthentication` enforces CSRF only for session-authenticated requests — API key auth (bearer token) bypasses CSRF, so this is only relevant for dashboard users logged in via Django
- In dev mode (AllowAny permission, no session), CSRF is not enforced

### State Management (TanStack Query)

Each page uses `useQuery` / `useMutation` hooks directly. No global store needed.

```typescript
// Example usage in a component:
const { data: memories, isLoading } = useQuery({
  queryKey: ["memories"],
  queryFn: api.listMemories,
});

const createMutation = useMutation({
  mutationFn: api.createMemory,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["memories"] }),
});
```

### Pages

**HomePage** (`src/pages/HomePage.tsx`):
- Shows recent memories from `GET /api/memories/` in a scrollable feed of `MemoryCard` components
- Inline `MemoryForm` at the top for quick memory creation via `POST /api/memories/`
- Auto-refreshes after successful create via TanStack Query invalidation

**SearchPage** (`src/pages/SearchPage.tsx`):
- Text input for search query
- `SearchFilters` panel: tag multi-select (populated from `GET /api/tags/`), source dropdown, date range pickers, semantic weight slider (0.0–1.0 range input)
- Results displayed as `MemoryCard` list with `rrf_score` badge
- Debounced search: fires `POST /api/search/` 300ms after user stops typing

**GraphPage** (`src/pages/GraphPage.tsx`):
- Fetches recent memories from `GET /api/memories/`
- Builds graph data client-side:
  - **Nodes:** Each memory is a node (sized by importance, colored by source)
  - **Links:** Two memories are linked if they share one or more tags (link weight = number of shared tags)
- D3.js force simulation rendered to SVG:
  - `d3.forceSimulation` with `forceLink`, `forceManyBody`, `forceCenter`
  - Drag-to-reposition nodes
  - Click node → shows memory detail in a side panel
  - Hover → tooltip with content preview
- React manages the container; D3 manages the SVG elements via `useRef` + `useEffect`

**AnalyticsPage** (`src/pages/AnalyticsPage.tsx`):
- Fetches data from `GET /api/stats/` and `GET /api/tags/`
- Summary cards: total memory count, source count, date range
- Recharts `PieChart`: source distribution (from `stats.by_source`)
- Recharts `BarChart`: top 10 tags (from `stats.top_tags`)

**SettingsPage** (`src/pages/SettingsPage.tsx`):
- Displays health status from `GET /api/health/` (status indicator, database connectivity)
- Shows API documentation link (`/api/docs/`)
- System info: memory count from stats

### Layout (`src/components/Layout.tsx`)

Persistent sidebar navigation with links to all 5 pages. Uses React Router's `<Outlet />` for page content. Responsive: sidebar collapses to hamburger menu on mobile.

### Key Components

**MemoryCard** (`src/components/MemoryCard.tsx`):
- Displays memory content (truncated), source badge, tags as `TagBadge` chips, importance meter, timestamps
- Click to expand full content
- Edit and delete buttons (inline edit via `MemoryForm`, delete with confirmation)

**MemoryForm** (`src/components/MemoryForm.tsx`):
- Controlled form for creating/editing memories
- Fields: content (textarea), tags (comma-separated input or tag chips), importance (range slider), source (text input, defaults to "dashboard")
- Validates content is non-empty, importance 0–1
- Submit calls `api.createMemory` or `api.updateMemory`

**SearchFilters** (`src/components/SearchFilters.tsx`):
- Collapsible filter panel
- Tag multi-select: fetches available tags from `GET /api/tags/`, rendered as clickable chips
- Source dropdown: options populated from stats `by_source` keys
- Date range: two date inputs for `after`/`before`
- Semantic weight slider: range input 0.0–1.0 with labels "Keyword" ↔ "Semantic"

**TagBadge** (`src/components/TagBadge.tsx`):
- Pill-shaped badge displaying a tag name
- Optional click handler (for filtering by tag)

### Django Integration (Production Serving)

In production, Django serves the Vite-built frontend:

1. `frontend/dist/index.html` — served by a catch-all Django view
2. `frontend/dist/assets/` — served as static files via Django's `STATIC_URL`

**Asset path alignment:** Vite builds with `base: "/static/"`, so `index.html` references `<script src="/static/assets/main.<hash>.js">`. Django's `STATIC_URL = "static/"` serves files from `STATICFILES_DIRS`, which includes `frontend/dist/` — so `assets/main.<hash>.js` maps to `/static/assets/main.<hash>.js`.

**Settings changes (`openbrain/settings/base.py`):**
```python
TEMPLATES = [
    {
        ...
        "DIRS": [BASE_DIR / "frontend" / "dist"],
        ...
    },
]

STATICFILES_DIRS = [
    BASE_DIR / "frontend" / "dist",
]
```

Note: `STATICFILES_DIRS` includes `frontend/dist` (not `frontend/dist/assets`) so that Django preserves the `assets/` subdirectory prefix matching Vite's output paths.

**Catch-all view (`openbrain/views.py`):**
```python
from django.views.generic import TemplateView

class FrontendView(TemplateView):
    template_name = "index.html"
```

**URL routing (`openbrain/urls.py`):**
```python
# After all API routes, catch-all for SPA routing:
re_path(r"^(?!api/|admin/|static/).*$", FrontendView.as_view(), name="frontend"),
```

The catch-all excludes `api/`, `admin/`, and `static/` prefixes — ensuring asset requests (`/static/assets/...`) are handled by Django's staticfiles, not the SPA fallback.

### Tailwind CSS

```javascript
// tailwind.config.js
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
};
```

Global styles in `src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### Test Suite

- `src/__tests__/client.test.ts` — API client tests with mocked `fetch`:
  - `listMemories` returns array, `createMemory` sends POST, `deleteMemory` returns void on 204, error handling on non-OK responses
- `src/__tests__/MemoryCard.test.tsx` — Component render tests:
  - Renders content, source, tags, timestamps
  - Delete button triggers confirmation + API call
- Test runner: Vitest with jsdom environment

## Files to Create/Modify

| Action | File | Description |
|--------|------|-------------|
| Create | `frontend/package.json` | Project dependencies and scripts |
| Create | `frontend/tsconfig.json` | TypeScript configuration |
| Create | `frontend/vite.config.ts` | Vite config with proxy |
| Create | `frontend/tailwind.config.js` | Tailwind content paths |
| Create | `frontend/postcss.config.js` | PostCSS with Tailwind plugin |
| Create | `frontend/index.html` | HTML entry point |
| Create | `frontend/src/main.tsx` | React entry with QueryClient + Router |
| Create | `frontend/src/App.tsx` | Route definitions |
| Create | `frontend/src/index.css` | Tailwind directives |
| Create | `frontend/src/types/index.ts` | TypeScript interfaces |
| Create | `frontend/src/api/client.ts` | Typed API client |
| Create | `frontend/src/components/Layout.tsx` | Sidebar nav + Outlet |
| Create | `frontend/src/components/MemoryCard.tsx` | Memory display card |
| Create | `frontend/src/components/MemoryForm.tsx` | Create/edit form |
| Create | `frontend/src/components/SearchFilters.tsx` | Search filter panel |
| Create | `frontend/src/components/TagBadge.tsx` | Tag badge chip |
| Create | `frontend/src/pages/HomePage.tsx` | Recent memories feed |
| Create | `frontend/src/pages/SearchPage.tsx` | Search + filters |
| Create | `frontend/src/pages/GraphPage.tsx` | D3.js knowledge graph |
| Create | `frontend/src/pages/AnalyticsPage.tsx` | Stats + charts |
| Create | `frontend/src/pages/SettingsPage.tsx` | Health + system info |
| Create | `frontend/src/__tests__/client.test.ts` | API client tests |
| Create | `frontend/src/__tests__/MemoryCard.test.tsx` | Component tests |
| Create | `openbrain/views.py` | FrontendView catch-all |
| Modify | `openbrain/urls.py` | Add catch-all for SPA routing |
| Modify | `openbrain/settings/base.py` | Add frontend/dist to TEMPLATES.DIRS and STATICFILES_DIRS, ensure CSRF_COOKIE_HTTPONLY=False |

## Success Criteria

1. `npm run dev` starts Vite dev server on `:5173` with hot reload
2. Home page loads and displays recent memories from the API
3. Creating a memory via the form adds it to the feed
4. Search page returns ranked results with working semantic weight slider
5. Tag, source, and date filters narrow search results
6. Knowledge graph renders memories as nodes with tag-based edges
7. Clicking a graph node shows memory detail
8. Analytics page shows source distribution pie chart and top tags bar chart
9. Settings page shows health status (green/red indicator)
10. Edit and delete memory actions work from MemoryCard
11. `npm run build` produces `frontend/dist/` with `index.html` referencing `/static/assets/...`
12. Django serves the built frontend at `/` in production mode
13. Production asset requests (`/static/assets/...`) load JS/CSS correctly (not caught by SPA fallback)
14. React Router handles client-side navigation (refresh on `/search` doesn't 404)
15. Secured-mode session-auth writes succeed (CSRF token sent via `X-CSRFToken` header)
16. API client tests pass with mocked fetch
17. MemoryCard component tests pass
