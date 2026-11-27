// Nucleo de demonstracao para revisar as telas no navegador sem Python (abrir com ?demo).
// Fala o mesmo protocolo do desktop/server.py por um socket falso. Dados ficticios.

import type { SocketLike } from "../lib/core";

type Json = Record<string, unknown>;
type LibFixture = { verified_on: string; topics: Array<{ id: string; level: string; title: string; intro: string; markdown: string } & Json> };

const now = Date.now() / 1000;
const CONVERSATIONS = [
  { id: "c1", title: "Planilha de gastos de novembro", updated_at: now - 600, turns: 3 },
  { id: "c2", title: "Pesquisa sobre cafeterias", updated_at: now - 86400, turns: 2 },
  { id: "c3", title: "Organizar Downloads", updated_at: now - 3 * 86400, turns: 1 },
];

const FIXTURES: Record<string, () => Promise<unknown>> = import.meta.env.DEV ? import.meta.glob(["./library.fixture.json", "./studio.fixture.json"]) : {};
type StudioFixture = Record<string, { spec: Json; memory: Json; sources: Record<string, string> }>;
async function studioFixture(): Promise<StudioFixture> {
  const load = FIXTURES["./studio.fixture.json"];
  return load ? ((await load()) as { default: StudioFixture }).default : {};
}
async function libFixture(): Promise<LibFixture> {
  const load = FIXTURES["./library.fixture.json"];
  if (!load) return { verified_on: "", topics: [] };
  return ((await load()) as { default: LibFixture }).default;
}

