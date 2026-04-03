# kick75-customizer-app

This repository is initialized as a content-ready baseline so work can start immediately without redoing structure later. The current setup is intentionally framework-agnostic: it supports planning, content authoring, asset intake, and application code once the implementation stack is chosen.

## Current repo layout

```text
.
├── content/
│   ├── assets/
│   │   ├── images/
│   │   └── reference/
│   └── copy/
├── docs/
│   ├── architecture/
│   └── content/
├── public/
│   ├── icons/
│   └── images/
├── scripts/
├── src/
│   ├── app/
│   ├── components/
│   ├── content/
│   ├── lib/
│   └── styles/
└── tests/
```

## Directory intent

- `content/`: raw content inputs, copy, reference assets, and non-runtime source material.
- `content/assets/images/`: source images before optimization or app integration.
- `content/assets/reference/`: inspiration, design references, and source attachments.
- `content/copy/`: product copy, page copy, and structured text drafts.
- `docs/`: project decisions, architecture notes, content plans, and implementation handoff material.
- `docs/architecture/`: technical planning, system notes, and stack decisions.
- `docs/content/`: content outlines, briefs, editorial notes, and publishing requirements.
- `public/`: runtime-served static files for the eventual app.
- `public/icons/`: shipped icons and app-facing static icon assets.
- `public/images/`: optimized images intended to be served directly by the app.
- `scripts/`: utility scripts for setup, transforms, imports, or local automation.
- `src/`: application source once the stack is selected.
- `src/app/`: top-level app entrypoints, routes, or screens.
- `src/components/`: reusable UI components.
- `src/content/`: app-consumable structured content or transformed content modules.
- `src/lib/`: shared utilities, helpers, and non-UI application logic.
- `src/styles/`: global styles, tokens, and theming.
- `tests/`: focused tests once implementation begins.

## Working rules

- Put raw inputs in `content/` and only ship optimized or application-ready assets from `public/` or `src/content/`.
- Keep planning notes in `docs/` so repo intent stays explicit as the app takes shape.
- Add a framework only when the stack decision is made; this baseline is meant to avoid premature lock-in.

## Recommended next step

Choose the implementation stack for `src/` before adding package manager files. If the target is a web app, the next clean move is to initialize the chosen framework into this existing structure instead of rebuilding the repo from scratch.
