import { describe, expect, it } from "vitest";
import { animationTime, signalProgress, cognitiveEvent, detailLevel, eventsAt, type CognitiveEvent } from "./cognitive";
import { layoutPanorama, traceLit } from "./panorama";
import { initialTaskState, taskReducer, type TaskState } from "./taskStore";

const base: CognitiveEvent = { seq: 0, ms: 100, stage: "memory", agent: "FILE", status: "observed", count: 1, refs: ["Regra"], action: "" };
const scene = () => layoutPanorama({ agents: [{ id: "MAESTRO", name: "Maestro", color: "#fff", own: [], uses: [] },
  { id: "FILE", name: "Arquivos", color: "#fff", own: ["File/Regra.md"], uses: [] }] });
describe("observatorio cognitivo", () => {
  it("never fabricates idle signals or turns operational success into verification", () => {
    expect(traceLit([], scene()).path).toEqual([]);
    expect(traceLit([{ ...base, stage: "verification", status: "completed" }], scene()).outcome).toBe("");
    expect(traceLit([{ ...base, stage: "verification", status: "uncertain" }], scene()).outcome).toBe("fail");
    expect(traceLit([{ ...base, stage: "verification", status: "verified" }], scene()).outcome).toBe("ok");
  });
  it("lights retrieved sources and keeps unsuccessful lookups quiet", () => {
    expect(traceLit([base], scene()).nodes.has("note:FILE:File/Regra.md")).toBe(true);
    expect(traceLit([base], scene()).path).toContain("e:note:FILE:File/Regra.md");
    const nerve = scene().edges.find((e) => e.id === "e:note:FILE:File/Regra.md");
    expect(nerve?.b).toBe("FILE"); // recuperacao conduz a fonte ate o agente
    expect(traceLit([{ ...base, count: 0, refs: [] }], scene()).path).toEqual([]);
  });
  it("replay includes only evidence available at the selected instant", () => {
    const later = { ...base, seq: 1, ms: 900, stage: "learning" as const };
    expect(eventsAt([base, later], 99)).toEqual([]);
    expect(eventsAt([base, later], 500)).toEqual([base]);
  });
  it("rejects cross-run, duplicate and malformed events", () => {
    const state = { ...initialTaskState, busy: true, runId: 4 };
    const send = (s: TaskState, run_id: number) => taskReducer(s, { type: "event", name: "cognitiveActivity", payload: { ...base, run_id }, now: 100 });
    expect(send(state, 3)).toBe(state);
    const accepted = send(state, 4);
    expect(accepted.cognitive).toEqual([base]);
    expect(send(accepted, 4)).toBe(accepted);
    expect(cognitiveEvent({ ...base, stage: "__proto__" })).toBeNull();
    expect(cognitiveEvent({ ...base, ms: -1 })).toBeNull();
  });
  it("disables the animation clock and limits detail on compact panels", () => {
    expect(signalProgress(99, 100)).toBe(0); // timestamp do RAF pode anteceder o efeito React
    expect(signalProgress(2500, 100)).toBe(1);
    expect(animationTime(900, true)).toBe(0);
    expect(detailLevel(1200, true)).toBe(1);
    expect(detailLevel(1200, false)).toBe(2);
  });
  it("does not double count a chat handoff and creates only observed tools", () => {
    const s = layoutPanorama({ agents: [], routing: { total: 1, routes: [{ route: "maestro", runs: 1, ok: 1, avg_ms: 1 }], agents: [], edges: [{ from: "conversa", to: "maestro", runs: 1 }] } });
    expect(s.edges.find((e) => e.id === "route:MAESTRO>stage:politicas")?.weight).toBe(1);
    expect(s.nodes.some((n) => n.kind === "tool")).toBe(false);
    const call = { ...base, stage: "model" as const, agent: "CHAT", action: "fixture-model" };
    const observed = layoutPanorama({ agents: [], events: [call] });
    expect(observed.edges.find((e) => e.b === "call:model:CHAT:fixture-model")?.a).toBe("stage:conversa");
  });
});
