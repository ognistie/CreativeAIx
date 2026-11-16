// Nome amigavel do agente (Theme.agentLabel no app anterior): o nucleo usa CODE, DATA, ...
const LABELS: Record<string, string> = {
  MAESTRO: "Maestro",
  CODE: "Código",
  DATA: "Dados",
  WEB: "Web",
  DESKTOP: "Desktop",
  FILE: "Arquivos",
  EXTCODE: "Claude / Codex",
  MEMORY: "Memória",
  SYSTEM: "Sistema",
};

export function agentLabel(name: string): string {
  return LABELS[(name || "").toUpperCase()] ?? name ?? "";
}

import type { IconName } from "../components/ui";

/** Icone de cada agente: o mesmo no Lab, na Atividade e no Historico (identidade por nome + icone). */
const ICONS: Record<string, IconName> = {
  MAESTRO: "route",
  WEB: "globe",
  DESKTOP: "monitor",
  CODE: "code",
  DATA: "chart",
  FILE: "folder",
  EXTCODE: "terminal",
  MEMORY: "brain",
};

export function agentIcon(name: string): IconName {
  return ICONS[(name || "").toUpperCase()] ?? "sparkle";
}
