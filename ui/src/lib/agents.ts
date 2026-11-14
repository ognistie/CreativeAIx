// Nome amigavel do agente (Theme.agentLabel no QML): o nucleo usa CODE, DATA, ...
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
