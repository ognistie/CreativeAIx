import { describe, expect, it } from "vitest";
import { failedSteps, isFailure } from "./AgentWork";

const task = (state: string, events: Array<Record<string, unknown>>) =>
  ({ id: "t1", goal: "salvar", state, started_at: "", events: events.map((e) => ({ agent: "", action: "", status: "", result: "", ...e })) }) as Parameters<typeof isFailure>[0];

describe("aba Erros", () => {
  it("acha o passo que falhou e o agente dele mesmo numa tarefa concluida", () => {
    const t = task("completed", [
      { type: "step_started", step: 1, agent: "DESKTOP", action: "app_search" },
      { type: "step_finished", step: 1, action: "app_search", ok: true },
      { type: "step_started", step: 2, agent: "DESKTOP", action: "app_task" },
      { type: "step_finished", step: 2, action: "app_task", ok: false, result: "janela nao encontrada" },
    ]);
    expect(failedSteps(t).map((e) => [e.step, e.agent, e.result])).toEqual([[2, "DESKTOP", "janela nao encontrada"]]);
    expect(isFailure(t, "DESKTOP")).toBe(true);
    expect(isFailure(t, "WEB")).toBe(false);
  });

  it("falha ou interrupcao da tarefa conta mesmo sem passo marcado", () => {
    expect(isFailure(task("failed", []), "WEB")).toBe(true);
    expect(isFailure(task("interrupted", []), "WEB")).toBe(true);
    expect(isFailure(task("completed", [{ type: "step_finished", step: 1, ok: true }]), "WEB")).toBe(false);
  });
});
