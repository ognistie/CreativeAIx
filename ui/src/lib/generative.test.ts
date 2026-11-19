import { describe, expect, it } from "vitest";
import { GENERATIVE_STYLES, drawGenerative, generativeOf, hexToRgb, ramp, wallpaperOf, type Ctx } from "./generative";
import { SCENES, SCENE_IDS, sceneValue } from "./scenes";
import { COMBOS, PALETTES } from "../views/AppearancePanel";

const COLORS = { base: "#08090a", tones: ["#0e2523", "#131617", "#1a1626"] as [string, string, string], accent: "#16897e" };

function fakeCtx() {
  const calls = { rect: 0, arc: 0, fills: new Set<string>() };
  const ctx: Ctx = {
    fillStyle: "", imageSmoothingEnabled: true,
    fillRect() { calls.rect++; calls.fills.add(String(ctx.fillStyle)); },
    beginPath() {}, moveTo() {}, arc() { calls.arc++; }, fill() { calls.fills.add(String(ctx.fillStyle)); },
  };
  return { ctx, calls };
}

/** Amostra a cena numa grade: media e quanto da tela e "claro" (forma desenhada) */
function sample(id: (typeof SCENE_IDS)[number]) {
  const values: number[] = [];
  for (let j = 0; j < 36; j++) for (let i = 0; i < 64; i++) values.push(sceneValue(id, (i + 0.5) / 64, (j + 0.5) / 36));
  return values;
}

describe("papeis de parede gerativos", () => {
  it("id gen:<estilo>:<cena>, com o formato antigo (sem cena) valendo synthwave", () => {
    expect(GENERATIVE_STYLES).toEqual(["dither", "halftone"]);
    expect(generativeOf("gen:ascii")).toEqual({ style: "dither", scene: "retro" });
    expect(generativeOf("gen:ascii:praia")).toEqual({ style: "dither", scene: "praia" });
    expect(generativeOf("gen:halftone:aquario")).toEqual({ style: "halftone", scene: "aquario" });
    expect(wallpaperOf({ style: "dither", scene: "rio" })).toBe("gen:dither:rio");
    for (const other of ["", "gen:", "gen:matrix", "gen:ascii:marte", "gen:ascii:rio:x", "personal:abc", "catalog:x"]) {
      expect(generativeOf(other), other).toBeNull();
    }
  });

  it("toda cena tem luz entre 0 e 1 e um desenho de verdade (contraste, nao um degrade liso)", () => {
    expect(SCENES).toHaveLength(11);
    for (const id of SCENE_IDS) {
      const values = sample(id);
      expect(values.every((v) => v >= 0 && v <= 1), id).toBe(true);
      const bright = values.filter((v) => v > 0.6).length / values.length;
      const dark = values.filter((v) => v < 0.2).length / values.length;
      expect(bright, `${id}: formas claras`).toBeGreaterThan(0.01);
      expect(dark + bright, `${id}: contraste`).toBeGreaterThan(0.15);
    }
  });

  it("as cenas sao diferentes entre si", () => {
    const all = SCENE_IDS.map(sample);
    for (let a = 0; a < all.length; a++) {
      for (let b = a + 1; b < all.length; b++) {
        const diff = all[a]!.reduce((sum, v, k) => sum + Math.abs(v - all[b]![k]!), 0) / all[a]!.length;
        expect(diff, `${SCENE_IDS[a]} x ${SCENE_IDS[b]}`).toBeGreaterThan(0.08);
      }
    }
  });

  it("a rampa vai da base da paleta ate o destaque", () => {
    const r = ramp(COLORS);
    expect(r[0]).toBe("rgb(8 9 10)");
    expect(r.at(-1)).toBe("rgb(22 137 126)");
    expect(hexToRgb("rgb(1, 2, 3)")).toEqual([1, 2, 3]);
  });

  it("cada estilo desenha com o seu tipo de marca, em qualquer cena", () => {
    for (const style of GENERATIVE_STYLES) {
      for (const scene of ["retro", "aquario", "praia"] as const) {
        const { ctx, calls } = fakeCtx();
        const cells = drawGenerative(ctx, style, 640, 360, COLORS, scene);
        expect(cells, `${style}/${scene}`).toBeGreaterThan(300);
        expect(calls.fills.size, `${style}/${scene}`).toBeGreaterThan(3);
        if (style === "dither") expect(calls.rect).toBe(cells + 1);
        if (style === "halftone") expect(calls.arc).toBe(cells);
      }
    }
  });
});

describe("combinacoes da Aparencia", () => {
  it("cada combinacao e unica: paleta, cenario e destaque proprios", () => {
    const palettes = new Set(PALETTES.map(([id]) => id));
    expect(COMBOS.length).toBeGreaterThanOrEqual(14);
    for (const combo of COMBOS) {
      expect(palettes.has(combo.palette), combo.id).toBe(true);
      expect(combo.wallpaper === "" || generativeOf(combo.wallpaper) !== null, combo.id).toBe(true);
    }
    expect(new Set(COMBOS.map((c) => c.palette)).size).toBe(COMBOS.length);
    const scenes = COMBOS.map((c) => c.wallpaper).filter(Boolean);
    expect(new Set(scenes).size).toBe(scenes.length);
    for (const theme of ["aquario", "gatinhos", "frutas", "rio", "texas", "noite", "jardim", "bosque", "lago", "praia"]) {
      expect(COMBOS.some((c) => generativeOf(c.wallpaper)?.scene === theme), theme).toBe(true);
    }
  });
});
