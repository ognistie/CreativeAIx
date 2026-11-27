import { describe, expect, it } from "vitest";
import { clampCamera, curvePoints, fibonacciSphere, layoutPanorama, liveLit, pick, project, VIEWS, type PanoramaInput } from "./panorama";

const input: PanoramaInput = {
  agents: [
    { id: "MAESTRO", name: "Maestro", color: "#8b5cf6", own: ["00 Maestro/Regras.md", "00 Maestro/Fonte.md"], uses: ["20 Politicas/POL-001.md"] },
    { id: "WEB", name: "Web", color: "#3b82f6", own: ["10 Agentes/Web/Web.md"], uses: ["20 Politicas/POL-001.md"] },
    { id: "DESKTOP", name: "Desktop", color: "#14b8a6", own: ["10 Agentes/Desktop/A.md", "10 Agentes/Desktop/B.md"], uses: [] },
  ],
  routing: {
    total: 10,
    routes: [{ route: "conversa", runs: 6, ok: 6, avg_ms: 3000 }, { route: "maestro", runs: 4, ok: 3, avg_ms: 12000 }],
    agents: [{ agent: "DESKTOP", runs: 4, ok: 4 }],
    edges: [{ from: "conversa", to: "maestro", runs: 2 }, { from: "maestro", to: "DESKTOP", runs: 4 }],
  },
  evolution: {
    plans: [{ key: "k1", template: "abrir <app>", status: "promoted", successes: 4, failures: 0, streak: 3, replays: 2, agents: ["DESKTOP"] }],
    hypotheses: [{ id: "h1", agent: "WEB", objective: "fontes oficiais", result: "refutada" }],
    summary: { promoted: 1, candidate: 0, blocked: 0, hypotheses: 1 },
  },
};

describe("layoutPanorama", () => {
  const scene = layoutPanorama(input);

  it("places every layer: core, agents, notes, shared memory, routing, evolution", () => {
    const kinds = (k: string) => scene.nodes.filter((n) => n.kind === k);
    expect(kinds("core")).toHaveLength(1);
    expect(kinds("agent").map((n) => n.id)).toEqual(["WEB", "DESKTOP"]);
    expect(kinds("note")).toHaveLength(5);
    expect(kinds("shared").map((n) => n.rel)).toEqual(["20 Politicas/POL-001.md"]);   // usada por 2 agentes
    expect(kinds("stage").map((n) => n.id)).toContain("stage:conversa");
    expect(kinds("plan")[0]!.status).toBe("promoted");
    expect(kinds("hypothesis")[0]!.color).toBe("#e05a5a");                             // refutada
  });

  it("is deterministic and every edge points to a real node", () => {
    expect(layoutPanorama(input).nodes.map((n) => n.pos)).toEqual(scene.nodes.map((n) => n.pos));
    for (const e of scene.edges) {
      expect(scene.byId.has(e.a), e.id).toBe(true);
      expect(scene.byId.has(e.b), e.id).toBe(true);
    }
  });

  it("route thickness follows real traffic", () => {
    const w = (id: string) => scene.edges.find((e) => e.id === id)!.weight;
    expect(w("route:stage:entendimento>stage:conversa")).toBeCloseTo(0.6);
    expect(w("route:stage:conversa>MAESTRO")).toBeCloseTo(0.2);                       // conversa entregou ao Maestro
    expect(w("traffic:DESKTOP")).toBe(1);
    expect(w("traffic:WEB")).toBe(0);
  });

  it("notes sit in a cloud around their own agent", () => {
    const desk = scene.byId.get("DESKTOP")!.pos;
    for (const n of scene.nodes.filter((x) => x.kind === "note" && x.agent === "DESKTOP")) {
      const d = Math.hypot(n.pos[0] - desk[0], n.pos[1] - desk[1], n.pos[2] - desk[2]);
      expect(d).toBeGreaterThan(30);
      expect(d).toBeLessThan(70);
    }
  });
});

describe("camera", () => {
  const cam = { ...VIEWS.geral, target: [0, 0, 0] as const };

  it("projects the target to the center and nearer points bigger", () => {
    const c = project([0, 0, 0], cam, 800, 600);
    expect(c.x).toBeCloseTo(400);
    expect(c.y).toBeCloseTo(300);
    const near = project([0, 0, 300], { ...cam, yaw: 0, pitch: 0 }, 800, 600);
    const far = project([0, 0, -300], { ...cam, yaw: 0, pitch: 0 }, 800, 600);
    expect(near.k).toBeGreaterThan(far.k);
    expect(project([0, 0, 5000], { ...cam, yaw: 0, pitch: 0 }, 800, 600).visible).toBe(false);   // atras da camera
  });

  it("clamps zoom and tilt", () => {
    const c = clampCamera({ ...cam, pitch: 3, dist: 10 });
    expect(c.pitch).toBeLessThanOrEqual(1.25);
    expect(c.dist).toBeGreaterThanOrEqual(320);
  });

  it("curves start and end at the nodes and bend in the middle", () => {
    const pts = curvePoints([0, 0, 0], [100, 0, 0], 40, 10);
    expect(pts[0]).toEqual([0, 0, 0]);
    expect(pts[10]).toEqual([100, 0, 0]);
    expect(pts[5]![1]).toBeGreaterThan(15);
  });

  it("picks the nearest node under the pointer", () => {
    const scene = layoutPanorama(input);
    const target = scene.byId.get("MAESTRO")!;
    const p = project(target.pos, VIEWS.geral, 1000, 700);
    expect(pick(scene.nodes, VIEWS.geral, 1000, 700, p.x, p.y)?.id).toBe("MAESTRO");
    expect(pick(scene.nodes, VIEWS.geral, 1000, 700, -500, -500)).toBeNull();
  });
});

describe("liveLit", () => {
  const scene = layoutPanorama(input);
  const base = { busy: true, status: "running", route: "", planAgents: [], steps: [], review: false };

  it("lights only the entry while the request is being understood", () => {
    const lit = liveLit(base, scene.edges);
    expect(lit.path).toEqual(["route:stage:pedido>stage:entendimento"]);
  });

  it("follows the chat handing an action to the Maestro and down to the agent", () => {
    const lit = liveLit({ ...base, route: "conversa→maestro", planAgents: ["DESKTOP"], steps: [{ agent: "DESKTOP", state: "running" }] }, scene.edges);
    expect(lit.path).toEqual([
      "route:stage:pedido>stage:entendimento", "route:stage:entendimento>stage:conversa", "route:stage:conversa>MAESTRO",
      "route:MAESTRO>stage:politicas", "traffic:DESKTOP",
    ]);
    expect([...lit.working]).toEqual(["DESKTOP"]);
  });

  it("a chat answer stays in the chat and a finished run flashes its outcome", () => {
    const chat = liveLit({ ...base, steps: [{ agent: "CHAT", state: "ok" }] }, scene.edges);
    expect(chat.nodes.has("stage:conversa")).toBe(true);
    expect(chat.nodes.has("stage:politicas")).toBe(false);
    expect(liveLit({ ...base, busy: false, status: "done", route: "atalho" }, scene.edges).outcome).toBe("ok");
    expect(liveLit({ ...base, busy: false, status: "idle" }, scene.edges).path).toEqual([]);
  });

  it("spreads points evenly on a sphere", () => {
    const pts = fibonacciSphere(20, 50);
    for (const p of pts) expect(Math.hypot(...p)).toBeCloseTo(50, 0);
  });
});
