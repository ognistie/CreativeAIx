// Telemetria observada, sem inferir que planejar ou executar equivale a verificar.
export const COGNITIVE_STAGES = {
  stimulus: { label: "Estímulo", node: "stage:pedido", source: "desktop/controller.py" },
  understanding: { label: "Entendimento", node: "stage:entendimento", source: "core/followup.py" },
  memory: { label: "Recuperação de memória", node: "region:memory", source: "core/brain.py · agents/maestro.py" },
  context: { label: "Construção de contexto", node: "region:context", source: "core/brain.py · core/context_engine.py" },
  planning: { label: "Planejamento", node: "MAESTRO", source: "agents/maestro.py" },
  decision: { label: "Decisão e permissões", node: "stage:politicas", source: "desktop/controller_gates.py" },
  transmission: { label: "Transmissão", node: "region:spine", source: "core/task_schedule.py" },
  execution: { label: "Execução", node: "region:spine", source: "core/automation.py" },
  verification: { label: "Verificação", node: "region:verify", source: "core/verification.py" },
  learning: { label: "Aprendizado validado", node: "region:learning", source: "core/learned_plans.py" },
  recovery: { label: "Recuperação", node: "MAESTRO", source: "core/run_context.py" },
  model: { label: "Chamada de modelo", node: "region:model", source: "core/ai_client.py" },
} as const;
export type CognitiveStage = keyof typeof COGNITIVE_STAGES;
export const COGNITIVE_STATES = ["started", "observed", "completed", "verified", "failed", "blocked", "uncertain", "cancelled"] as const;
export const STATUS_LABEL: Record<typeof COGNITIVE_STATES[number], string> = {
  started: "iniciado", observed: "observado", completed: "concluído", verified: "verificado",
  failed: "falhou", blocked: "bloqueado", uncertain: "incerto", cancelled: "cancelado",
};
export interface CognitiveEvent {
  seq: number; ms: number; stage: CognitiveStage; agent: string;
  status: typeof COGNITIVE_STATES[number]; count: number; refs: string[]; action: string;
}
export interface CognitiveRun { id: string; when: string; ok: boolean; route: string; events: CognitiveEvent[]; dropped: number }
export function cognitiveEvent(value: unknown): CognitiveEvent | null {
  if (!value || typeof value !== "object") return null;
  const p = value as Record<string, unknown>;
  if (typeof p.stage !== "string" || !Object.hasOwn(COGNITIVE_STAGES, p.stage)
    || !COGNITIVE_STATES.includes(p.status as CognitiveEvent["status"])
    || !Number.isSafeInteger(p.seq) || Number(p.seq) < 0 || !Number.isFinite(p.ms) || Number(p.ms) < 0) return null;
  return { seq: Number(p.seq), ms: Number(p.ms), stage: p.stage as CognitiveStage, status: p.status as CognitiveEvent["status"],
    agent: typeof p.agent === "string" ? p.agent.slice(0, 32) : "", count: Math.max(0, Number(p.count) || 0),
    refs: Array.isArray(p.refs) ? p.refs.filter((r): r is string => typeof r === "string").slice(0, 16) : [],
    action: typeof p.action === "string" ? p.action.slice(0, 64) : "" };
}
export function eventsAt(events: CognitiveEvent[], ms: number): CognitiveEvent[] {
  return events.filter((e) => e.ms <= ms);
}
export function eventNode(e: CognitiveEvent): string {
  return e.stage === "execution" && e.agent ? e.agent : COGNITIVE_STAGES[e.stage].node;
}
export function eventSource(e: CognitiveEvent): string {
  if (e.stage === "execution" && e.agent === "EXTCODE") return "core/coding_agents.py";
  if (e.stage === "memory" && e.action === "conversation_turns") return "core/context_engine.py";
  return COGNITIVE_STAGES[e.stage].source;
}
export function animationTime(now: number, calm: boolean): number { return calm ? 0 : now; }
export function signalProgress(now: number, started: number, offset = 0): number {
  return Math.max(0, Math.min(1, (now - started) / 1200 + offset));
}
export function detailLevel(width: number, compact: boolean): number { return compact || width < 800 ? 1 : 2; }
