import { describe, expect, it } from "vitest";
import { layoutAgentSpine, SPINE_H, SPINE_W, usesFromGraph } from "./agentSpine";

const input = [
  { id: "MAESTRO", own: ["00 Maestro/Rotas.md", "00 Maestro/Como delegar.md"], uses: ["20 Politicas/POL-001.md", "30 Tarefas/Salvar.md"] },
  { id: "WEB", own: ["10 Agentes/Web/A.md", "10 Agentes/Web/B.md"], uses: ["20 Politicas/POL-001.md"] },
  { id: "DESKTOP", own: ["10 Agentes/Desktop/A.md"], uses: ["30 Tarefas/Salvar.md", "20 Politicas/POL-001.md"] },
  { id: "CODE", own: [], uses: [] },
];

describe("layoutAgentSpine", () => {
  it("o Maestro fica no cerebro e cada outro agente ganha uma vertebra e um nervo, alternando os lados", () => {
    const s = layoutAgentSpine(input);
    expect(s.brain.agent).toBe("MAESTRO");
    expect(s.brain.notes.map((n) => n.rel)).toEqual(input[0]!.own);
    expect(s.nerves.map((n) => n.id)).toEqual(["WEB", "DESKTOP", "CODE"]);
    expect(s.nerves.map((n) => n.side)).toEqual([-1, 1, -1]);
    // desenho em pixels, como a arvore: medula, vertebras, cerebro e nervos tem tracos
    expect(s.cord.pixels.join("").length).toBeGreaterThan(0);
    expect(s.bones.join("").length).toBeGreaterThan(0);
    expect(s.brain.pixels.join("").length).toBeGreaterThan(0);
    for (const n of s.nerves) expect(n.pixels.join("").length).toBeGreaterThan(0);
    // nervos em pares: os dois primeiros saem da mesma vertebra, um de cada lado
    expect(s.nerves[0]!.level).toBe(s.nerves[1]!.level);
    // os niveis descem a coluna
    const levels = s.nerves.map((n) => n.level);
    expect([...levels].sort((a, b) => a - b)).toEqual(levels);
  });

  it("tudo cabe no desenho", () => {
    const s = layoutAgentSpine(input);
    const points = [...s.brain.notes, ...s.nerves.flatMap((n) => [...n.notes, { x: n.tip[0], y: n.tip[1] }]), ...s.shared];
    for (const p of points) {
      expect(p.x).toBeGreaterThan(0);
      expect(p.x).toBeLessThan(SPINE_W);
      expect(p.y).toBeGreaterThan(0);
      expect(p.y).toBeLessThan(SPINE_H);
    }
  });

  it("um ganglio por nota da pasta e contas na medula so para notas de mais de um agente", () => {
    const s = layoutAgentSpine(input);
    expect(s.nerves.find((n) => n.id === "WEB")!.notes.map((n) => n.rel)).toEqual(["10 Agentes/Web/A.md", "10 Agentes/Web/B.md"]);
    const shared = Object.fromEntries(s.shared.map((f) => [f.rel, f.owners]));
    expect(shared["20 Politicas/POL-001.md"]).toEqual(["DESKTOP", "MAESTRO", "WEB"]);
    expect(shared["30 Tarefas/Salvar.md"]).toEqual(["DESKTOP", "MAESTRO"]);
    expect(Object.keys(shared)).toHaveLength(2);
  });

  it("muitas notas: o desenho mostra 12 por nervo e conta o resto", () => {
    const many = Array.from({ length: 20 }, (_, i) => `10 Agentes/Web/N${i}.md`);
    const s = layoutAgentSpine([{ id: "WEB", own: many, uses: [] }]);
    expect(s.nerves[0]!.notes).toHaveLength(12);
    expect(s.nerves[0]!.hidden).toBe(8);
  });

  it("e deterministico", () => {
    expect(JSON.stringify(layoutAgentSpine(input))).toBe(JSON.stringify(layoutAgentSpine(input)));
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
