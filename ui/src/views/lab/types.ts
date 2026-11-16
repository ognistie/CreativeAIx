import type { IconName } from "../../components/ui";

// Tipos do estudio de agentes (core/agent_studio.py via studioAgent/studioSource/studioSave).

export interface Policy {
  id: string;
  title: string;
  rule: string;
  enforcement: string;
  note: string;
}

export interface Spec {
  agent: string;
  role: string;
  does: string[];
  uses: string;
  inputs: string;
  limits: string[];
  examples: string[];
  config: { model: string; effort: string; thinking: string; max_tokens: number; provider: string; notes?: string[] };
  authorization: string;
  tools: Array<{ name: string; params: string[]; permission: string }>;
  skills: Array<{ name: string; purpose: string; triggers: string[] }>;
  policies: Policy[];
  files: Array<{ path: string; lines: number; shared: boolean; doc: string }>;
}

export interface Memory {
  note: string;
  layer: string;
  writable: boolean;
  rules: string;
  how: string;
  failures: string;
  extra: string;
  links: Array<{ title: string; rel: string }>;
}

export type Reply = { ok?: boolean; error?: string } & Record<string, unknown>;

export const call = (p: Promise<unknown>): Promise<Reply> =>
  p.then((r) => r as Reply).catch((e: Error) => ({ ok: false, error: e.message }) as Reply);

export const AGENTS = ["MAESTRO", "WEB", "DESKTOP", "CODE", "DATA", "FILE", "EXTCODE"] as const;

export const AGENT_LOOK: Record<string, { icon: IconName; color: string; name: string }> = {
  MAESTRO: { icon: "route", color: "#8b5cf6", name: "Maestro" },
  WEB: { icon: "globe", color: "#3b82f6", name: "Web" },
  DESKTOP: { icon: "monitor", color: "#14b8a6", name: "Desktop" },
  CODE: { icon: "code", color: "#f59e0b", name: "Código" },
  DATA: { icon: "chart", color: "#22c55e", name: "Dados" },
  FILE: { icon: "folder", color: "#f97316", name: "Arquivos" },
  EXTCODE: { icon: "terminal", color: "#94a3b8", name: "Claude / Codex" },
};

export const EFFORT_LABEL: Record<string, string> = { low: "Baixo", medium: "Médio", high: "Alto", max: "Máximo" };
export const AUTH_LABEL: Record<string, string> = {
  enforce: "Pede aprovação para efeitos sensíveis",
  shadow: "Só registra efeitos sensíveis",
  off: "Aprovação desligada",
};
