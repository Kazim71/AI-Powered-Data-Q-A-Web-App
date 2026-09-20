# 09 · Frontend design direction

Binding brief for milestone 3. The goal is an interface that looks designed by a product designer for **this** product, not an AI-generated SaaS template.

## Priorities (in order)

Information hierarchy · usability · typography · spacing · layout · content · identity · interaction · motion · decoration.

## Hard "no" list

- Gradients as a design language, gradient text, glows, radial orbs, mesh backgrounds, blobs, dot grids
- Glassmorphism / frosted cards, heavy blur, heavy shadows
- Purple-on-black, neon, rainbow or random pastel palettes; pure white everywhere
- Sparkle icons, emojis as decoration, robot/AI imagery, stock illustrations
- Section → heading → three cards, repeated; bento grids by default; card for every paragraph; nested cards
- Excessive radius, pill buttons everywhere, gradient/glowing buttons, competing primary CTAs
- Colored left stripes, fake terminal windows, icon beside every heading
- Fake testimonials, logos, metrics, social proof
- Hover and scroll animations on everything; animated arrows; floating elements
- Marketing clichés: "unlock", "supercharge", "seamlessly", "the future of", "it's not X, it's Y"; em-dash-heavy copy
- Inter / Geist / Space Grotesk chosen by default

## Tooling

