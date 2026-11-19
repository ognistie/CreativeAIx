import { describe, expect, it } from "vitest";
import theme from "../../../../app/design/theme.json";
import { hexToRgb, zoneRamps } from "../generative";
import { SCENE_IDS } from "../scenes";
import { COMBOS } from "../../views/AppearancePanel";
import { artFor } from "./art";

// Todas as paletas (claras e escuras) x todos os destaques das combinacoes x todas as cenas: as quatro regioes de
// cor tem que se separar do fundo o bastante para a cena aparecer (contraste de luminancia relativa, WCAG).

const lum = (c: string) => {
  const ch = hexToRgb(c).map((v) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * ch[0]! + 0.7152 * ch[1]! + 0.0722 * ch[2]!;
};
const contrast = (a: string, b: string) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
const toHex = (css: string) => {
  const [r, g, b] = hexToRgb(css);
  return "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
};

describe("paletas x cenas", () => {
  const palettes = theme.palettes as unknown as Record<"light" | "dark", Record<string, string[]>>;
  const accents = [...new Set(COMBOS.map((c) => c.accent.toUpperCase()))];

  it("em toda paleta, com todo destaque e em toda cena, assunto e luzes se destacam do fundo", () => {
    const weak: string[] = [];
    let checked = 0;
    for (const mode of ["dark", "light"] as const) {
      for (const [name, tones] of Object.entries(palettes[mode])) {
        for (const accent of accents) {
          for (const scene of SCENE_IDS) {
            const colors = { base: tones[0]!, tones: [tones[1]!, tones[2]!, tones[3]!] as [string, string, string], accent };
            const ramps = zoneRamps(colors, artFor(scene).hues).map((r) => r.map(toHex));
            const base = colors.base;
            // luz forte (sol, lua, olhos) e o assunto no meio-tom precisam aparecer contra a base
            const light = contrast(base, ramps[3]![7]!), subject = contrast(base, ramps[2]![5]!);
            checked++;
            if (light < 1.7 || subject < 1.45) weak.push(`${mode}/${name}/${accent}/${scene}: luz ${light.toFixed(2)} assunto ${subject.toFixed(2)}`);
          }
        }
      }
    }
    expect(checked).toBeGreaterThan(1000);
    expect(weak, weak.slice(0, 12).join("\n")).toEqual([]);
  });
});