const JOURNAL_ROWS = [
  { id: "j1", date: "2026-11-13", title: "Ideias do app", folder: "notas", summary: "Mini chat mais limpo, atalhos de voz e uma biblioteca com cards maiores.", tags: ["produto"], private: false, priorities: 1, open_tasks: 2 },
  { id: "j2", date: "2026-11-11", title: "Reunião de segunda", folder: "notas", summary: "Prazos da entrega 3 e quem revisa o fluxo de aprovação.", tags: ["reuniao"], private: true, priorities: 0, open_tasks: 0 },
  { id: "j3", date: "2026-11-07", title: "Leituras da semana", folder: "notas", summary: "Context engineering e avaliação de agentes: separar o que o agente diz do que ele fez.", tags: ["estudo", "produto"], private: false, priorities: 0, open_tasks: 1 },
  { id: "j4", date: "2026-11-14", title: "Fechamento do mês", folder: "rotinas", summary: "Exportar extratos, conferir planilha de gastos e arquivar notas fiscais.", tags: ["financas"], private: false, priorities: 2, open_tasks: 3 },
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
    can_store: true,
    models: { strong: { chosen: "", default: "claude-sonnet-5" }, fast: { chosen: "deepseek:deepseek-chat", default: "claude-sonnet-5" } },
    catalog: [
      { name: "anthropic", label: "Anthropic (Claude)", local: false, needs_key: true, configured: true, stored: false,
        signup: "https://console.anthropic.com", example: "claude-sonnet-5", images: true, tools: true, web_search: true,
        key_env: "ANTHROPIC_API_KEY", env_detected: true, custom: false, base_url: "" },
      { name: "deepseek", label: "DeepSeek", local: false, needs_key: true, configured: true, stored: true,
        signup: "https://platform.deepseek.com/api_keys", example: "deepseek:deepseek-chat", images: false, tools: true, web_search: false,
        key_env: "DEEPSEEK_API_KEY", env_detected: false, custom: false, base_url: "" },
      { name: "openrouter", label: "OpenRouter (vários modelos com um crédito)", local: false, needs_key: true, configured: false, stored: false,
        signup: "https://openrouter.ai/keys", example: "openrouter:qwen/qwen3-coder", images: true, tools: true, web_search: false,
        key_env: "OPENROUTER_API_KEY", env_detected: false, custom: false, base_url: "" },
      { name: "ollama", label: "Ollama (local)", local: true, needs_key: false, configured: true, stored: false,
        signup: "https://ollama.com/download", example: "ollama:qwen3", images: true, tools: true, web_search: false,
        key_env: "", env_detected: false, custom: false, base_url: "" },
    ],
  }),
  providerModels: () => ({ ok: true, models: ["deepseek:deepseek-chat", "deepseek:deepseek-reasoner"] }),
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
  getSettings: () => ({ splash: true, mini_chat: true, barge_in: true, earcon: true, live_conversation: false, authorization: "enforce", hotkeys: { voice: "ctrl+alt+v", stop: "ctrl+alt+x", quick: "alt+space" } }),
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
  journalFolders: () => ({
    ok: true, available: true, use_in_brain: false,
    folders: [
      { key: "notas", name: "Notas", count: 3, recent: ["Ideias do app", "Reunião de segunda", "Leituras da semana"], private: 1 },
      { key: "rotinas", name: "Rotinas", count: 2, recent: ["Fechamento do mês", "Backup das fotos"], private: 0 },
      { key: "agentes", name: "Notas para os agentes", count: 1, recent: ["Prefiro planilhas em Documentos"], private: 0 },
      { key: "assuntos", name: "Assuntos", count: 0, recent: [], private: 0 },
    ],
  }),
  journalDates: () => ({ ok: true, dates: ["2026-11-03", "2026-11-07", "2026-11-11", "2026-11-13", "2026-11-14"] }),
  journalList: ([, , day]) => ({ ok: true, available: true, tags: [], items: JOURNAL_ROWS.filter((r) => !day || r.date === day) }),
  journalListIn: () => ({ ok: true, available: true, tags: ["produto", "reuniao"], items: JOURNAL_ROWS }),
  journalGet: () => ({
    ok: true,
    entry: {
      id: "j1", title: "Ideias do app", date: "2026-11-13", folder: "notas", private: false,
      body: "! Deixar o mini chat mais limpo\n- [ ] testar atalhos de voz\n- [x] revisar paleta clara\n#produto",
      derived: { tags: ["produto"], priorities: ["Deixar o mini chat mais limpo"], tasks: [{ text: "testar atalhos de voz", done: false }, { text: "revisar paleta clara", done: true }] },
    },
  }),
  journalSave: ([payload]) => ({ ok: true, entry: { ...JSON.parse(String(payload)), id: "j1" } }),
  harnessPanorama: () => ({
    ok: true,
    routing: {
      total: 48,
      routes: [
        { route: "conversa", runs: 17, ok: 17, avg_ms: 3400 }, { route: "atalho", runs: 11, ok: 11, avg_ms: 1300 },
        { route: "maestro", runs: 12, ok: 10, avg_ms: 14200 }, { route: "aprendido", runs: 5, ok: 5, avg_ms: 6100 },
        { route: "continuar", runs: 2, ok: 2, avg_ms: 2900 }, { route: "resposta", runs: 1, ok: 1, avg_ms: 400 },
      ],
      agents: [
        { agent: "DESKTOP", runs: 14, ok: 13 }, { agent: "WEB", runs: 8, ok: 8 }, { agent: "DATA", runs: 6, ok: 5 },
        { agent: "FILE", runs: 4, ok: 4 }, { agent: "CODE", runs: 3, ok: 2 }, { agent: "EXTCODE", runs: 1, ok: 1 },
      ],
      edges: [{ from: "conversa", to: "maestro", runs: 4 }],
      recent: [{ route: "conversa", ok: true, agents: ["CHAT"], when: "2026-11-27T09:12", ms: 3100 }],
    },
    evolution: {
      plans: [
        { key: "p1", template: "abrir ⟨app⟩ e escrever ⟨texto⟩", status: "promoted", successes: 6, failures: 0, streak: 6, replays: 3, agents: ["DESKTOP"] },
        { key: "p2", template: "pesquisar ⟨termo⟩ no youtube", status: "promoted", successes: 4, failures: 0, streak: 4, replays: 1, agents: ["WEB"] },
        { key: "p3", template: "copie ⟨arquivo⟩ dentro de ⟨caminho⟩", status: "candidate", successes: 2, failures: 0, streak: 2, replays: 0, agents: ["FILE"] },
        { key: "p4", template: "crie uma planilha de ⟨tema⟩", status: "candidate", successes: 1, failures: 1, streak: 1, replays: 0, agents: ["DATA"] },
        { key: "p5", template: "mande ⟨mensagem⟩ no teams", status: "blocked", successes: 0, failures: 2, streak: 0, replays: 0, agents: ["DESKTOP"] },
      ],
      hypotheses: [
        { id: "h1", agent: "FILE", objective: "Conferir o destino antes de mover", result: "aguardando decisão", origin: "real", when: "2026-11-26T18:20" },
        { id: "h2", agent: "WEB", objective: "Preferir fontes oficiais", result: "refutada", origin: "real", when: "2026-11-25T10:02" },
        { id: "h3", agent: "DATA", objective: "Sempre incluir gráfico", result: "promovida", origin: "real", when: "2026-11-24T15:41" },
      ],
      summary: { promoted: 2, candidate: 2, blocked: 1, hypotheses: 3 },
    },
  }),
  labVersions: () => ({
    ok: true,
    versions: [
      { id: "file-v1", n: 1, note: "Referência (configuração atual)", instructions: "", params: { effort: "low" }, published: true },
      { id: "file-v2", n: 2, note: "", instructions: "Confira o destino antes de copiar.", params: { effort: "medium" }, published: false },
    ],
    effective: {},
  }),
  labEvalSets: () => ({ ok: true, sets: [{ name: "arquivos-basico", cases: [1, 2, 3, 4] }] }),
  labRuns: () => ({ ok: true, runs: [{ id: "r1" }], busy: false }),
  labRunDetail: () => ({
    ok: true,
    run: {
      id: "r1", versions: ["file-v1", "file-v2"],
      summary: {
        "file-v1": { passed: 3, cases: 4, cost_usd: 0.012, latency_ms_avg: 2100, origin: "simulado" },
        "file-v2": { passed: 4, cases: 4, cost_usd: 0.014, latency_ms_avg: 2300, origin: "simulado" },
      },
      results: [
        { case: "copiar para pasta nova", version: "file-v1", status: "passou", trace: [] },
        { case: "copiar para pasta nova", version: "file-v2", status: "passou", trace: [] },
        { case: "não sobrescrever arquivo", version: "file-v1", status: "falhou", trace: [{ kind: "executado", action: "copy", params: { dst: "relatorio.xlsx" } }, { kind: "verificado", checks: [{ ok: false, check: "original intacto" }] }] },
        { case: "não sobrescrever arquivo", version: "file-v2", status: "passou", trace: [{ kind: "verificado", checks: [{ ok: true, check: "original intacto" }] }] },
      ],
    },
  }),
  labPromotionCheck: () => ({ ok: false, reasons: ["falta um teste real com o modelo"] }),
  harnessGet: () => ({
    ok: true, writable: true,
    versions: [{ id: "20261113-1402", label: "Aparência", when: "20261113-1402" }],
    harness: {
      agents: { MAESTRO: { instructions: "" }, WEB: { instructions: "" }, DESKTOP: { instructions: "" }, CODE: { instructions: "" }, DATA: { instructions: "Use gráfico de pizza só até 6 categorias." }, FILE: { instructions: "" }, EXTCODE: { instructions: "" } },
      response: { tone: "natural", length: "media", extra: "" },
      appearance: { accent: "#16897E", palette: "abismo", mode: "escuro", radius: "suave", motion: true },
      modules: { brain: true, you: true, harness: true, history: true },
      dev: { enabled: false, code_changes: false, greeting: "", hint: "", shortcuts: [], cards: [] },
    },
  }),
  agentProfile: ([agent]) => ({
    ok: true, agent, role: "Entende o pedido, divide em etapas e escolhe o agente de cada uma.",
    does: ["Lê o pedido e o contexto da conversa", "Monta o plano e passa pelas políticas de aceite"],
    uses: "Plano validado em código", inputs: "Seu pedido, a conversa, o Harness e a seção Você",
    limits: ["Não age no computador: só planeja e delega"], examples: ["Organize meus downloads"], tools: [], rules: [], skills: [],
  }),
  devList: () => ({ ok: true, items: [] }),
  brainOverview: () => ({
    ok: true, personal: "C:/Users/voce/Documents/AI Farm Agent", writable: true, edited: 2, removed: [],
    folders: ["10 Agentes", "20 Politicas", "60 Aprendizados"],
    notes: [
      { rel: "00 Maestro/Maestro.md", title: "Maestro", folder: "00 Maestro", layer: "base" },
      { rel: "10 Agentes/Dados.md", title: "Dados", folder: "10 Agentes", layer: "editada" },
      { rel: "10 Agentes/Web.md", title: "Web", folder: "10 Agentes", layer: "base" },
      { rel: "20 Politicas/Arquivos.md", title: "Arquivos", folder: "20 Politicas", layer: "base" },
      { rel: "60 Aprendizados/Excel abre devagar.md", title: "Excel abre devagar", folder: "60 Aprendizados", layer: "pessoal" },
      // notas nas pastas dos agentes (Memória dos agentes no Lab)
      ...AGENT_NOTES.map((rel) => ({ rel, title: rel.split("/").pop()!.replace(/\.md$/, ""), folder: rel.slice(0, rel.lastIndexOf("/")), layer: "base" })),
    ],
  }),
  brainRead: ([rel]) => ({
    ok: true,
    rel,
    layer: String(rel).includes("Dados") ? "editada" : "base",
    links: [
      { target: "Maestro", rel: "00 Maestro/Maestro.md" },
      { target: "Excel abre devagar", rel: "60 Aprendizados/Excel abre devagar.md" },
      { target: "Nota que falta", rel: null },
    ],
    backlinks: [{ rel: "00 Maestro/Maestro.md", title: "Maestro" }],
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
  brainSearch: ([q]) => ({ ok: true, items: [{ rel: "10 Agentes/Dados.md", title: "Dados", snippet: `…${q}… em planilhas com fórmulas` }, { rel: "30 Tarefas de referencia/Playbook - Planilha com grafico.md", title: "Playbook - Planilha com grafico", snippet: "Caminho verificado" }, { rel: "Notas/Financeiro.md", title: "Financeiro", snippet: "Pastas e prazos" }] }),
  brainGraph: () => ({
    ok: true,
    // mesmo formato do nucleo (core/brain_store.graph): id = caminho da nota
    nodes: [
      { id: "00 Maestro/Maestro.md", title: "Maestro", folder: "00 Maestro" },
      { id: "10 Agentes/Dados.md", title: "Dados", folder: "10 Agentes" },
      { id: "10 Agentes/Web.md", title: "Web", folder: "10 Agentes" },
      { id: "20 Politicas/Arquivos.md", title: "Arquivos", folder: "20 Politicas" },
      { id: "60 Aprendizados/Excel abre devagar.md", title: "Excel abre devagar", folder: "60 Aprendizados" },
    ],
    edges: [
      { from: "00 Maestro/Maestro.md", to: "10 Agentes/Dados.md" },
      { from: "00 Maestro/Maestro.md", to: "10 Agentes/Web.md" },
      { from: "00 Maestro/Maestro.md", to: "20 Politicas/Arquivos.md" },
      { from: "10 Agentes/Dados.md", to: "60 Aprendizados/Excel abre devagar.md" },
      { from: "10 Agentes/Data/Planilhas com grafico.md", to: "60 Aprendizados/Excel abre devagar.md" },
      { from: "10 Agentes/Desktop/Rotinas de apps.md", to: "60 Aprendizados/Excel abre devagar.md" },
      { from: "10 Agentes/File/Organizar por tipo.md", to: "20 Politicas/Arquivos.md" },
      { from: "10 Agentes/Desktop/Bloco de Notas.md", to: "20 Politicas/Arquivos.md" },
      { from: "00 Maestro/Como delegar.md", to: "20 Politicas/Arquivos.md" },
      { from: "60 Aprendizados/Excel abre devagar.md", to: "00 Maestro/Maestro.md" },
    ],
  }),
  suggestionsList: () => ({ ok: true, items: [{ id: "s1", kind: "licao", title: "Abra o Excel e preencha a primeira linha", evidence: "Falhou: a janela do Excel não respondeu a tempo.", body: "", hint: "Escreva a regra que evita essa falha (o que o agente deve fazer diferente)." }] }),
  // Biblioteca: textos reais em demo/library.fixture.json (npm run demo:library), so no dev; fora do build.
  studioAgent: async ([a]) => {
    const s = (await studioFixture())[String(a)];
    return s ? { ok: true, spec: s.spec, memory: { ...s.memory, writable: true } } : { ok: false, error: "Rode npm run demo:library para os dados do estúdio." };
  },
  studioSource: async ([a, path]) => {
    const s = (await studioFixture())[String(a)];
    const text = s?.sources[String(path)];
    return text !== undefined ? { ok: true, file: { path, text, truncated: false } } : { ok: false, error: "Arquivo fora da lista do agente." };
  },
  studioSave: async ([a, payload]) => {
    const s = (await studioFixture())[String(a)];
    const d = JSON.parse(String(payload)) as Json;
    const links = Array.isArray(d.links) ? (d.links as string[]).map((title) => ({ title, rel: `Notas/${title}.md` })) : undefined;
    return { ok: true, memory: { ...(s?.memory ?? {}), ...d, ...(links ? { links } : {}), layer: "editada", writable: true } };
  },
  libraryCatalog: async ([q, level]) => {
    const { topics, verified_on } = await libFixture();
    const words = String(q ?? "").toLowerCase().split(/\s+/).filter((w) => w.length > 1);
    const items = topics
      .filter((t) => (!level || t.level === level) && words.every((w) => `${t.title} ${t.intro} ${t.markdown}`.toLowerCase().includes(w)))
      .map(({ markdown: _m, ...rest }) => rest);
    return { ok: true, verified_on, items };
  },
  libraryTopic: async ([id]) => {
    const { topics, verified_on } = await libFixture();
    const topic = topics.find((t) => t.id === id);
    return topic ? { ok: true, verified_on, topic } : { ok: false, error: "Tema não encontrado." };
  },
  librarySearch: () => ({
    ok: true, verified_on: "2026-11-12",
    items: [
      { id: "harness", title: "Harness Engineering", level: "iniciante", order: 1, intro: "O harness é tudo o que fica em volta do modelo: ferramentas, regras, ambiente, feedback e verificações.", why: "A maior parte da qualidade de um agente vem do ambiente, não do prompt.", prereqs: [], practice: "Escreva no Harness uma regra para o agente de Dados e rode em modo Simular.", terms: ["harness", "ferramenta"], limits: "", article: [{ h: "O que é", p: ["Um modelo sozinho só gera texto. O harness dá mãos e olhos a ele."] }], readings: [{ title: "Building effective AI agents", authors: "Anthropic", year: 2024, url: "https://www.anthropic.com/research/building-effective-agents", kind: "didatico", venue: "", note: "Comece aqui." }] },
      { id: "evals", title: "Avaliação de agentes", level: "intermediario", order: 2, intro: "Como saber se o agente melhorou: tarefas, critérios e notas reproduzíveis.", why: "Sem avaliação, toda mudança é palpite.", prereqs: ["harness"], practice: "Rode um experimento no AI Research Lab.", terms: ["eval", "grader"], limits: "", readings: [] },
    ],
  }),
};

/** Socket falso: autentica, responde metodos e simula uma tarefa em executeTask. */
// Notas das pastas dos agentes no Cérebro de demonstração
const AGENT_NOTES = [
  "00 Maestro/Como delegar.md", "00 Maestro/Rotas que funcionaram.md",
  "10 Agentes/Web/Navegar com o piloto.md", "10 Agentes/Web/Sites permitidos.md", "10 Agentes/Web/Pesquisa no Google.md",
  "10 Agentes/Desktop/Rotinas de apps.md", "10 Agentes/Desktop/Bloco de Notas.md",
  "10 Agentes/Code/Projetos estaticos.md", "10 Agentes/Code/Validar antes de abrir.md",
  "10 Agentes/Data/Planilhas com grafico.md", "10 Agentes/File/Organizar por tipo.md",
  "10 Agentes/ExtCode/Pasta escolhida.md",
];

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
      if ("id" in msg) void Promise.resolve(fn ? fn(args) : null).then((result) => reply({ jsonrpc: "2.0", id: msg.id, result }));
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

let demoRun = 0;
function simulate(task: string, emit: (name: string, payload: unknown) => void) {
  const steps = [
    "[DATA] Montar a planilha com as categorias do mês",
    "[DATA] Inserir fórmulas de total e um gráfico de pizza",
    "[FILE] Salvar em Documentos como Gastos-novembro.xlsx",
  ];
  const at = (ms: number, fn: () => void) => setTimeout(fn, ms);
  at(100, () => emit("phaseChanged", { msg: "Entendendo o pedido", run_id: ++demoRun }));
  at(700, () => emit("planReady", { plan: { route: "conversa→maestro", steps: steps.map((d) => ({ description: d })) } }));
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
