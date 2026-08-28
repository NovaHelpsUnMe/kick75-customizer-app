# Kick75 Customizer

A local-first Vite application for inspecting and visualizing NuPhy Kick75 VIA definitions and profiles.

The Codex Command Center firmware, macOS helpers, recovery material, and release artifacts now live in the separate [kick75-codex-command-center](https://github.com/NovaHelpsUnMe/kick75-codex-command-center) repository.

## Current app

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
├── content/              # source content and reference assets
├── docs/                 # customizer architecture and content records
├── src/                  # customizer application
└── tests/                # customizer parser tests
```

## Safety and compatibility

- This is an unofficial community project and is not affiliated with NuPhy or OpenAI.
- The included VIA definition targets **NuPhy Kick75 ANSI QMK/VIA** with USB IDs `19F5:32D5`.
- Imported profiles must match the supported Kick75 key order and layer structure.
- Never commit API keys, personal task databases, device identifiers, or machine-specific paths.

## License and attribution

The project is distributed under GPL-2.0-or-later. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).

Created and maintained by [NovaHelpsUnMe](https://github.com/NovaHelpsUnMe).
