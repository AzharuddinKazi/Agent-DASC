# DS-STAR Frontend

React (Vite) single-page app for submitting DS-STAR queries and watching the agent pipeline
run. See the [repo-level README](../README.md) for the overall architecture.

## Stack

- React + Vite, plain JS (no TypeScript — `jsconfig.json` only, for editor path/type hints)
- Tailwind CSS v4 + shadcn/radix-ui primitives (`components/ui/`)
- Supabase JS client — auth (email/password) and the JWT used to authorize backend calls
- `axios` for API calls, `recharts` for charts, `react-markdown`/`react-syntax-highlighter` for
  rendering report/answer content

## Layout

```
src/
├── App.jsx                 Top-level view switch: login → empty state → dashboard → domain packs
├── api.js                  All backend calls; attaches the Supabase session JWT to every request
├── hooks/
│   ├── useAuth.js           Supabase session state + signIn/signUp/signOut
│   └── useHealth.js         Polls GET /health
├── lib/supabaseClient.js   Supabase client instance (URL + anon key from env)
├── config/brand.js         White-label branding config (name, colors, logo) — see brand.examples.js
└── components/
    ├── app/                 Feature components (see below)
    └── ui/                  Generic shadcn-style primitives (button, card, table, sidebar, ...)
```

`App.jsx` holds a single `view` state (`"empty" | "dashboard" | "domainPacks"`) — there's no
router; the app is one screen at a time by design.

### `components/app/`

| Component | Purpose |
|---|---|
| `Login.jsx` | Email/password sign-in and sign-up via Supabase auth |
| `EmptyState.jsx` | Landing screen: query input, task-type toggle (QA vs. report), submit |
| `Dashboard.jsx` | Main task view — wires together the pipeline timeline and result panel for an in-flight or completed task |
| `PipelineHeader.jsx` | Task title/status bar above the dashboard content |
| `PipelineTimeline.jsx` | Renders the live agent-by-agent log stream (from `get_task`'s `logs`) as a timeline |
| `ResearchProgress.jsx` | Report-mode progress indicator across sub-questions |
| `ReportPanel.jsx` / `ReportView.jsx` / `ReportSections.jsx` | Render a completed report's sections, charts, and findings |
| `DomainPacks.jsx` | Browse/activate domain packs, upload knowledge documents |
| `Sidebar.jsx` | Task history list + navigation |

## Data flow

There's no WebSocket/SSE — the dashboard polls `GET /api/v1/get_task/{id}` on an interval and
re-renders as `logs`, `status`, and `final_result`/`sub_results` change. Every request in
`api.js` goes through an axios interceptor that reads the current Supabase session and attaches
it as `Authorization: Bearer <jwt>`; the backend validates that token on every `/api/v1/*` call
(see `backend/auth.py`).

## Setup

```bash
npm install
```

Environment variables (Vite — compile-time, prefixed `VITE_`):

- `VITE_API_BASE` — backend base URL (default `http://localhost:8000`)
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` — same Supabase project as the backend

Create a `.env` file in `frontend/` with these, or set them as Docker build args (see
`docker-compose.yml`) since Vite bakes them into the build at compile time, not runtime.

## Running

```bash
npm run dev       # dev server with HMR, http://localhost:5174 (pinned in vite.config.js)
npm run build     # production build to dist/
npm run preview   # serve the production build locally
npm run lint      # eslint
```

Or via Docker: the `Dockerfile` here builds the app and serves `dist/` with nginx
(`nginx.conf` — a single SPA fallback route). See [repo README](../README.md#option-a--docker-compose-backend--frontend-together)
for running it as part of the full stack (served on port 5174 there, matching the backend's
default CORS allowlist).

## Testing

None yet — no test framework is configured (tracked in `../TASKS.md`).

## Known issues

`npm run lint` currently reports errors, almost entirely from vendored shadcn boilerplate in
`components/ui/`, not app code. See `../TASKS.md` for this and other tracked frontend issues
(bundle size, accessibility, error boundaries).
