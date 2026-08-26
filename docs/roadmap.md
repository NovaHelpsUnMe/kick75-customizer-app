# Roadmap

Items here are planned, not shipped. They enter the feature report and changelog only after implementation and physical verification.

## Next: Govee manual lighting modes

Reserve Home, Page Up, and Page Down in Codex mode as three intentional room-light scene controls while preserving their normal behavior outside Codex mode.

| Key | Planned scene | Intent |
|---|---|---|
| Home | Home Base | Calm neutral work lighting |
| Page Up | Codex Flow | Red/amber KITT-inspired focus scene |
| Page Down | Fireplace Reset | Gentle warm ember scene for winding down |

Planned architecture:

- Kick75 emits three otherwise-unused private shortcuts only in Codex mode.
- A local macOS helper maps them to real Govee scenes discovered through Govee's official API.
- The Govee API key is stored locally in macOS Keychain and is never committed.
- Scene identifiers and device capabilities are discovered from the user's account rather than guessed.
- Current F1–F12 mappings, task status lights, KITT effect, and knob behavior remain unchanged.

Implementation stays blocked until the exact Govee models and supported scene capabilities are verified.

## Later candidates

- Portable installer with clear permission diagnostics
- Compatibility matrix for additional Kick75 variants
- Customizer app view that documents the installed Codex layer
- Community-submitted scene and shortcut profiles

