# Handoff Cycle: React Dashboard — Plan Review

- **Phase:** react-dashboard
- **Type:** plan
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/react-dashboard.md](../phases/react-dashboard.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Submitting the Phase 5 (React Dashboard) plan for review. The plan covers:

- **Stack:** React 18 + TypeScript + Vite + Tailwind CSS in `frontend/`. Dependencies: React Router v6, TanStack Query v5, D3.js v7, Recharts v2.

- **API client** (`src/api/client.ts`): Typed `fetch` wrapper for all 8 REST API operations. Single `request<T>()` helper handles JSON parsing, error extraction, and 204 responses. All functions are typed with the interfaces from `src/types/index.ts`.

- **Vite proxy:** Dev server on `:5173` proxies `/api` to Django on `:8000` — eliminates CORS concerns in development. Production serves both from the same origin.

- **5 pages:**
  - **Home:** Recent memories feed from `GET /api/memories/`, inline `MemoryForm` for quick creation, TanStack Query auto-invalidation on create.
  - **Search:** Text input with debounced `POST /api/search/`, `SearchFilters` panel (tag multi-select from `/api/tags/`, source dropdown, date range, semantic weight slider 0–1), results with `rrf_score` badge.
  - **Graph:** D3.js force-directed layout. Nodes = memories (sized by importance, colored by source). Links = shared tags between memories (weight = tag overlap count). Interactive: drag, click-to-detail, hover tooltip. React manages container via `useRef`; D3 manages SVG.
  - **Analytics:** Summary cards (total count, source count, date range), Recharts PieChart (source distribution from `stats.by_source`), Recharts BarChart (top 10 tags from `stats.top_tags`).
  - **Settings:** Health status indicator from `GET /api/health/`, link to Swagger docs, memory count.

- **Layout:** Persistent sidebar navigation with React Router `<Outlet />`. Responsive: sidebar collapses to hamburger on mobile.

- **Components:** `MemoryCard` (truncated content, source badge, tag chips, importance meter, edit/delete), `MemoryForm` (textarea + tags + importance slider + source), `SearchFilters` (tag chips, source dropdown, date pickers, weight slider), `TagBadge` (pill chip with optional click handler).

- **Django integration (production):** Vite builds to `frontend/dist/`. Django's `TEMPLATES.DIRS` includes `frontend/dist/` to find `index.html`. `STATICFILES_DIRS` includes `frontend/dist/assets/` for JS/CSS bundles. Catch-all `FrontendView(TemplateView)` in `openbrain/views.py` serves `index.html` for all non-API/admin routes via `re_path`.

- **Tests:** Vitest + React Testing Library + jsdom. `client.test.ts` (API client with mocked fetch), `MemoryCard.test.tsx` (component render + interactions).

Please review `docs/phases/react-dashboard.md` for the full plan.

### Reviewer

**Action:** REQUEST_CHANGES

The plan is strong, but there are two blocking integration gaps that will break production behavior as written.

**Blocking issues:**
- **Vite asset URLs are not aligned with Django static serving.** The plan serves `frontend/dist/index.html` via Django and static files via `STATICFILES_DIRS` under `frontend/dist/assets/`, but Vite’s default production HTML references `/assets/...` paths. With the proposed catch-all route (`^(?!api/|admin/).*`), `/assets/...` requests can be routed to `index.html` instead of JS/CSS bundles, or otherwise miss Django’s `/static/` path.
- **Session-auth write flow is missing CSRF strategy.** The plan explicitly positions SessionAuthentication for the dashboard, but the API client helper only sends `Content-Type` and does not define CSRF token handling (`X-CSRFToken`) for POST/PATCH/DELETE. In secured mode with session auth, writes can fail with 403 CSRF errors.

**Required changes:**
1. Define a consistent production asset path strategy:
   - set Vite `base` to match Django static URL (typically `/static/`), and
   - ensure catch-all routing excludes static/media prefixes (or equivalent) so asset requests never hit the SPA fallback.
2. Define the dashboard auth/write strategy for secured mode:
   - if using session auth, include CSRF token extraction + `X-CSRFToken` header logic in the API client for unsafe methods;
   - if using API key auth for frontend writes, specify secure key provisioning approach and avoid conflicting session assumptions.
3. Reflect these in success criteria (at least one criterion proving production asset load works and one proving secured-mode write requests succeed).

Please revise `docs/phases/react-dashboard.md` and resubmit.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Addressed both blocking issues. Changes to `docs/phases/react-dashboard.md`:

**1. Production asset path alignment:**
- Vite config now uses conditional `base`: `"/static/"` for production build, `"/"` for dev. Built `index.html` references `/static/assets/main.<hash>.js`.
- `STATICFILES_DIRS` changed to `[BASE_DIR / "frontend" / "dist"]` (whole dist directory, not just `assets/`). This preserves the `assets/` subdirectory prefix so Django serves `/static/assets/...` correctly.
- Catch-all regex updated to `^(?!api/|admin/|static/).*$` — excludes `static/` prefix so asset requests go through Django's staticfiles, not the SPA fallback.

**2. CSRF strategy for session-auth writes:**
- Added `getCsrfToken()` helper that reads Django's `csrftoken` cookie (readable by JS because `CSRF_COOKIE_HTTPONLY` defaults to `False`).
- `request()` now includes `X-CSRFToken` header on all unsafe methods (POST, PATCH, DELETE).
- Added `credentials: "same-origin"` to `fetch()` so session and CSRF cookies are always sent.
- Documented that CSRF enforcement only applies to `SessionAuthentication` — bearer token auth bypasses CSRF. Dev mode (AllowAny) doesn't enforce CSRF.

**3. Updated success criteria:**
- Added criterion 13: production asset requests (`/static/assets/...`) load correctly (not caught by SPA fallback).
- Added criterion 15: secured-mode session-auth writes succeed (CSRF token sent via `X-CSRFToken` header).

### Reviewer

**Action:** APPROVE

Approved. The blocking issues from Round 1 are resolved:
- Production asset path strategy is now coherent (`base: "/static/"` for build, `STATICFILES_DIRS` includes full `dist`, and SPA catch-all excludes `static/`).
- Session-auth CSRF handling is now explicitly defined in the API client for unsafe methods (`X-CSRFToken` + `credentials: "same-origin"`).
- Success criteria now include explicit checks for production asset loading and secured-mode session-auth write behavior.

No further blocking issues for the React Dashboard plan phase.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 2
STATE: approved
```
