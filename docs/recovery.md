# Recovery and Reinstall Guide

This guide restores the verified v1.0 firmware and reconstructs the two macOS helpers.

## Requirements

- NuPhy Kick75 ANSI QMK/VIA keyboard
- macOS
- QMK CLI and ARM toolchain
- The upstream [BunnyHorseCat/NuphyQMK](https://github.com/BunnyHorseCat/NuphyQMK) source
- Wired USB for flashing and live status updates
- Codex desktop app for the Codex-specific controls

The v1.0 snapshot was built from upstream Git revision `9606f5a1fbc2cad0489f07eb336d4e317ee29ee4`.

## Fastest recovery

Download `nuphy_kick75_ansi_via.bin` from this repository's v1.0 GitHub Release. Verify its SHA-256:

```text
76be851d4081b369e2b0effea444061d51fe81f5c440f7a93189cc61b8c59c66
```

Enter the Kick75 bootloader:

1. Disconnect the wired USB cable.
2. Hold Esc.
3. Reconnect the cable while still holding Esc.
4. Wait approximately two seconds, then release Esc.
5. Confirm `dfu-util -l` shows STM32 DFU device `0483:df11`.

Flash from a QMK checkout containing the snapshot keymap:

```bash
qmk flash -kb nuphy/kick75/ansi -km via -e SKIP_GIT=yes
```

A successful flash ends with `File downloaded successfully` and a leave request. The keyboard should reconnect as USB device `19F5:32D5`.

## Rebuild from source

1. Clone the upstream QMK repository.
2. Check out the recorded upstream revision.
3. Replace `keyboards/nuphy/kick75/ansi/keymaps/via/keymap.c` with this repository's copy under `firmware/`.
4. Build:

```bash
qmk compile -kb nuphy/kick75/ansi -km via -e SKIP_GIT=yes
```

5. Confirm the output is `.build/nuphy_kick75_ansi_via.bin`.
6. Run the 18 status tests from this repository:

```bash
python3 -m unittest helpers.macos.tests.test_codex_status
```

A binary checksum can differ when the QMK toolchain or source revision differs. Behavior and build success are the primary checks for a rebuild.

## Rebuild the macOS helpers

Run:

```bash
./scripts/build-macos-helpers.sh
```

This creates two ad-hoc-signed archives under `dist/macos/`:

- `Kick75-Codex-Status-macOS.zip`
- `Kick75-Codex-Sidebar-macOS.zip`

Unzip them, copy the two apps to the current user's `Applications` folder, launch each once, then grant:

- Input Monitoring to Kick75 Codex Status
- Accessibility to Kick75 Codex Sidebar

Add both apps to **System Settings → General → Login Items → Open at Login**. Do not install the retired Python LaunchAgent; the native status app owns the keyboard connection.

## Recovery checks

- Enter Codex mode and confirm KITT lighting appears.
- Pin up to four tasks and confirm F1–F4 follow the pinned order.
- Start and finish a test task: its slot should move blue → green.
- Press the matching F-key: it should open the task and return to white.
- Turn the knob: only the Codex left sidebar should scroll.
- Press the knob and turn it: reasoning effort should change.
- Exit Codex mode: normal RGB and keyboard behavior should return.
- Open VIA and confirm the keyboard remains detectable.

## Safety

Do not flash this binary to another Kick75 layout or model. Do not commit local Codex databases, API keys, task logs, or generated app permissions to the repository.
