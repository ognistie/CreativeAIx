// Estado da tela de tarefa: o mesmo que a TaskView.qml mantem, como reducer puro (testavel).
// Os eventos do nucleo (Signals do Bridge) e as acoes da tela entram aqui; a tela so desenha.

export type TaskStatus = "idle" | "running" | "done" | "failed" | "cancelled" | "clarify" | "limited";

export interface Turn {
  said: string;
  resolved: string;
  status: TaskStatus;
  summary: string;
}

export interface Step {
  kind: "step" | "note";
  n: number;
  agent: string;
  desc: string;
  state: "running" | "ok" | "fail" | "warn";
  result: string;
}

export interface Usage {
  calls: number;
  tokens_est: number;
  cost_usd: number;
}

export interface Artifacts {
  folder: string;
  files: string[];
  url: string;
}

export interface Review {
  token: string;
  effect: boolean;
  summary: string;
  steps: string[];
}

export interface TaskState {
  status: TaskStatus;
  busy: boolean;
  task: string;
  phaseMsg: string;
  errorMsg: string;
  question: string;
  resolvedText: string;
  heardText: string;
  assistantText: string;
  reportSummary: string;
  progress: number;
  startedAt: number;
  finishedMs: number | null;
  dryRun: boolean;
  usageNow: Usage;
  usageBase: Usage;
  finalMetrics: { api_calls: number; tokens_est: number; cost_usd: number } | null;
  artifacts: Artifacts;
  plan: Array<{ agent: string; text: string }>;
  steps: Step[];
  replies: string[];
  turns: Turn[];
  review: Review | null;
}

const ZERO: Usage = { calls: 0, tokens_est: 0, cost_usd: 0 };

export const initialTaskState: TaskState = {
  status: "idle",
  busy: false,
  task: "",
  phaseMsg: "",
  errorMsg: "",
  question: "",
  resolvedText: "",
  heardText: "",
  assistantText: "",
  reportSummary: "",
  progress: 0,
  startedAt: 0,
  finishedMs: null,
  dryRun: false,
  usageNow: ZERO,
  usageBase: ZERO,
  finalMetrics: null,
  artifacts: { folder: "", files: [], url: "" },
  plan: [],
  steps: [],
  replies: [],
  turns: [],
  review: null,
};

export type TaskAction =
  | { type: "start"; text: string; heard?: string; dryRun: boolean; now: number }
  | { type: "newConversation" }
  | { type: "showConversation"; turns: Array<Record<string, unknown>> }
  | { type: "reviewDecided" }
  | { type: "event"; name: string; payload: unknown; now: number };

type P = Record<string, unknown>;
const str = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));
const norm = (s: string) => s.trim().toLowerCase().replace(/[.!?,]/g, "");

export function parseAgent(desc: string): { agent: string; text: string } {
  const m = /^\[(\w+)\]\s*/.exec(desc || "");
  return m ? { agent: m[1]!, text: desc.slice(m[0].length) } : { agent: "", text: desc || "" };
}

/** O pedido que terminou vai para a conversa, em forma compacta. */
function archive(s: TaskState): Turn[] {
  if (s.status === "idle" || !s.task) return s.turns;
  const lastReply = s.replies.at(-1) ?? "";
  const summary = (s.assistantText || s.reportSummary || s.errorMsg || s.question || lastReply).slice(0, 400);
  return [...s.turns, { said: s.task, resolved: s.resolvedText, status: s.status, summary }];
}

function cleared(s: TaskState, turns: Turn[]): TaskState {
  return {
    ...initialTaskState,
    usageNow: s.usageNow,
    usageBase: s.usageNow,
    turns,
  };
}

