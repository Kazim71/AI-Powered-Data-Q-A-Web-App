# Frontend

Next.js (App Router) + TypeScript + Tailwind v4 + Recharts. One route — this is a working
data-analysis tool, not a marketing site. See
**[docs/09-frontend-design-direction.md](../docs/09-frontend-design-direction.md)** for the
design system (colours, type, spacing, motion) and the information architecture this
implements — read that before changing anything here.

## Run it

```bash
npm install
```

```bash
cp .env.example .env.local
```

```bash
npm run dev
```

Open http://localhost:3000. The backend must be running (see
[../backend](../backend) / [docs/05-local-development.md](../docs/05-local-development.md)) —
by default at `http://localhost:8000`, matching `NEXT_PUBLIC_API_URL`.

## Structure

```
src/
├─ app/
│  ├─ layout.tsx       fonts (Public Sans + IBM Plex Mono), metadata
│  ├─ page.tsx          the single workspace route — orchestrates everything below
│  └─ globals.css       design tokens (colour/type/spacing/radius/motion), Tailwind v4 @theme
├─ hooks/
│  └─ useWorkspace.ts   session, schema, uploads, turns — all app state and API calls
├─ lib/
│  ├─ api.ts             typed client for the backend's four endpoints
│  ├─ types.ts           hand-written twin of backend/app/models.py
│  ├─ format.ts           number/cell formatting, row→record conversion for charts
│  └─ utils.ts             cn() className helper
└─ components/
   ├─ ui/                Button, Badge, StatusBanner — hand-rolled primitives, not the
   │                      shadcn CLI (see docs/07-progress-log.md for why)
   ├─ EmptyState.tsx      first screen: what the tool does + the upload zone
   ├─ UploadZone.tsx       drag-and-drop + click-to-browse
   ├─ UploadProgressList.tsx per-file upload outcome
   ├─ SchemaSidebar.tsx / DataSheet.tsx / SchemaContent.tsx
   │                      desktop sidebar and mobile bottom sheet, sharing one content component
   ├─ AskBar.tsx           the question input
   ├─ Turn.tsx             one Q&A turn: answer → chart → table → SQL (collapsed)
   ├─ ChartView.tsx        renders whatever chart.type the backend picked — no chart logic here
   └─ ResultTable.tsx       the data table, scrolls within itself
```

No global state library — `useWorkspace` is the one hook holding everything, which is enough
for a single-route app. No shadcn CLI, no Watermelon UI install, no Motion Primitives package:
evaluated against the brief's tooling list, and for this scope hand-rolling was faster and gave
more control over avoiding the generic look than pulling in and then fighting default styling.
Motion is a handful of CSS transitions/keyframes in `globals.css`, respecting
`prefers-reduced-motion`.

## A known environment gotcha (Windows only)

If your checkout's path contains a literal `&` (e.g. this repo cloned somewhere under a folder
named with "Q&A" in it), `cmd.exe` — npm's default script shell on Windows — mangles it, and
**every** npm script fails: `npm run dev`, `build`, `lint`, and any `npx <tool>` call, all with
some variant of `Cannot find module '...'` or `'X' is not recognized as an internal or external
command`.

Fix: create a `frontend/.npmrc` (this file is machine-local and gitignored on purpose — see
below) pointing npm at Git Bash instead:

```
script-shell=C:\\Program Files\\Git\\bin\\bash.exe
```

Adjust the path if Git for Windows is installed elsewhere. With that in place `npm run dev`
etc. work normally. For a one-off command without wanting to add the file, call the local
binary directly instead of through `npx`:

```bash
node node_modules/next/dist/bin/next build
```

**Why `.npmrc` isn't committed:** it hardcodes a Windows path. Committing it would break the
build on any Linux machine — including Vercel's build servers — since that path simply doesn't
exist there. This bug is specific to this one Windows checkout's folder name, not the project.
