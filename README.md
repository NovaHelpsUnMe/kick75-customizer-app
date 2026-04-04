# kick75-customizer-app

Kick75 Customizer is now a minimal web-first MVP scaffold for a NuPhy Kick75 configuration tool. The current implementation is intentionally local-first: it loads the real Kick75 VIA definition, normalizes it into typed app state, renders the physical layout from the official schema, exposes the official lighting menu, and supports JSON export for future persistence.

## Current status

- Frontend stack: Vite + React + TypeScript
- Data model: separate board-definition parser and narrow imported-profile parser
- Current screens: Overview, Keymap, Lighting, Import/Export
- Tests: board-definition parsing plus supported/unsupported profile import coverage
- Important limitation: profile import in v1 only supports JSON files with explicit layer arrays aligned to the normalized Kick75 board key order

## Local run

1. Install dependencies: `npm install`
2. Start the dev server: `npm run dev`
3. Run tests: `npm run test`
4. Build production assets: `npm run build`

## MVP structure

```text
.
├── src/
│   ├── app/              # app shell and screen switching
│   ├── components/       # keyboard rendering components
│   ├── content/          # app-consumable JSON inputs
│   ├── lib/via/          # parser and typed data model
│   └── styles/           # global CSS
├── tests/                # parser-focused tests
├── content/              # raw source material and references
└── docs/                 # planning and architecture notes
```

## What needs to happen next

- Import a real VIA-style backup/profile with explicit layer arrays if you want assignment-aware inspection
- Keep editing out of scope until a safe round-trip profile format is confirmed
- Add import support and profile persistence
- Keep firmware-aware logic isolated from the UI layer

## Notes on source material

- [`Kick75 app.make`](/Users/morningstar/Documents/GitHub/kick75-customizer-app/Kick75%20app.make) is treated as design/reference input only
- Do not treat its internal generated-code references as authoritative source files
- Put additional keyboard reference files under `content/assets/reference/` if you need more confirmed labels or capability checks beyond the official VIA file
