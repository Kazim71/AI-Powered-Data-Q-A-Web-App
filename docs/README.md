# Documentation

Everything about how this app is built, why, and how to run it.

## Start here

**Reviewing this for the first time? Start with [10 · Project overview](10-project-overview.md)**
— a self-contained what/why/how, with the tech-stack rationale and real tested scenarios.
Everything below is the deep-dive version of one part of that page.

| Doc | What it covers |
|---|---|
| [00 · Build plan](00-build-plan.md) | Original scoping, stack choice, 6-hour schedule |
| [01 · Overview](01-overview.md) | The brief, scope, and how each acceptance criterion is met |
| [02 · Architecture](02-architecture.md) | System diagram, request flow, module map |
| [03 · Data pipeline](03-data-pipeline.md) | Ingestion → naming → profiling → join inference, in depth |
| [04 · API reference](04-api-reference.md) | Every endpoint, request and response |
| [05 · Local development](05-local-development.md) | Setup, running, testing, known environment gotchas |
| [06 · Deployment](06-deployment.md) | Free-tier hosting: Vercel + Render, and alternatives |
| [07 · Progress log](07-progress-log.md) | What was built when, and bugs found along the way |
| [08 · Roadmap](08-roadmap.md) | Milestone status and what comes next |
| [09 · Frontend design direction](09-frontend-design-direction.md) | Binding UI/UX brief for the frontend |
| [10 · Project overview](10-project-overview.md) | **Start here** — self-contained what/why/how for review or presentation |

## Decisions

Architecture Decision Records live in [`decisions/`](decisions/README.md). Each one records a
choice, the alternatives considered, and the trade-off accepted. When a decision changes,
supersede the record rather than editing history.

## Conventions

- **Numbered guides** (`NN-topic.md`) are living documents — keep them current with the code.
- **ADRs** (`decisions/NNNN-title.md`) are append-only.
- **Progress log** is appended to at the end of each working session.
- Diagrams and screenshots go in [`assets/`](assets/).
