# Kick75 Codex Command Center v1.0

## Purpose

This build turns a NuPhy Kick75 ANSI QMK/VIA keyboard into a physical Codex command center while preserving normal keyboard use. It is both a reusable community build and a recovery record for rebuilding the original keyboard later.

## Entering and leaving Codex mode

- Enter Codex mode with the configured `Fn + C` layer toggle.
- The full keyboard switches to the red KITT scanner.
- Esc has a restrained red pulse and exits Codex mode.
- Leaving Codex mode restores the RGB configuration that was active before entry without writing the Codex effect to EEPROM.

## F1–F4 task slots

F1–F4 open the first four pinned Codex tasks using Codex's native macOS chat shortcuts. Pressing a completed green slot opens that task and acknowledges the light back to assigned white.

| Light | Meaning |
|---|---|
| Off | No pinned task is assigned to the slot |
| White | Pinned and assigned, with no active work |
| Breathing blue | The task is actively working |
| Bright gentle green glow | The task completed and is waiting to be checked |
| Rapid amber | A verified permission or user-input request needs attention |
| Rapid red | A verified task error occurred |

The bridge follows pinned-task order, ignores archived stale pins, and reads Codex state without modifying tasks, settings, or databases. Status values are runtime-only and are never saved to keyboard EEPROM.

## F5–F12 actions

| Key | Codex action | macOS shortcut emitted |
|---|---|---|
| F5 | Archive current chat | Command + Shift + A |
| F6 | New chat | Command + N |
| F7 | Pin or unpin current chat | Command + Option + P |
| F8 | Search files | Command + P |
| F9 | Open review | Control + Shift + G |
| F10 | Toggle plan mode | Control + Option + Command + P |
| F11 | Toggle browser panel | Command + Shift + B |
| F12 | Next task needing attention | Command + Option + A |

F5–F12 and the last top-row key before the knob use fixed electric-violet lighting. The KITT scanner is repainted beneath that overlay so the number row remains active.

## Knob behavior

- Turn the knob in Codex mode to scroll only the Codex left conversation sidebar.
- Press the knob to enter or leave reasoning control.
- Turn in reasoning control to decrease or increase reasoning effort.
- Home, Page Up, and Page Down currently indicate the knob mode: cyan for sidebar mode and violet for reasoning mode.
- The knob helper only responds while Codex is frontmost and does not click, pin, archive, or inspect task content.

## Runtime architecture

```text
Codex local read-only state
          │
          ▼
codex_status.py ── four status names ──► native macOS HID helper
                                                │
                                                ▼
                                  VIA runtime custom value 0x81
                                                │
                                                ▼
                                  F1–F4 RGB status overlay

Kick75 knob ── private shortcuts ──► macOS Accessibility helper ──► Codex sidebar
```

The status helper targets only the Kick75 Raw HID interface for USB IDs `19F5:32D5`. The sidebar helper requires macOS Accessibility permission. The status app requires Input Monitoring permission.

## Verified v1.0 acceptance

- QMK firmware builds for `nuphy/kick75/ansi:via`.
- Firmware flashes through the STM32 DFU bootloader.
- Keyboard returns as the Kick75 HID device after flashing.
- The Python status logic passes 18 focused tests.
- F1–F4 statuses, KITT lighting, F5–F12, and knob behavior were physically exercised during development.
- The public snapshot contains no API key, personal Codex task content, task database, or personal filesystem path.

