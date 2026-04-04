import type {
  BoardDefinition,
  BoardKey,
  KeyboardLayoutToken,
  LightingColorControl,
  LightingDefinition,
  LightingRangeControl,
  RawKick75BoardDefinition,
  ViaCustomKeycode,
  ViaMenuControl,
} from "./types";

function parseMatrixPosition(value: string): { row: number; col: number } {
  const [row, col] = value.split(",").map(Number);
  return { row, col };
}

function createLayoutLabel(matrixPosition: string): string {
  const { row, col } = parseMatrixPosition(matrixPosition);
  return `R${row} C${col}`;
}

function parseKeyboardLayout(
  rows: RawKick75BoardDefinition["layouts"]["keymap"],
): BoardKey[] {
  const keys: BoardKey[] = [];
  let currentY = 0;

  rows.forEach((layoutRow) => {
    let currentX = 0;
    let rowHeight = 1;
    let nextWidth = 1;
    let nextHeight = 1;

    layoutRow.forEach((entry) => {
      if (typeof entry === "string") {
        const matrixPosition = entry;
        const { row, col } = parseMatrixPosition(matrixPosition);

        keys.push({
          id: `key-${matrixPosition.replace(",", "-")}`,
          index: keys.length,
          matrixPosition,
          x: currentX,
          y: currentY,
          width: nextWidth,
          height: nextHeight,
          row,
          col,
          label: createLayoutLabel(matrixPosition),
        });

        currentX += nextWidth;
        rowHeight = Math.max(rowHeight, nextHeight);
        nextWidth = 1;
        nextHeight = 1;
        return;
      }

      const token = entry as Partial<KeyboardLayoutToken>;
      if (typeof token.x === "number") currentX += token.x;
      if (typeof token.y === "number") currentY += token.y;
      if (typeof token.w === "number") nextWidth = token.w;
      if (typeof token.h === "number") nextHeight = token.h;
    });

    currentY += rowHeight;
  });

  return keys;
}

function findControl(controls: ViaMenuControl[], label: string): ViaMenuControl | undefined {
  return controls.find((control) => control.label === label);
}

function parseRangeControl(control: ViaMenuControl | undefined): LightingRangeControl | undefined {
  if (!control || control.type !== "range") return undefined;
  const [min, max] = (control.options as number[]) ?? [0, 255];
  const id = typeof control.content[0] === "string" ? control.content[0] : control.label;

  return {
    id,
    label: control.label,
    min,
    max,
    value: max,
    showIf: control.showIf,
  };
}

function parseColorControl(control: ViaMenuControl | undefined): LightingColorControl | undefined {
  if (!control || control.type !== "color") return undefined;
  const id = typeof control.content[0] === "string" ? control.content[0] : control.label;
  return {
    id,
    label: control.label,
    value: "#8ad0ff",
    showIf: control.showIf,
  };
}

function parseLighting(raw: RawKick75BoardDefinition): LightingDefinition {
  const lightingMenu = raw.menus.find((menu) => menu.label === "Lighting");
  const lightingSection = lightingMenu?.content[0];
  const controls = lightingSection?.content ?? [];
  const effectControl = findControl(controls, "Effect");
  const effectOptions =
    effectControl?.type === "dropdown"
      ? (effectControl.options?.filter((item): item is string => typeof item === "string") ?? [])
      : [];

  return {
    menuLabel: lightingMenu?.label ?? "Lighting",
    sectionLabel: lightingSection?.label ?? "Backlight",
    supportedKeycodeFamilies: raw.keycodes,
    effects: effectOptions,
    selectedEffect: effectOptions[0] ?? "All Off",
    brightness: parseRangeControl(findControl(controls, "Brightness")),
    speed: parseRangeControl(findControl(controls, "Effect Speed")),
    color: parseColorControl(findControl(controls, "Color")),
  };
}

function sortCustomKeycodes(values: ViaCustomKeycode[]): ViaCustomKeycode[] {
  return [...values].sort((left, right) => left.title.localeCompare(right.title));
}

export function parseKick75BoardDefinition(raw: RawKick75BoardDefinition): BoardDefinition {
  return {
    name: raw.name,
    vendorId: raw.vendorId,
    productId: raw.productId,
    matrix: raw.matrix,
    keys: parseKeyboardLayout(raw.layouts.keymap),
    physicalLayoutOnly: true,
    lighting: parseLighting(raw),
    customKeycodes: sortCustomKeycodes(raw.customKeycodes),
  };
}
