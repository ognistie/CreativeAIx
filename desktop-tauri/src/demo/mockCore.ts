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
  activitySummary: () => ({
    running: "",
    attention: [{ kind: "clarify", text: "Qual pasta devo organizar: Downloads ou Documentos?", task: "Organize meus arquivos" }],
    today: [
      { time: "14:02", task: "Crie uma planilha de gastos do mês com gráfico", ok: true, duration_ms: 48200, agents: ["DATA"], status: "ok" },
      { time: "11:40", task: "Abra o Excel e preencha a primeira linha", ok: false, duration_ms: 15300, agents: ["DESKTOP"], status: "falhou" },
    ],
    usage: {
      cost: 1.284, calls: 212, tokens: 318000, runs: 41, success_rate: 88,
      segments: [
        { agent: "DATA", cost: 0.52, share: 0.405 }, { agent: "WEB", cost: 0.31, share: 0.241 },
        { agent: "CODE", cost: 0.27, share: 0.21 }, { agent: "DESKTOP", cost: 0.184, share: 0.144 },
      ],
      daily: Array.from({ length: 14 }, (_, i) => ({ day: `${String(i + 1).padStart(2, "0")}/11`, cost: [0.02, 0.11, 0.08, 0, 0.14, 0.2, 0.05, 0.09, 0.12, 0, 0.07, 0.16, 0.1, 0.13][i] })),
    },
    heatmap: {
      rows: Array.from({ length: 7 }, (_, d) => Array.from({ length: 24 }, (_, h) => (h >= 9 && h <= 18 && d < 5 ? (h * 7 + d * 3) % 5 : h === 21 ? 1 : 0))),
      peak: 4,
      weekdays: ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"],
    },
  }),
  youProfile: () => ({
    ok: true, writable: true,
    sections: [
      { name: "Sobre mim", hint: "Quem você é e no que trabalha.", rel: "Você/Sobre mim.md", text: "Desenvolvedor, trabalho com produtos de IA." },
      { name: "Preferências", hint: "Como gosta que as coisas sejam feitas.", rel: "Você/Preferências.md", text: "Planilhas em português, com gráfico quando fizer sentido." },
      { name: "Evitar", hint: "O que os agentes nunca devem fazer.", rel: "Você/Evitar.md", text: "" },
    ],
  }),
  youSave: () => ({ ok: true }),
  brainOverview: () => ({
    ok: true, personal: "C:/Users/voce/Documents/AI Farm Agent", writable: true, edited: 2, removed: [],
    folders: ["10 Agentes", "20 Politicas", "60 Aprendizados"],
    notes: [
      { rel: "00 Maestro/Maestro.md", title: "Maestro", folder: "00 Maestro", layer: "base" },
      { rel: "10 Agentes/Dados.md", title: "Dados", folder: "10 Agentes", layer: "editada" },
      { rel: "10 Agentes/Web.md", title: "Web", folder: "10 Agentes", layer: "base" },
      { rel: "20 Politicas/Arquivos.md", title: "Arquivos", folder: "20 Politicas", layer: "base" },
      { rel: "60 Aprendizados/Excel abre devagar.md", title: "Excel abre devagar", folder: "60 Aprendizados", layer: "pessoal" },
    ],
  }),
  brainRead: ([rel]) => ({
    ok: true,
    rel,
    layer: String(rel).includes("Dados") ? "editada" : "base",
    links: ["Maestro", "Excel abre devagar"],
    backlinks: ["00 Maestro/Maestro.md"],
    text: [
      "# Dados",
      "",
      "Monta planilhas Excel com **fórmulas** e gráficos.",
      "",
      "## Regras",
      "",
      "- Totais calculados pelo app, nunca pelo modelo",
      "- Gráfico de pizza só com até 6 categorias",
      "",
      "> [!dica] Veja [[Excel abre devagar]] antes de abrir o Excel.",
      "",
      "Quem distribui o trabalho é o [[Maestro]].",
    ].join("\n"),
  }),
  brainSave: () => ({ ok: true }),
  brainSearch: ([q]) => ({ ok: true, items: [{ rel: "10 Agentes/Dados.md", title: "Dados", snippet: `…${q}… em planilhas com fórmulas` }] }),
  brainGraph: () => ({
    ok: true,
    nodes: ["Maestro", "Dados", "Web", "Arquivos", "Excel abre devagar"].map((t) => ({ id: t, title: t, folder: "" })),
    edges: [{ from: "Maestro", to: "Dados" }, { from: "Maestro", to: "Web" }, { from: "Maestro", to: "Arquivos" }, { from: "Dados", to: "Excel abre devagar" }],
  }),
  suggestionsList: () => ({ ok: true, items: [{ id: "s1", kind: "licao", title: "Abra o Excel e preencha a primeira linha", evidence: "Falhou: a janela do Excel não respondeu a tempo.", body: "", hint: "Escreva a regra que evita essa falha (o que o agente deve fazer diferente)." }] }),
  librarySearch: () => ({
    ok: true, verified_on: "2026-11-12",
    items: [
      { id: "harness", title: "Harness Engineering", level: "iniciante", order: 1, intro: "O harness é tudo o que fica em volta do modelo: ferramentas, regras, ambiente, feedback e verificações.", why: "A maior parte da qualidade de um agente vem do ambiente, não do prompt.", prereqs: [], practice: "Escreva no Harness uma regra para o agente de Dados e rode em modo Simular.", terms: ["harness", "ferramenta"], limits: "", article: [{ h: "O que é", p: ["Um modelo sozinho só gera texto. O harness dá mãos e olhos a ele."] }], readings: [{ title: "Building effective AI agents", authors: "Anthropic", year: 2024, url: "https://www.anthropic.com/research/building-effective-agents", kind: "didatico", venue: "", note: "Comece aqui." }] },
      { id: "evals", title: "Avaliação de agentes", level: "intermediario", order: 2, intro: "Como saber se o agente melhorou: tarefas, critérios e notas reproduzíveis.", why: "Sem avaliação, toda mudança é palpite.", prereqs: ["harness"], practice: "Rode um experimento no AI Research Lab.", terms: ["eval", "grader"], limits: "", readings: [] },
    ],
  }),
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
