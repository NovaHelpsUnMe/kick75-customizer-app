import { describe, expect, it } from "vitest";
import rawKick75 from "../src/content/kick75-via.json";
import supportedProfile from "./fixtures/via-profile-supported.json";
import unsupportedProfile from "./fixtures/via-profile-unsupported.json";
import { parseKick75BoardDefinition } from "../src/lib/via/parseKick75";
import { parseImportedProfile } from "../src/lib/via/parseImportedProfile";

describe("parseKick75BoardDefinition", () => {
  it("normalizes the real Kick75 VIA definition into a physical board model", () => {
    const parsed = parseKick75BoardDefinition(rawKick75);

    expect(parsed.name).toBe("NuPhy Kick75");
    expect(parsed.vendorId).toBe("0x19F5");
    expect(parsed.productId).toBe("0x32D5");
    expect(parsed.matrix.rows).toBe(6);
    expect(parsed.matrix.cols).toBe(17);
    expect(parsed.physicalLayoutOnly).toBe(true);
    expect(parsed.keys.length).toBe(81);
  });

  it("parses KLE-style layout widths and matrix positions correctly", () => {
    const parsed = parseKick75BoardDefinition(rawKick75);
    const enterKey = parsed.keys.find((key) => key.matrixPosition === "2,13");
    const leftShift = parsed.keys.find((key) => key.matrixPosition === "4,0");
    const space = parsed.keys.find((key) => key.matrixPosition === "5,6");

    expect(enterKey?.width).toBe(1.5);
    expect(leftShift?.width).toBe(2.25);
    expect(space?.width).toBe(6.25);
  });

  it("extracts the real lighting menu and custom keycodes", () => {
    const parsed = parseKick75BoardDefinition(rawKick75);

    expect(parsed.lighting.menuLabel).toBe("Lighting");
    expect(parsed.lighting.sectionLabel).toBe("Backlight");
    expect(parsed.lighting.effects).toContain("Reactive Nexus");
    expect(parsed.lighting.effects).toContain("position_mode");
    expect(parsed.lighting.brightness?.max).toBe(255);
    expect(parsed.lighting.speed?.showIf).toContain("!= 0");
    expect(parsed.customKeycodes).toHaveLength(25);
    expect(parsed.customKeycodes.some((item) => item.title === "Device Reset")).toBe(true);
    expect(parsed.customKeycodes.some((item) => item.title === "Side Next Color")).toBe(true);
  });
});

describe("parseImportedProfile", () => {
  it("accepts a narrow VIA-style profile with layer arrays aligned to board key order", () => {
    const board = parseKick75BoardDefinition(rawKick75);
    const result = parseImportedProfile(supportedProfile, board);

    expect(result.status).toBe("supported");
    if (result.status !== "supported") return;

    expect(result.profile.layerCount).toBe(2);
    expect(result.profile.layers[0]?.assignments[board.keys[0]!.id]).toBe("KC_ESC");
    expect(result.profile.layers[1]?.assignments[board.keys[0]!.id]).toBe("KC_GRV");
  });

  it("keeps the official board definition out of the profile-import path", () => {
    const board = parseKick75BoardDefinition(rawKick75);
    const result = parseImportedProfile(rawKick75, board);

    expect(result.status).toBe("unsupported");
    if (result.status !== "unsupported") return;

    expect(result.diagnostics[0]).toContain("does not contain");
  });

  it("rejects unsupported shapes with diagnostics", () => {
    const board = parseKick75BoardDefinition(rawKick75);
    const result = parseImportedProfile(unsupportedProfile, board);

    expect(result.status).toBe("unsupported");
    if (result.status !== "unsupported") return;

    expect(result.diagnostics[0]).toContain("does not contain");
  });
});