| Tool | Role |
|---|---|
| Next.js + TypeScript + Tailwind | Foundation |
| shadcn/ui | Primitives only, restyled (type, colour, radius, density, states) so it never reads as the shadcn demo |
| [Watermelon UI](https://watermelon.sh/) | Only where a component clearly beats building it. `npx shadcn@latest add https://registry.watermelon.sh/r/<name>.json` |
| [Motion Primitives](https://motion-primitives.com/) | Sparse, purposeful motion (state changes, answer reveal). `npx motion-primitives@latest add text-effect` |
| Lucide | Only icons that carry meaning or identify an action |

## Process (before any component code)

1. Information architecture and required states
2. Design tokens: colour, type scale, spacing, radius (restrained, not uniform), borders, shadows (sparing), transitions, breakpoints
3. Component system and interaction patterns
4. Responsive behaviour (reorganise for mobile, don't just stack)
5. Animation principles, with `prefers-reduced-motion` respected and the UI excellent with motion off

Record the resulting system in this doc before implementation.

## What that means for this product

This is a **working tool for analysing a user's own data**, not a landing page. Personality should come from treating data seriously:

- **The workspace is the product.** No marketing hero. First screen is an honest empty state that explains what to do and accepts files.
- **Real content only.** Demos use the actual sample files; no invented dashboards or numbers.
- **Data-appropriate typography.** A readable text face plus a tabular/monospaced face for numbers, SQL and column names, with tabular figures in tables.
- **Dense where it helps.** Schema sidebar and result tables can be information-dense; the answer itself gets space and hierarchy.
- **Colour = meaning.** One strong primary; semantic-type badges (identifier, numeric, temporal, categorical…) and states use a small controlled set; charts use a restrained, accessible palette.
- **Progressive disclosure.** Answer first, then chart, then table, then SQL (collapsed), then join hints.
- **Required states:** empty, uploading (per file), partial upload failure, profiling, asking, answer, SQL error/repaired, no rows, session expired, backend cold start.

## Mobile

Upload and ask must be fully usable on a phone. Schema moves into a sheet, tables scroll inside their own container (never the page), touch targets ≥ 44px.

## Accessibility

Semantic landmarks, one logical heading order, visible focus rings, keyboard-operable upload and chat, labelled controls, WCAG AA contrast, charts paired with a data table.

## Final design test

Before calling the frontend done, check every screen:

1. Does it look like a generic AI website?
2. Any unnecessary gradient? 3. Card? 4. Icon? 5. Animation? 6. Meaningless decoration?
7. Repetitive 3-column layouts? 8. Too many rounded rectangles? 9. Too many shadows?
10. Is typography distinctive and readable? 11. Is colour intentional?
12. Does the layout communicate the actual product? 13. Personality without effects?
14. Is mobile intentionally designed? 15. Does anything look like a pasted template component?

Any "yes" to a generic pattern means redesign that part.

---

## Information architecture

One route. This is a workspace, not a multi-page site — there's nothing to navigate to.

```
/  (single workspace)
 ├─ no session yet          → empty state, upload zone, nothing else
 ├─ session, no files       → same empty state (a session id alone isn't a milestone)
 ├─ files uploading         → per-file progress, partial failures shown inline
 ├─ files landed            → schema sidebar populates; ask bar becomes active
 ├─ question asked          → answer stream: answer → chart → table → SQL (collapsed) → joins used
 └─ error states            → SQL failed & repaired (shown, not hidden), no rows, session
                               expired (404 from backend → re-upload prompt), backend cold
                               start (first request >5s → "waking up" message, not a blank wait)
```

No separate "results page" — each question appends a turn to the same view, like a working
log, not a chat product pretending to be friendly. The most recent turn gets full visual
weight; earlier turns collapse to their answer line + a re-expand affordance.

## Layout

Desktop: two-pane. A fixed-width schema sidebar (tables, columns, semantic-type badges, join
lines) on the left; the ask bar + turn history filling the remaining width. Not a chat-app
layout with a centered narrow column — the data is part of the interface, not hidden behind a
toggle.

Mobile: sidebar becomes a bottom sheet triggered by a "Data" tab, so the ask bar and the latest
turn own the full screen.

## Design system

### Colour

Product identity: a tool that computes real numbers from your own data and shows its work —
not a generic "AI assistant." Colour should read as *precise and calm*, not vibrant.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#F7F5F0` (warm paper, not pure white) | `#15181A` (ink, not pure black) | Page background |
| `--surface` | `#FFFFFF` | `#1C2023` | Sidebar, panels, the ask bar |
| `--surface-sunken` | `#EFEBE3` | `#101314` | Table zebra rows, code/SQL blocks |
| `--border` | `#DED7C9` | `#2B3033` | Hairlines only — never a shadow to separate panels |
| `--text` | `#1C1B17` | `#EDEAE2` | Body text |
| `--text-muted` | `#6B6459` | `#9B948A` | Secondary text, captions |
| `--primary` | `#0E5F56` (deep petrol) | `#4FBFA8` | Primary actions, active states, links |
| `--primary-contrast` | `#FFFFFF` | `#0B211D` | Text on `--primary` |
| `--accent` | `#B7791F` (muted amber) | `#D9A345` | *One* controlled use: flags a model-stated assumption. Never decorative. |
| `--success` | `#2E7D5B` | `#5FC594` | Upload ok, query ok |
| `--warning` | `#A56A1B` | `#D9A345` | Truncated result, repaired query |
| `--error` | `#A23B2E` | `#E08776` | Failed upload, SQL error, timeout |
| `--info` | `#3B6E91` | `#7FB4D9` | Neutral notices (cold start, session TTL) |

Petrol was picked over blue/purple specifically to avoid the generic-AI palette; amber for
assumptions (not red — an assumption isn't an error, it's the model being honest about a
judgement call).

**Chart series palette** (categorical, used by Recharts, colour-blind-checked for adjacent-pair
contrast): `#0E5F56, #B7791F, #3B6E91, #8A4B6B, #5B7A3A, #94582C` — six colours before any
repeat, none of them primary-adjacent enough to be confused with an interactive element.

### Typography

Two faces, both via `next/font` (self-hosted, no runtime Google Fonts request):

- **Public Sans** — UI text and prose. Chosen over Inter/Geist/Space Grotesk for a slightly
  more distinctive, less "AI demo default" character while staying highly legible at small
  sizes; it's a workhorse government-design-system face built for dense information UI, which
  is exactly this product.
- **IBM Plex Mono** — every number, column name, table cell, and the SQL panel. Tabular
  figures by default, so a column of numbers actually lines up. This is a deliberate,
  functional choice (data must be legible and comparable), not a "terminal aesthetic."

| Token | Size / line-height | Weight | Use |
|---|---|---|---|
| `--text-xs` | 12px / 16px | 500 | Badges, captions, table headers |
| `--text-sm` | 13px / 20px | 400–500 | Secondary text, SQL panel |
| `--text-base` | 15px / 24px | 400 | Body, ask input |
| `--text-lg` | 17px / 26px | 500 | The answer sentence — gets the most weight in the UI |
| `--text-xl` | 22px / 30px | 600 | Empty-state heading (the only "heading" in the app) |

Numbers in tables and KPI figures always use the mono face with `font-variant-numeric:
tabular-nums`. Three weights total across both faces (400/500/600) — no thin, no black.

### Spacing & radius

4px base unit: `4, 8, 12, 16, 24, 32, 48, 64`.

Radius is **not uniform** — it signals what kind of thing an element is:
`--radius-sm: 4px` (inputs, buttons, badges) · `--radius-md: 8px` (panels, the ask bar, cards
that group content) · `--radius-none: 0` (table cells, the SQL code block — data shouldn't
look "soft").

### Borders & shadows

Hairline borders (`--border`, 1px) do the separating work. Shadow used exactly once: a single
soft `0 1px 3px` on the ask bar only, to lift the one element the user always interacts with.
Nothing else gets a shadow.

### Motion

`transform`/`opacity` only, 150–200ms, `ease-out`. Used for: a turn's answer fading/lifting in
once it arrives (not sliding from off-screen), a chart crossfading when its data updates, an
upload row's progress fill. Never: hover-scale on cards, animated icons, anything looping.
Everything wrapped in `@media (prefers-reduced-motion: reduce) { transition: none }` and the
UI must be equally usable with it off — motion confirms state changes, it never carries
information alone.

### Breakpoints

`sm: 480px · md: 768px · lg: 1024px · xl: 1280px`. Sidebar→sheet collapse happens at `md`.
