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
