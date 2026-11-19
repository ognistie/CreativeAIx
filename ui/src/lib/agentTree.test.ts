import { describe, expect, it } from "vitest";
import { layoutAgentTree, TREE_H, TREE_W, usesFromGraph } from "./agentTree";

const input = [
  { id: "MAESTRO", own: ["00 Maestro/Rotas.md"], uses: ["20 Politicas/POL-001.md", "30 Tarefas/Salvar.md"] },
  { id: "WEB", own: ["10 Agentes/Web/A.md", "10 Agentes/Web/B.md"], uses: ["20 Politicas/POL-001.md"] },
  { id: "DESKTOP", own: ["10 Agentes/Desktop/A.md"], uses: ["30 Tarefas/Salvar.md", "20 Politicas/POL-001.md"] },
  { id: "CODE", own: [], uses: [] },
];

describe("layoutAgentTree", () => {
  it("poe o Maestro na copa e os outros agentes em galhos alternados", () => {
    const tree = layoutAgentTree(input);
    expect(tree.crown).toBe("MAESTRO");
    expect(tree.branches.map((b) => b.id)).toEqual(["WEB", "DESKTOP", "CODE"]);
    expect(tree.branches.map((b) => b.side)).toEqual([-1, 1, -1]);
    for (const b of tree.branches) {
      expect(b.tip[0]).toBeGreaterThanOrEqual(0);
      expect(b.tip[0]).toBeLessThanOrEqual(TREE_W);
      expect(b.tip[1]).toBeGreaterThan(0);
      expect(b.tip[1]).toBeLessThan(TREE_H);
      expect(b.flow.startsWith("M")).toBe(true);
    }
  });

  it("uma folha por nota da pasta e frutos so para notas de mais de um agente", () => {
    const tree = layoutAgentTree(input);
    expect(tree.branches.find((b) => b.id === "WEB")!.leaves.map((l) => l.rel)).toEqual(["10 Agentes/Web/A.md", "10 Agentes/Web/B.md"]);
    const fruits = Object.fromEntries(tree.fruits.map((f) => [f.rel, f.owners]));
    expect(fruits["20 Politicas/POL-001.md"]).toEqual(["DESKTOP", "MAESTRO", "WEB"]);
    expect(fruits["30 Tarefas/Salvar.md"]).toEqual(["DESKTOP", "MAESTRO"]);
    expect(tree.fruits[0]!.rel).toBe("20 Politicas/POL-001.md");
  });

  it("e deterministica", () => {
    expect(JSON.stringify(layoutAgentTree(input))).toBe(JSON.stringify(layoutAgentTree(input)));
  });
});

describe("usesFromGraph", () => {
  it("so conta notas fora da pasta do agente citadas pelas notas dele", () => {
    const uses = usesFromGraph(
      { WEB: "10 Agentes/Web" },
      [{ from: "10 Agentes/Web/A.md", to: "20 Politicas/P.md" }, { from: "10 Agentes/Web/A.md", to: "10 Agentes/Web/B.md" },
       { from: "Outra.md", to: "20 Politicas/Q.md" }],
      { WEB: ["10 Agentes/Web/A.md", "10 Agentes/Web/B.md"] },
    );
    expect(uses.WEB).toEqual(["20 Politicas/P.md"]);
  });
});
