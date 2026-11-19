import { describe, expect, it } from "vitest";
import { LABEL_H, LABEL_W, PER_PAGE, TONES, VIEW_H, VIEW_W, labelBox, layoutWorld, type LevelSpec } from "./branchLayout";

const path = (...levels: Array<[string, number, number?]>): LevelSpec[] =>
  levels.map(([key, count, open]) => ({ key, count, open }));

const FOLDERS = Array.from({ length: 120 }, (_, i) => `pasta ${i}`);

function noOverlap(boxes: Array<{ x: number; y: number }>, label: string) {
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i]!, b = boxes[j]!;
      expect(Math.abs(a.x - b.x) >= LABEL_W || Math.abs(a.y - b.y) >= LABEL_H, `${label}: ${i} x ${j}`).toBe(true);
    }
  }
}

describe("arvore do Cerebro", () => {
  it("a mesma pasta desenha sempre o mesmo galho; pastas diferentes, galhos diferentes", () => {
    const a = layoutWorld(path(["", 5, 1], ["Agentes", 4]));
    expect(layoutWorld(path(["", 5, 1], ["Agentes", 4]))).toEqual(a);
    expect(layoutWorld(path(["", 5, 1], ["Inbox", 4])).levels[1]!.pixels).not.toEqual(a.levels[1]!.pixels);
  });

  it("um raminho por filho visivel, no maximo uma pagina", () => {
    for (let n = 0; n <= PER_PAGE + 3; n++) expect(layoutWorld(path(["x", n])).levels[0]!.nodes).toHaveLength(Math.min(n, PER_PAGE));
  });

  it("abrir uma pasta faz brotar o galho dela a partir do icone dela, sem mexer nos galhos de antes", () => {
    const root = layoutWorld(path(["", 6]));
    const opened = layoutWorld(path(["", 6, 2], ["Agentes", 5]));
    expect(opened.levels[0]).toEqual(root.levels[0]);                      // a arvore de antes continua igual
    expect(opened.levels[1]!.anchor).toEqual(root.levels[0]!.nodes[2]!.tip); // o galho novo nasce na pasta aberta
    // e segue para o mesmo lado em que a pasta estava (em cima sobe, embaixo desce)
    const side = root.levels[0]!.nodes[2]!.side;
    const box = opened.levels[1]!.box;
    expect(side < 0 ? box.y0 < opened.levels[1]!.anchor[1] : box.y1 > opened.levels[1]!.anchor[1]).toBe(true);
  });

  it("subir um nivel devolve exatamente a arvore de antes", () => {
    const deep = layoutWorld(path(["", 6, 1], ["A", 5, 3], ["A/B", 4]));
    const up = layoutWorld(path(["", 6, 1], ["A", 5]));
    expect(deep.levels.slice(0, 2)).toEqual(up.levels);
  });

  it("a camera enquadra o galho da pasta aberta e deixa a origem dele a vista", () => {
    for (const folder of FOLDERS.slice(0, 40)) {
      const world = layoutWorld(path(["", 7, 3], [folder, 6, 2], [`${folder}/x`, 5]));
      const level = world.levels.at(-1)!;
      const [cx, cy] = world.camera;
      expect(level.anchor[0] + cx).toBeGreaterThanOrEqual(60);
      expect(level.anchor[0] + cx).toBeLessThan(VIEW_W / 2);
      const middle = (level.box.y0 + level.box.y1) / 2 + cy;
      expect(Math.abs(middle - VIEW_H / 2)).toBeLessThan(1);
    }
    const root = layoutWorld(path(["", 5]));
    expect(root.camera[0]).toBe(0);                                        // a raiz entra pela borda esquerda
    expect(Math.abs((root.levels[0]!.box.y0 + root.levels[0]!.box.y1) / 2 + root.camera[1] - VIEW_H / 2)).toBeLessThan(1);
  });

  it("nenhum nome encosta em outro, nem entre niveis diferentes", () => {
    for (const folder of FOLDERS) {
      const world = layoutWorld(path(["", PER_PAGE, 4], [folder, PER_PAGE, 1], [`${folder}/y`, PER_PAGE]));
      noOverlap(world.levels.flatMap((level) => level.nodes.map((node) => labelBox(node.tip))), folder);
    }
  });

  it("tudo em pixels alinhados a grade, um caminho por tom", () => {
    const { pixels } = layoutWorld(path(["Agentes", 4])).levels[0]!;
    expect(pixels).toHaveLength(TONES);
    expect(pixels.join("").length).toBeGreaterThan(1000);
    for (const d of pixels) expect(d === "" || /^(M-?\d+ -?\d+h3v3h-3z)+$/.test(d)).toBe(true);
    const coords = [...pixels.join("").matchAll(/M(-?\d+) (-?\d+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
    expect(coords.every(([x, y]) => x! % 3 === 0 && y! % 3 === 0)).toBe(true);
  });
});
