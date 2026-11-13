// Nucleo de demonstracao para revisar as telas no navegador sem Python (abrir com ?demo).
// Fala o mesmo protocolo do desktop/server.py por um socket falso. Dados ficticios.

import type { SocketLike } from "../lib/core";

type Json = Record<string, unknown>;

const now = Date.now() / 1000;
const CONVERSATIONS = [
  { id: "c1", title: "Planilha de gastos de novembro", updated_at: now - 600, turns: 3 },
  { id: "c2", title: "Pesquisa sobre cafeterias", updated_at: now - 86400, turns: 2 },
  { id: "c3", title: "Organizar Downloads", updated_at: now - 3 * 86400, turns: 1 },
];

const HISTORY = [
  { id: "t1", task: "Crie uma planilha de gastos do mês com gráfico", success: true, duration_ms: 48200, created_at: now - 700, metrics: { api_calls: 6, tokens_est: 9100, cost_usd: 0.0412 }, agents: ["DATA"] },
  { id: "t2", task: "Pesquise no Google sobre cafeterias artesanais", success: true, duration_ms: 22100, created_at: now - 86500, metrics: { api_calls: 3, tokens_est: 4200, cost_usd: 0.0161 }, agents: ["WEB"] },
  { id: "t3", task: "Abra o Excel e preencha a primeira linha", success: false, duration_ms: 15300, created_at: now - 90000, error: "A janela do Excel não respondeu a tempo.", metrics: { api_calls: 2, tokens_est: 2600, cost_usd: 0.0094 }, agents: ["DESKTOP"] },
];

const METHODS: Record<string, (args: unknown[]) => unknown> = {
  uiSettings: () => ({ splash: true, mini_chat: true, stop_hotkey_label: "Ctrl+Alt+X" }),
  appearance: () => ({ mode: "escuro", palette: "abismo", accent: "#16897E", radius: "suave", motion: true }),
  providerStatus: () => ({
    ok: true,
    providers: [
      { name: "Anthropic", use: "Maestro e agentes", configured: true, next: "" },
      { name: "OpenAI", use: "Conversa por voz (GPT-Live)", configured: false, next: "Opcional. Coloque OPENAI_API_KEY no .env." },
    ],
  }),
  loadConversations: () => ({ items: CONVERSATIONS, current: "c0" }),
  openConversation: ([sid]) => ({
    id: sid,
    turns: [
      { said: "Crie uma planilha de gastos do mês", summary: "Criei Gastos-novembro.xlsx com as categorias e um gráfico de pizza.", success: true },
      { said: "valeu", kind: "chat", reply: "Por nada! Quer que eu some os totais por semana?" },
    ],
  }),
  renameConversation: () => true,
  deleteConversation: () => true,
  newSession: () => null,
  forceStop: () => null,
  loadHistory: () => ({ items: HISTORY, stats: { total: 3, success_rate: 66.7, total_cost_usd: 0.0667, avg_duration_ms: 28533 } }),
  getSettings: () => ({ splash: true, mini_chat: true, barge_in: true, earcon: true, live_conversation: false, hotkeys: { voice: "ctrl+alt+v", stop: "ctrl+alt+x", quick: "alt+space" } }),
  attachFiles: () => ({ files: [] }),
};

/** Socket falso: autentica, responde metodos e simula uma tarefa em executeTask. */
export function mockSocket(): SocketLike {
  const sock: SocketLike = {
    readyState: 0,
    onopen: null,
    onmessage: null,
    onclose: null,
    onerror: null,
    send(data: string) {
      const msg = JSON.parse(data) as Json;
      if ("token" in msg) {
        reply({ jsonrpc: "2.0", method: "hello", params: { protocol: 1 } });
        return;
      }
      const method = String(msg.method);
      const args = (msg.params as unknown[]) ?? [];
      if (method === "executeTask") simulate(String(args[0]), emit);
      const fn = METHODS[method];
      if ("id" in msg) reply({ jsonrpc: "2.0", id: msg.id, result: fn ? fn(args) : null });
    },
    close() {
      sock.readyState = 3;
    },
  };
  const reply = (m: Json) => setTimeout(() => sock.onmessage?.({ data: JSON.stringify(m) }), 15);
  const emit = (name: string, payload: unknown) => reply({ jsonrpc: "2.0", method: "event", params: { name, payload } });
  setTimeout(() => {
    sock.readyState = 1;
    sock.onopen?.({});
  }, 30);
  return sock;
}

function simulate(task: string, emit: (name: string, payload: unknown) => void) {
  const steps = [
    "[DATA] Montar a planilha com as categorias do mês",
    "[DATA] Inserir fórmulas de total e um gráfico de pizza",
    "[FILE] Salvar em Documentos como Gastos-novembro.xlsx",
  ];
  const at = (ms: number, fn: () => void) => setTimeout(fn, ms);
  at(100, () => emit("phaseChanged", { msg: "Entendendo o pedido" }));
  at(700, () => emit("planReady", { plan: { steps: steps.map((d) => ({ description: d })) } }));
  steps.forEach((d, i) => {
    at(1200 + i * 1400, () => emit("stepStart", { step: i + 1, desc: d, total: steps.length, progress: (i / steps.length) * 100 }));
    at(1900 + i * 1400, () => emit("stepDone", { step: i + 1, desc: d, ok: true, result: i === 2 ? "C:\\Users\\voce\\Documents\\Gastos-novembro.xlsx" : "ok", progress: ((i + 1) / steps.length) * 100 }));
    at(1950 + i * 1400, () => emit("apiUsage", { calls: (i + 1) * 2, tokens_est: (i + 1) * 3000, cost_usd: (i + 1) * 0.013 }));
  });
  const end = 1200 + steps.length * 1400;
  at(end, () => emit("taskDone", {}));
  at(end + 200, () => emit("contextExtracted", { folder: "C:\\Users\\voce\\Documents", files: ["Gastos-novembro.xlsx"] }));
  at(end + 400, () => emit("assistantMessage", { said: task, text: "Pronto! A planilha está em Documentos, com os totais por categoria e um gráfico de pizza." }));
  at(end + 500, () => emit("historyChanged", { entry: { task, success: true, duration_ms: end + 500, metrics: { api_calls: 6, tokens_est: 9000, cost_usd: 0.039 }, artifacts: { folder: "C:\\Users\\voce\\Documents", files: ["Gastos-novembro.xlsx"] } } }));
  at(end + 600, () => emit("executionFinished", { success: true }));
}