export function taskReducer(s: TaskState, a: TaskAction): TaskState {
  switch (a.type) {
    case "start": {
      const heard = a.heard && norm(a.heard) !== norm(a.text) ? a.heard : "";
      return {
        ...cleared(s, archive(s)),
        status: "running",
        busy: true,
        task: a.text,
        heardText: heard,
        phaseMsg: "Entendendo o pedido",
        startedAt: a.now,
        dryRun: a.dryRun,
      };
    }
    case "newConversation":
      return s.busy ? s : cleared(s, []);
    case "showConversation": {
      if (s.busy) return s;
      const turns: Turn[] = a.turns.map((t) => ({
        said: str(t.said),
        resolved: str(t.resolved),
        status: t.kind === "chat" ? "done" : t.success === false ? "failed" : "done",
        summary: str(t.reply || t.summary).slice(0, 400),
      }));
      return cleared(s, turns);
    }
    case "reviewDecided":
      return { ...s, review: null };
    case "event":
      return onEvent(s, a.name, (a.payload ?? {}) as P, a.now);
  }
}

function onEvent(s: TaskState, name: string, p: P, now: number): TaskState {
  switch (name) {
    case "phaseChanged":
      return { ...s, busy: true, phaseMsg: str(p.msg) || s.phaseMsg };
    case "planReady": {
      const steps = (((p.plan as P | undefined)?.steps as P[] | undefined) ?? []).map((st) => {
        const a = parseAgent(str(st.description));
        return { agent: a.agent || str(st.action), text: a.text };
      });
      return { ...s, plan: steps, phaseMsg: "Executando" };
    }
    case "stepStart": {
      const a = parseAgent(str(p.desc));
      const n = Number(p.step);
      const step: Step = { kind: "step", n, agent: a.agent, desc: a.text, state: "running", result: "" };
      return {
        ...s,
        steps: [...s.steps, step],
        progress: Number(p.progress) || s.progress,
        phaseMsg: `Passo ${n}${p.total ? ` de ${p.total}` : ""}`,
      };
    }
    case "stepDone": {
      const n = Number(p.step);
      const result = str(p.result).trim().slice(0, 600);
      const state = p.ok ? "ok" : "fail";
      const i = s.steps.findIndex((x) => x.kind === "step" && x.n === n);
      let steps: Step[];
      if (i >= 0) {
        steps = s.steps.map((x, j) => (j === i ? { ...x, state, result } : x));
      } else {
        const a = parseAgent(str(p.desc));
        steps = [...s.steps, { kind: "step", n, agent: a.agent, desc: a.text, state, result }];
      }
      return { ...s, steps, progress: Number(p.progress) || s.progress };
    }
    case "logEntry": {
      // So o que o usuario precisa saber: avisos e erros que nao viraram passo.
      const level = str(p.level).toUpperCase();
      const msg = str(p.msg);
      if (!s.busy || (level !== "ERROR" && level !== "WARN") || msg.startsWith("Step falhou")) return s;
      const note: Step = { kind: "note", n: -1, agent: str(p.agent), desc: msg, state: level === "ERROR" ? "fail" : "warn", result: "" };
      return { ...s, steps: [...s.steps, note] };
    }
    case "apiUsage":
      return { ...s, usageNow: { ...ZERO, ...(p as Partial<Usage>) } };
    case "contextExtracted":
      return { ...s, artifacts: mergeArtifacts(s.artifacts, p) };
    case "taskDone":
      return { ...s, progress: 100, phaseMsg: "Finalizando" };
    case "executionFinished":
      return { ...s, busy: false, review: null, finishedMs: s.finishedMs ?? (s.startedAt ? now - s.startedAt : null) };
    case "reportReady":
      return { ...s, reportSummary: str((p.report as P | undefined)?.summary) };
    case "planReview": {
      const plan = (p.plan as P | undefined) ?? {};
      const token = str(p.token);
      const effect = !!p.effect;
      const closingEffect = !!s.review?.effect && !token;
      let steps = ((plan.steps as unknown[]) ?? []).map(str);
      if (effect && p.spoken_code) steps = [...steps, `Por voz, diga: confirmo ${str(p.spoken_code)}`];
      const phaseMsg = token ? "Aguardando sua aprovação" : closingEffect && s.busy ? "Executando" : s.phaseMsg;
      return { ...s, review: token ? { token, effect, summary: str(plan.summary), steps } : null, phaseMsg };
    }
    case "cancelled":
      return { ...s, review: null, status: s.status === "running" ? "cancelled" : s.status };
    case "errorRaised": {
      const kind = str(p.kind);
      if (kind === "clarification") return { ...s, question: str(p.msg) || "Pode dar mais detalhes?", status: "clarify" };
      if (kind === "limitation") return { ...s, question: str(p.msg) || "Não posso fazer isso como pedido.", status: "limited" };
      return { ...s, errorMsg: str(p.msg) || "Erro desconhecido", status: "failed" };
    }
    case "resolved":
      return p.said === s.task && p.task !== p.said ? { ...s, resolvedText: str(p.task) } : s;
    case "voiceReply": {
      const t = str(p.text);
      return t && s.status !== "idle" ? { ...s, replies: [...s.replies, t] } : s;
    }
    case "assistantMessage":
      return p.said === s.task ? { ...s, assistantText: str(p.text) } : s;
    case "voiceChat": {
      // Papo por voz ("valeu", "oi"): mensagem propria, sem grudar no pedido anterior
      const heard = str(p.heard);
      const reply = str(p.reply);
      if (s.busy) return { ...s, replies: [...s.replies, reply] };
      return { ...cleared(s, archive(s)), turns: [...archive(s), { said: heard, resolved: "", status: "done", summary: reply }] };
    }
    case "answerReady":
      return { ...s, reportSummary: str(p.msg) };
    case "historyChanged": {
      const entry = (p.entry as P | undefined) ?? {};
      if (entry.task !== s.task) return s;
      let status = s.status;
      if (status === "running") status = entry.success ? "done" : "failed";
      const errorMsg = status === "failed" && !s.errorMsg ? str(entry.error) || "Um ou mais passos não funcionaram." : s.errorMsg;
      return {
        ...s,
        status,
        errorMsg,
        finalMetrics: (entry.metrics as TaskState["finalMetrics"]) ?? null,
        finishedMs: Number(entry.duration_ms) || s.finishedMs,
        artifacts: mergeArtifacts(s.artifacts, (entry.artifacts as P | undefined) ?? {}),
      };
    }
    case "sessionReset":
      return s;
    default:
      return s;
  }
}

