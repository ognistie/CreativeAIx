// Comandos com barra no composer: "/claude ..." chama o Claude Code, "/codex ..." chama o Codex.
// Substitui o seletor "Quem atende o pedido" do cabecalho: a ferramenta vale para o pedido em que foi
// digitada, nunca fica ligada escondida para os proximos.

import type { IconName } from "../components/ui";

export type SlashTool = "claude" | "codex";

export interface SlashCommand {
  tool: SlashTool;
  command: string;
  name: string;
  hint: string;
  icon: IconName;
}

export const SLASH_COMMANDS: readonly SlashCommand[] = [
  { tool: "claude", command: "/claude", name: "Claude Code", hint: "O Claude Code trabalha na pasta do projeto", icon: "bolt" },
  { tool: "codex", command: "/codex", name: "Codex", hint: "O Codex trabalha na pasta do projeto", icon: "terminal" },
];

export const toolName = (tool: SlashTool) => SLASH_COMMANDS.find((c) => c.tool === tool)!.name;

/** "/cod" -> comandos que comecam assim (menu aberto). Fora de uma palavra com barra no inicio: []. */
export function slashMatches(text: string): SlashCommand[] {
  const m = /^\/(\w*)$/.exec(text);
  if (!m) return [];
  const q = (m[1] ?? "").toLowerCase();
  return SLASH_COMMANDS.filter((c) => c.command.slice(1).startsWith(q));
}

/** "/codex crie um site" -> { tool: "codex", rest: "crie um site" }. Sem comando no inicio: null. */
export function parseSlash(text: string): { tool: SlashTool; rest: string } | null {
  const m = /^\/(claude|codex)(?:\s+|$)([\s\S]*)$/i.exec(text);
  return m ? { tool: (m[1] ?? "").toLowerCase() as SlashTool, rest: m[2] ?? "" } : null;
}

/** O pedido que vai ao nucleo: o Maestro reconhece "com o Codex" / "com o Claude Code" e a pasta citada
 *  (agents/extcode_agent.py). Sem pasta, ele usa o projeto da conversa ou pergunta. */
export function withTool(text: string, tool: SlashTool | null, folder?: string): string {
  const t = text.trim();
  if (!tool) return t;
  const name = tool === "claude" ? "com o Claude Code" : "com o Codex";
  return [t, name, folder ? `na pasta ${folder}` : ""].filter(Boolean).join(" ");
}
