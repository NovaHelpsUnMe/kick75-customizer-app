# macOS helpers

The Codex Command Center uses two small local helpers.

## Kick75 Codex Status

- Reads local Codex task state without writing to Codex.
- Emits four status names from `codex_status.py`.
- Uses the native HID app to send a runtime-only VIA packet to the Kick75.
- Requires Input Monitoring permission.
- Requires wired USB for live LED updates.

The public Objective-C source loads `codex_status.py` from the app bundle, so it contains no personal filesystem path.

## Kick75 Codex Sidebar

- Listens only for the private knob shortcuts.
- Acts only while Codex is frontmost.
- Sends controlled scroll events to the left conversation sidebar.
- Requires Accessibility permission.
- Does not click or alter conversations.

Build both helpers with `scripts/build-macos-helpers.sh`. The generated signed zip archives remain under ignored `dist/macos/` and are not committed.