function mergeArtifacts(cur: Artifacts, p: P): Artifacts {
  const files = Array.isArray(p.files) && p.files.length ? (p.files as unknown[]).map(str) : cur.files;
  return { folder: str(p.folder) || cur.folder, files, url: str(p.url) || cur.url };
}

/** Eventos que a tela de tarefa consome. */
export const TASK_EVENTS = [
  "phaseChanged", "planReady", "stepStart", "stepDone", "logEntry", "apiUsage", "contextExtracted", "taskDone",
  "executionFinished", "reportReady", "planReview", "cancelled", "errorRaised", "resolved", "voiceReply",
  "assistantMessage", "voiceChat", "answerReady", "historyChanged",
] as const;

// ── Formatacao (mesma da TaskView.qml) ─────────────────────────────
export function fmtDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}min ${s % 60}s`;
}

export function fmtTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1).replace(".", ",")}k` : `${n}`;
}

export function fmtCost(v: number): string {
  return `US$ ${(v || 0).toFixed(4).replace(".", ",")}`;
}

export function usageLine(s: TaskState, elapsedMs: number): string {
  const m = s.finalMetrics;
  const calls = m ? m.api_calls : s.usageNow.calls - s.usageBase.calls;
  const tokens = m ? m.tokens_est : s.usageNow.tokens_est - s.usageBase.tokens_est;
  const cost = m ? m.cost_usd : s.usageNow.cost_usd - s.usageBase.cost_usd;
  const parts = [fmtDuration(elapsedMs)];
  if (calls > 0) parts.push(`${calls} ${calls === 1 ? "chamada" : "chamadas"}`, `${fmtTokens(tokens)} tokens`, fmtCost(cost));
  return parts.join("  ·  ");
}

/** Etapa do indicador: 0 entender, 1 planejar (revisao), 2 executar, 3 concluir, 4 concluido. */
export function phaseIndex(s: TaskState): number {
  if (s.status === "done") return 4;
  if (s.review && !s.review.effect) return 1;
  if (s.busy && s.progress >= 100) return 3;
  return s.steps.length > 0 || s.plan.length > 0 ? 2 : 0;
}
