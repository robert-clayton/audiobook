# Audiobook Pipeline — SPA frontend

React 19 + Vite + TypeScript + Tailwind 4 frontend for the audiobook pipeline,
served as static files by the FastAPI server in `audiobook/server/`.

## Build (required after changing src/)

```bash
cd frontend
npm install        # first time only
npm run build      # -> dist/, which is COMMITTED to git
```

`frontend/dist/` is committed so `git pull && uv run audiobook` works on any
machine without a Node toolchain. Rebuild and commit `dist/` alongside any
`src/` change.

## Dev loop (hot reload)

```bash
# Terminal 1 — API on a side port (production may own 8086)
uv run audiobook --dev --no-browser --port 8181

# Terminal 2 — Vite dev server on :5173, /api proxied to the side port
cd frontend
VITE_API_PORT=8181 npm run dev        # PowerShell: $env:VITE_API_PORT='8181'; npm run dev
```

## Architecture notes

- `src/api/` — typed client + one function per server endpoint
- `src/hooks/useStatusPoll.ts` — the single 2s `/api/status` poll (state,
  queue, incremental log via seq cursor); log lines live in a module store
  (`logStore.ts`) so they never churn React Query
- `src/lib/queryKeys.ts` — query keys + polling cadence (2s fast / 10s health)
- `src/components/ui/` — hand-built industrial primitives (no component lib)
- Theme tokens live in `src/index.css` (`@theme`) — near-black bg, amber
  accent, JetBrains Mono, 2px corners, hairline borders, no shadows
- Natural chapter sort ("Chapter 2" < "Chapter 10"): `src/lib/naturalSort.ts`,
  applied to title columns and mirrored server-side in
  `audiobook/server/util.py`
