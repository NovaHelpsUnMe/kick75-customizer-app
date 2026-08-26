import { ChangeEvent, useMemo, useState } from "react";
import rawKick75 from "../content/kick75-via.json";
import { KeyboardLayout } from "../components/keyboard/KeyboardLayout";
import { formatAssignmentLabel } from "../lib/via/display";
import { parseKick75BoardDefinition } from "../lib/via/parseKick75";
import { parseImportedProfile } from "../lib/via/parseImportedProfile";
import type { ImportParseResult } from "../lib/via/types";

type Screen = "overview" | "keymap" | "lighting" | "import-export";

const SCREENS: Array<{ id: Screen; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "keymap", label: "Keymap" },
  { id: "lighting", label: "Lighting" },
  { id: "import-export", label: "Import/Export" },
];

const board = parseKick75BoardDefinition(rawKick75);

function createInitialImportState(): ImportParseResult {
  return {
    status: "unsupported",
    diagnostics: ["No imported profile loaded. Keyboard view is using board-definition data only."],
  };
}

export function App() {
  const [activeScreen, setActiveScreen] = useState<Screen>("overview");
  const [selectedKeyId, setSelectedKeyId] = useState(board.keys[0]?.id ?? "");
  const [selectedEffect, setSelectedEffect] = useState(board.lighting.selectedEffect);
  const [brightness, setBrightness] = useState(board.lighting.brightness?.value ?? 255);
  const [speed, setSpeed] = useState(board.lighting.speed?.value ?? 255);
  const [color, setColor] = useState(board.lighting.color?.value ?? "#8ad0ff");
  const [importState, setImportState] = useState<ImportParseResult>(createInitialImportState());
  const [selectedLayerId, setSelectedLayerId] = useState("layer-0");
  const [lastImportFileName, setLastImportFileName] = useState<string | null>(null);

  const selectedKey = board.keys.find((key) => key.id === selectedKeyId) ?? board.keys[0];
  const activeProfile = importState.status === "supported" ? importState.profile : null;
  const activeLayer =
    activeProfile?.layers.find((layer) => layer.id === selectedLayerId) ?? activeProfile?.layers[0] ?? null;
  const activeAssignments = activeLayer?.assignments;
  const selectedAssignment = selectedKey && activeAssignments ? activeAssignments[selectedKey.id] ?? "" : "";

  const visibleLightingMeta = useMemo(
    () => ({
      showAdvancedControls: selectedEffect !== "All Off",
      supportedEffects: board.lighting.effects.length,
      customKeycodes: board.customKeycodes.length,
    }),
    [selectedEffect],
  );

  async function handleProfileImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setLastImportFileName(file.name);

    try {
      const text = await file.text();
      const parsedJson = JSON.parse(text) as unknown;
      const result = parseImportedProfile(parsedJson, board);
      setImportState(result);

      if (result.status === "supported") {
        setSelectedLayerId(result.profile.layers[0]?.id ?? "layer-0");
        setActiveScreen("keymap");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown import error";
      setImportState({
        status: "unsupported",
        diagnostics: [`Import failed: ${message}`],
      });
    } finally {
      event.target.value = "";
    }
  }

  function handleExport() {
    const payload = {
      keyboard: board.name,
      vendorId: board.vendorId,
      productId: board.productId,
      exportedAt: new Date().toISOString(),
      selectedKey,
      importedProfile:
        activeProfile === null
          ? null
          : {
              name: activeProfile.name,
              layerCount: activeProfile.layerCount,
              activeLayer: activeLayer?.name ?? null,
            },
      lightingPreview: {
        effect: selectedEffect,
        brightness,
        speed,
        color,
      },
    };

    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "kick75-config-export.json";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function renderScreen() {
    if (!selectedKey) return null;

    switch (activeScreen) {
      case "overview":
        return (
          <section className="workspace-grid">
            <article className="panel panel--hero">
              <p className="eyebrow">Current status</p>
              <h1>{board.name}</h1>
              <p className="lede">
                Physical layout, lighting, and custom keycodes come from the official Kick75 VIA
                definition. Assignment-aware inspection activates only after a supported profile import.
              </p>
              <div className="meta-row">
                <span>VID {board.vendorId}</span>
                <span>PID {board.productId}</span>
                <span>
                  {board.matrix.rows}x{board.matrix.cols} matrix
                </span>
                <span>{board.keys.length} layout positions</span>
              </div>
            </article>

            <article className="panel">
              <p className="eyebrow">Board definition</p>
              <ul className="check-list">
                <li>Physical layout comes from the official KLE-style `layouts.keymap` array</li>
                <li>Lighting comes from the official `menus` tree under `Lighting / Backlight`</li>
                <li>Custom keycodes come from the official `customKeycodes` list</li>
                <li>The official board JSON is never treated as assignment data</li>
              </ul>
            </article>

            <article className="panel">
              <p className="eyebrow">Profile import state</p>
              <div className="stat-list">
                <div className="stat-card">
                  <strong>{activeProfile ? activeProfile.name : "No profile loaded"}</strong>
                  <span>{lastImportFileName ?? "Awaiting user import"}</span>
                </div>
                <div className="stat-card">
                  <strong>{activeProfile ? `${activeProfile.layerCount} layers` : "Physical layout only"}</strong>
                  <span>
                    {activeProfile
                      ? "Assignment arrays matched to normalized board key order"
                      : "Keyboard view shows matrix positions until a supported profile is imported"}
                  </span>
                </div>
              </div>
            </article>

            <article className="panel">
              <p className="eyebrow">Diagnostics</p>
              <ul className="warning-list">
                {importState.diagnostics.map((diagnostic) => (
                  <li key={diagnostic}>{diagnostic}</li>
                ))}
              </ul>
            </article>
          </section>
        );
      case "keymap":
        return (
          <section className="editor-layout editor-layout--two-column">
            <div className="panel panel--workspace">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Official layout</p>
                  <h2>{activeProfile ? "Imported assignment view" : "Physical matrix map"}</h2>
                </div>
                <span className="badge">{activeProfile ? activeLayer?.name ?? "Layer" : "Source-backed positions"}</span>
              </div>

              {activeProfile ? (
                <div className="layer-switcher">
                  {activeProfile.layers.map((layer) => (
                    <button
                      key={layer.id}
                      type="button"
                      className={`layer-chip${layer.id === activeLayer?.id ? " is-active" : ""}`}
                      onClick={() => setSelectedLayerId(layer.id)}
                    >
                      <strong>{layer.name}</strong>
                      <span>{Object.keys(layer.assignments).length} keys</span>
                    </button>
                  ))}
                </div>
              ) : null}

              <KeyboardLayout
                keys={board.keys}
                selectedKeyId={selectedKey.id}
                assignments={activeAssignments}
                onSelectKey={setSelectedKeyId}
              />
            </div>

            <aside className="panel panel--inspector">
              <p className="eyebrow">Selected key</p>
              <h3>{selectedKey.label}</h3>
              <p className="inspector-meta">
                Matrix {selectedKey.matrixPosition} · Width {selectedKey.width}u · X {selectedKey.x}, Y {selectedKey.y}
              </p>

              <div className="inspector-block">
                <span>Assignment source</span>
                <strong>{activeProfile ? `${activeProfile.name} · ${activeLayer?.name ?? "Layer"}` : "Board definition only"}</strong>
              </div>

              <div className="inspector-block">
                <span>Readable assignment</span>
                <strong>{selectedAssignment ? formatAssignmentLabel(selectedAssignment) : "No imported assignment"}</strong>
              </div>

              <div className="inspector-block">
                <span>Raw assignment</span>
                <strong>{selectedAssignment || "Unavailable"}</strong>
              </div>

              <div className="inspector-block">
                <span>Custom keycodes available</span>
                <strong>{board.customKeycodes.length}</strong>
              </div>

              <div className="inspector-block">
                <span>Readable custom keycodes</span>
                <div className="metadata-list">
                  {board.customKeycodes.slice(0, 8).map((keycode) => (
                    <div key={keycode.title} className="metadata-row">
                      <strong>{keycode.name.replace(/\n/g, " / ")}</strong>
                      <span>{keycode.title}</span>
                    </div>
                  ))}
                </div>
              </div>
            </aside>
          </section>
        );
      case "lighting":
        return (
          <section className="workspace-grid workspace-grid--lighting">
            <article className="panel">
              <p className="eyebrow">{board.lighting.menuLabel}</p>
              <h2>{board.lighting.sectionLabel}</h2>

              <label className="field">
                <span>Effect</span>
                <select value={selectedEffect} onChange={(event) => setSelectedEffect(event.target.value)}>
                  {board.lighting.effects.map((effect) => (
                    <option key={effect} value={effect}>
                      {effect}
                    </option>
                  ))}
                </select>
              </label>

              {board.lighting.brightness ? (
                <label className="field">
                  <span>
                    {board.lighting.brightness.label} ({brightness})
                  </span>
                  <input
                    type="range"
                    min={board.lighting.brightness.min}
                    max={board.lighting.brightness.max}
                    value={brightness}
                    onChange={(event) => setBrightness(Number(event.target.value))}
                  />
                </label>
              ) : null}

              {board.lighting.speed && visibleLightingMeta.showAdvancedControls ? (
                <label className="field">
                  <span>
                    {board.lighting.speed.label} ({speed})
                  </span>
                  <input
                    type="range"
                    min={board.lighting.speed.min}
                    max={board.lighting.speed.max}
                    value={speed}
                    onChange={(event) => setSpeed(Number(event.target.value))}
                  />
                </label>
              ) : null}

              {board.lighting.color && visibleLightingMeta.showAdvancedControls ? (
                <label className="field">
                  <span>{board.lighting.color.label}</span>
                  <input type="color" value={color} onChange={(event) => setColor(event.target.value)} />
                </label>
              ) : null}
            </article>

            <article className="panel panel--hero">
              <p className="eyebrow">Preview</p>
              <div className="lighting-preview">
                <div
                  className="lighting-preview__glow"
                  style={{
                    background: `radial-gradient(circle, ${color} 0%, rgba(9, 10, 19, 0) 70%)`,
                    opacity: brightness / 255,
                  }}
                />
                <strong>{selectedEffect}</strong>
                <span>Brightness {brightness} / 255</span>
                {visibleLightingMeta.showAdvancedControls ? <span>Speed {speed} / 255</span> : null}
                <span>{visibleLightingMeta.supportedEffects} official effect options</span>
              </div>
            </article>
          </section>
        );
      case "import-export":
        return (
          <section className="workspace-grid">
            <article className="panel panel--hero">
              <p className="eyebrow">Import / export</p>
              <h1>Profile import</h1>
              <p className="lede">
                v1 import supports only narrow VIA-style backup/profile JSON with top-level layer arrays
                aligned to the normalized Kick75 board key order.
              </p>
              <label className="primary-button file-button">
                Import profile JSON
                <input type="file" accept="application/json,.json" onChange={handleProfileImport} hidden />
              </label>
              <button type="button" className="primary-button secondary-button" onClick={handleExport}>
                Export current metadata
              </button>
            </article>

            <article className="panel">
              <p className="eyebrow">Import result</p>
              <div className="metadata-list">
                <div className="metadata-row">
                  <strong>Status</strong>
                  <span>{importState.status}</span>
                </div>
                <div className="metadata-row">
                  <strong>Last file</strong>
                  <span>{lastImportFileName ?? "None"}</span>
                </div>
                {importState.status === "supported" ? (
                  <>
                    <div className="metadata-row">
                      <strong>Profile</strong>
                      <span>{importState.profile.name}</span>
                    </div>
                    <div className="metadata-row">
                      <strong>Layers</strong>
                      <span>{importState.profile.layerCount}</span>
                    </div>
                  </>
                ) : null}
              </div>
              <ul className="warning-list">
                {importState.diagnostics.map((diagnostic) => (
                  <li key={diagnostic}>{diagnostic}</li>
                ))}
              </ul>
            </article>
          </section>
        );
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="brand-kicker">NuPhy official source</p>
          <h1 className="brand-title">Kick75 Customizer</h1>
          <p className="brand-copy">
            Local-first board explorer aligned to the real Kick75 VIA definition.
          </p>
        </div>

        <nav className="nav-list" aria-label="Primary">
          {SCREENS.map((screen) => (
            <button
              key={screen.id}
              type="button"
              className={`nav-button${activeScreen === screen.id ? " is-active" : ""}`}
              onClick={() => setActiveScreen(screen.id)}
            >
              {screen.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="status-pill">Matrix {board.matrix.rows}x{board.matrix.cols}</span>
          <span className="status-meta">
            {activeProfile ? `${activeProfile.layerCount} imported layers` : "Physical layout only"}
          </span>
        </div>
      </aside>

      <main className="main-shell">{renderScreen()}</main>
    </div>
  );
}
