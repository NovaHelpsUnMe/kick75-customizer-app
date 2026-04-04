export interface ViaMenuControl {
  label: string;
  type: string;
  options?: Array<number | string>;
  content: (string | number)[];
  showIf?: string;
}

export interface ViaMenuSection {
  label: string;
  content: ViaMenuControl[];
}

export interface ViaMenu {
  label: string;
  content: ViaMenuSection[];
}

export interface ViaCustomKeycode {
  name: string;
  title: string;
}

export interface KeyboardLayoutToken {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface RawKick75BoardDefinition {
  name: string;
  vendorId: string;
  productId: string;
  matrix: {
    rows: number;
    cols: number;
  };
  layouts: {
    keymap: Array<Array<string | Partial<KeyboardLayoutToken>>>;
  };
  menus: ViaMenu[];
  keycodes: string[];
  customKeycodes: ViaCustomKeycode[];
}

export interface BoardKey {
  id: string;
  index: number;
  matrixPosition: string;
  x: number;
  y: number;
  width: number;
  height: number;
  row: number;
  col: number;
  label: string;
}

export interface LightingRangeControl {
  id: string;
  label: string;
  min: number;
  max: number;
  value: number;
  showIf?: string;
}

export interface LightingColorControl {
  id: string;
  label: string;
  value: string;
  showIf?: string;
}

export interface LightingDefinition {
  menuLabel: string;
  sectionLabel: string;
  supportedKeycodeFamilies: string[];
  effects: string[];
  selectedEffect: string;
  brightness?: LightingRangeControl;
  speed?: LightingRangeControl;
  color?: LightingColorControl;
}

export interface BoardDefinition {
  name: string;
  vendorId: string;
  productId: string;
  matrix: {
    rows: number;
    cols: number;
  };
  keys: BoardKey[];
  physicalLayoutOnly: true;
  lighting: LightingDefinition;
  customKeycodes: ViaCustomKeycode[];
}

export interface ImportedLayerAssignments {
  id: string;
  name: string;
  assignments: Record<string, string>;
}

export interface ImportedProfile {
  format: "via-keymap-arrays";
  name: string;
  layerCount: number;
  layers: ImportedLayerAssignments[];
  importedAt: string;
}

export interface SupportedImportParseResult {
  status: "supported";
  profile: ImportedProfile;
  diagnostics: string[];
}

export interface UnsupportedImportParseResult {
  status: "unsupported";
  diagnostics: string[];
}

export type ImportParseResult = SupportedImportParseResult | UnsupportedImportParseResult;

export interface RawViaProfileCandidate {
  name?: string;
  layers?: unknown;
  keymap?: unknown;
}
