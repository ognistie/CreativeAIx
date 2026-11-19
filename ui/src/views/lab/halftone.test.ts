import { describe, expect, it } from "vitest";
import { COLS, ROWS, halftone } from "./halftone";
import { AGENTS as ROOM_ORDER } from "./types";

const ink = (grid: Uint8Array) => grid.filter((v) => v >= 2).length / grid.length;

describe("ilustracoes em meio-tom dos agentes", () => {
  it("cada agente tem uma ilustracao propria, sempre igual", () => {
    for (const agent of ROOM_ORDER) {
      const grid = halftone(agent);
      expect(grid).toHaveLength(COLS * ROWS);
      expect(grid.every((v) => v >= 0 && v <= 3)).toBe(true);
      expect(halftone(agent)).toEqual(grid);
    }
  });

  it("figura bem desenhada: tem tinta de verdade sem virar um bloco chapado", () => {
    for (const agent of ROOM_ORDER) {
      const share = ink(halftone(agent));
      expect(share, agent).toBeGreaterThan(0.06);
      expect(share, agent).toBeLessThan(0.6);
      // os tres tons aparecem (meio-tom, nao silhueta)
      const levels = new Set(halftone(agent));
      expect([1, 2, 3].every((l) => levels.has(l)), agent).toBe(true);
    }
  });

  it("ilustracoes diferentes entre si", () => {
    const grids = ROOM_ORDER.map(halftone);
    for (let a = 0; a < grids.length; a++) {
      for (let b = a + 1; b < grids.length; b++) {
        let same = 0;
        for (let k = 0; k < grids[a]!.length; k++) if (grids[a]![k] === grids[b]![k]) same++;
        expect(same / grids[a]!.length, `${ROOM_ORDER[a]} x ${ROOM_ORDER[b]}`).toBeLessThan(0.85);
      }
    }
  });
});
