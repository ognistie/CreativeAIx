import { describe, expect, it } from "vitest";
import { initialTaskState, phaseIndex, taskReducer, usageLine, type TaskAction, type TaskState } from "./taskStore";

const ev = (name: string, payload: unknown, now = 1000): TaskAction => ({ type: "event", name, payload, now });
const run = (actions: TaskAction[], from: TaskState = initialTaskState) => actions.reduce(taskReducer, from);

describe("taskReducer", () => {
  it("follows a successful task from request to history entry", () => {
    const s = run([
      { type: "start", text: "abre o excel", dryRun: false, now: 0 },
      ev("phaseChanged", { msg: "Planejando" }),
      ev("planReady", { plan: { steps: [{ description: "[DESKTOP] Abrir o Excel", action: "open" }] } }),
      ev("stepStart", { step: 1, desc: "[DESKTOP] Abrir o Excel", total: 1, progress: 50 }),
      ev("stepDone", { step: 1, ok: true, result: "aberto", progress: 100 }),
      ev("taskDone", {}),
      ev("historyChanged", { entry: { task: "abre o excel", success: true, duration_ms: 4200, metrics: { api_calls: 2, tokens_est: 1500, cost_usd: 0.01 } } }),
      ev("executionFinished", {}),
    ]);
    expect(s.status).toBe("done");
    expect(s.busy).toBe(false);
    expect(s.plan).toEqual([{ agent: "DESKTOP", text: "Abrir o Excel" }]);
    expect(s.steps).toEqual([{ kind: "step", n: 1, agent: "DESKTOP", desc: "Abrir o Excel", state: "ok", result: "aberto" }]);
    expect(phaseIndex(s)).toBe(4);
    expect(usageLine(s, s.finishedMs!)).toBe("4s  ·  2 chamadas  ·  1,5k tokens  ·  US$ 0,0100");
  });

  it("archives the previous request when a new one starts", () => {
    const s = run([
      { type: "start", text: "pedido 1", dryRun: false, now: 0 },
      ev("assistantMessage", { said: "pedido 1", text: "Feito." }),
      ev("historyChanged", { entry: { task: "pedido 1", success: true } }),
      ev("executionFinished", {}),
      { type: "start", text: "pedido 2", heard: "Pedido 2.", dryRun: false, now: 5000 },
    ]);
    expect(s.turns).toEqual([{ said: "pedido 1", resolved: "", status: "done", summary: "Feito." }]);
    expect(s.task).toBe("pedido 2");
    expect(s.heardText).toBe("");          // o ouvido igual ao pedido nao repete
    expect(s.steps).toEqual([]);
  });

  it("clarification and limitation keep the question instead of an error", () => {
    const start: TaskAction = { type: "start", text: "faz aquilo", dryRun: false, now: 0 };
    expect(run([start, ev("errorRaised", { kind: "clarification", msg: "Qual arquivo?" })])).toMatchObject({ status: "clarify", question: "Qual arquivo?" });
    expect(run([start, ev("errorRaised", { kind: "limitation" })])).toMatchObject({ status: "limited" });
    expect(run([start, ev("errorRaised", { msg: "quebrou" })])).toMatchObject({ status: "failed", errorMsg: "quebrou" });
  });

  it("plan review waits for approval and clears when decided", () => {
    let s = run([
      { type: "start", text: "apaga a pasta", dryRun: false, now: 0 },
      ev("planReview", { token: "t1", effect: true, spoken_code: "42", plan: { summary: "Apagar", steps: ["Mover para a lixeira"] } }),
    ]);
    expect(s.review).toEqual({ token: "t1", effect: true, summary: "Apagar", steps: ["Mover para a lixeira", "Por voz, diga: confirmo 42"] });
    expect(s.phaseMsg).toBe("Aguardando sua aprovação");
    s = taskReducer(s, { type: "reviewDecided" });
    expect(s.review).toBeNull();
  });

  it("only warnings and errors during a run become notes", () => {
    const s = run([
      ev("logEntry", { level: "ERROR", msg: "antes de rodar" }),
      { type: "start", text: "x", dryRun: false, now: 0 },
      ev("logEntry", { level: "INFO", msg: "info" }),
      ev("logEntry", { level: "WARN", msg: "cuidado", agent: "WEB" }),
      ev("logEntry", { level: "ERROR", msg: "Step falhou: duplicado" }),
    ]);
    expect(s.steps).toEqual([{ kind: "note", n: -1, agent: "WEB", desc: "cuidado", state: "warn", result: "" }]);
  });

  it("does not reset the conversation while running", () => {
    const s = run([{ type: "start", text: "x", dryRun: false, now: 0 }, ev("phaseChanged", {}), { type: "newConversation" }]);
    expect(s.task).toBe("x");
  });

  it("a late reply of the previous run never lands on the same request repeated", () => {
    // Bug: o casamento era pelo texto; "de novo" com o mesmo texto recebia a resposta da execucao anterior
    let s = run([
      { type: "start", text: "resume a pasta", dryRun: false, now: 0 },
      ev("phaseChanged", { msg: "Entendendo", run_id: 1 }),
      ev("historyChanged", { entry: { task: "resume a pasta", run_id: 1, success: true } }),
      ev("executionFinished", {}),
      { type: "start", text: "resume a pasta", dryRun: false, now: 5000 },
    ]);
    s = taskReducer(s, ev("assistantMessage", { said: "resume a pasta", text: "resposta velha", run_id: 1 }));
    expect(s.assistantText).toBe("");                       // ainda sem fase da nova execucao: recusa
    s = run([ev("phaseChanged", { msg: "Entendendo", run_id: 2 }),
      ev("assistantMessage", { said: "resume a pasta", text: "resposta velha", run_id: 1 }),
      ev("historyChanged", { entry: { task: "resume a pasta", run_id: 1, success: false, error: "x" } })], s);
    expect(s.assistantText).toBe("");
    expect(s.status).toBe("running");                       // historico da execucao 1 nao fecha a 2
    s = taskReducer(s, ev("assistantMessage", { said: "resume a pasta", text: "resposta nova", run_id: 2 }));
    expect(s.assistantText).toBe("resposta nova");
    expect(s.turns[0]?.summary).toBe("");                   // o pedido anterior ficou sem a resposta velha
  });

  it("streams the chat answer and keeps it whole in the conversation", () => {
    const long = "## Análise\n" + "- ponto\n".repeat(200);
    let s = run([
      { type: "start", text: "analise a pasta", dryRun: false, now: 0 },
      ev("phaseChanged", { msg: "Entendendo", run_id: 7 }),
      ev("answerDelta", { run_id: 7, text: "## Aná" }),
      ev("answerDelta", { run_id: 6, text: "outra execução" }),
    ]);
    expect(s.streamText).toBe("## Aná");
    s = run([ev("answerReady", { msg: long, run_id: 7 }), ev("executionFinished", {}),
      { type: "start", text: "e o segundo ponto?", dryRun: false, now: 9000 }], s);
    expect(s.streamText).toBe("");
    expect(s.turns.at(-1)?.summary).toBe(long);              // antes: cortado em 400 letras
  });

  it("reopens a saved conversation", () => {
    const s = taskReducer(initialTaskState, {
      type: "showConversation",
      turns: [{ said: "oi", kind: "chat", reply: "olá" }, { said: "faz", success: false, summary: "não deu" }],
    });
    expect(s.turns.map((t) => t.status)).toEqual(["done", "failed"]);
    expect(s.status).toBe("idle");
  });
});
