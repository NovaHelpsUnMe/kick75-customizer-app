import type {
  BoardDefinition,
  ImportParseResult,
  ImportedLayerAssignments,
  ImportedProfile,
  RawViaProfileCandidate,
} from "./types";

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function createUnsupported(diagnostics: string[]): ImportParseResult {
  return {
    status: "unsupported",
    diagnostics,
  };
}

function normalizeLayerName(index: number): string {
  if (index === 0) return "Base";
  if (index === 1) return "Fn";
  return `Layer ${index}`;
}

function normalizeAssignments(
  board: BoardDefinition,
  layerEntries: string[],
): Record<string, string> {
  return board.keys.reduce<Record<string, string>>((acc, key, index) => {
    acc[key.id] = layerEntries[index] ?? "";
    return acc;
  }, {});
}

export function parseImportedProfile(
  rawJson: unknown,
  board: BoardDefinition,
): ImportParseResult {
  if (!rawJson || typeof rawJson !== "object") {
    return createUnsupported(["Imported file is not a JSON object."]);
  }

  const candidate = rawJson as RawViaProfileCandidate;
  const layersValue = candidate.layers ?? candidate.keymap;

  if (!Array.isArray(layersValue)) {
    return createUnsupported([
      "Imported file does not contain a supported top-level `layers` or `keymap` array.",
      "v1 import expects explicit per-layer assignment arrays aligned to the normalized board key order.",
    ]);
  }

  if (layersValue.length === 0) {
    return createUnsupported(["Imported file has no layer data to map onto the board."]);
  }

  const expectedKeyCount = board.keys.length;
  const diagnostics: string[] = [];
  const layers: ImportedLayerAssignments[] = [];

  for (let index = 0; index < layersValue.length; index += 1) {
    const layerValue = layersValue[index];
    if (!isStringArray(layerValue)) {
      return createUnsupported([
        `Layer ${index} is not a flat array of string assignments.`,
        "v1 import only supports VIA-style layer arrays with one string entry per normalized board key.",
      ]);
    }

    if (layerValue.length !== expectedKeyCount) {
      return createUnsupported([
        `Layer ${index} has ${layerValue.length} assignments, but the Kick75 board model expects ${expectedKeyCount}.`,
        "Assignment arrays must match the normalized board key order exactly.",
      ]);
    }

    layers.push({
      id: `layer-${index}`,
      name: normalizeLayerName(index),
      assignments: normalizeAssignments(board, layerValue),
    });
  }

  diagnostics.push(`Imported ${layers.length} layer arrays matched to ${expectedKeyCount} board keys.`);

  const profile: ImportedProfile = {
    format: "via-keymap-arrays",
    name: candidate.name?.trim() || "Imported VIA profile",
    layerCount: layers.length,
    layers,
    importedAt: new Date().toISOString(),
  };

  return {
    status: "supported",
    profile,
    diagnostics,
  };
}
