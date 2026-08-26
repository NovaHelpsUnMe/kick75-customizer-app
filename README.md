# Kick75 Customizer + Codex Command Center

A public, local-first project for understanding, restoring, and extending a NuPhy Kick75 keyboard.

The repository has two connected lanes:

1. **Kick75 Customizer** — the existing Vite/React/TypeScript app for inspecting the real Kick75 VIA definition.
2. **Codex Command Center** — the verified QMK firmware and macOS helpers that turn the Kick75 into a physical controller for Codex tasks.

## Codex Command Center v1.0

The current hardware build includes:

- a red KITT scanner while Codex mode is active;
- F1–F4 navigation for the first four pinned Codex tasks;
- live F1–F4 status colors for assigned, working, completed, attention, and error states;
- F5–F12 shortcuts for common Codex actions;
- a knob that scrolls the Codex conversation sidebar;
- knob-press reasoning control;
- isolated indicator lighting for Codex controls;
- normal keyboard behavior and saved VIA settings outside Codex mode.

Start with the [complete feature report](docs/codex-command-center.md) or the [recovery guide](docs/recovery.md). The verified source snapshot is under [firmware](firmware/README.md), and the local status/sidebar bridge is under [helpers/macos](helpers/macos/README.md).

## Current customizer app

- Frontend: Vite + React + TypeScript
- Data model: board-definition parser plus a narrow imported-profile parser
- Screens: Overview, Keymap, Lighting, Import/Export
- Tests: Kick75 definition parsing and supported/unsupported profile imports
- Limitation: profile import currently requires explicit layer arrays aligned to the normalized Kick75 key order

### Local app commands

```bash
npm install
npm run dev
npm run test
npm run build
```

## Repository layout

```text
.
├── docs/                 # durable feature, recovery, and roadmap records
├── firmware/             # verified Kick75 QMK source snapshot
├── helpers/macos/        # Codex status and sidebar bridge source
├── scripts/              # reproducible helper build scripts
├── src/                  # existing customizer application
└── tests/                # customizer parser tests
```

## Safety and compatibility

- This is an unofficial community project and is not affiliated with NuPhy or OpenAI.
- The firmware target is **NuPhy Kick75 ANSI QMK/VIA** with USB IDs `19F5:32D5`.
- Live status updates require wired USB. Normal keyboard input can continue to use the keyboard's supported connection modes.
- Codex desktop shortcuts and local state formats can change. Each release records the tested behavior and source revision.
- Never commit API keys, personal task databases, device identifiers, or machine-specific paths.

## Project direction

Stable behavior is recorded as a release before experimental work is added. Planned additions—including three manual Govee modes on Home, Page Up, and Page Down—remain in the [roadmap](docs/roadmap.md) until implemented and physically verified.

## License and attribution

The project is distributed under GPL-2.0-or-later to remain compatible with the QMK-derived firmware. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).

Created and maintained by [NovaHelpsUnMe](https://github.com/NovaHelpsUnMe).
