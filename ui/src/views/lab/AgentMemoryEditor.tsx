import { useEffect, useState } from "react";
import { Button, EmptyState, Segmented, Skeleton } from "../../components/ui";
import { core } from "../../lib/host";
import { AgentContext } from "./AgentContext";
import { AgentMemory } from "./AgentMemory";
import { AGENT_LOOK, call, type Memory } from "./types";

// Editor da memoria e do contexto de UM agente (camada pessoal do Cerebro, via studioSave). Usado na area
// Memoria do Lab e no dialogo da conversa. So memoria e contexto: instrucoes, codigo e testes ficam em outras areas.

export function AgentMemoryEditor({ agent, onDirty }: { agent: string; onDirty: (dirty: boolean) => void }) {
  const [memory, setMemory] = useState<Memory | null>(null);
  const [error, setError] = useState("");
  const [part, setPart] = useState<"memoria" | "contexto">("memoria");
  const [attempt, setAttempt] = useState(0);
  const [dirty, setDirty] = useState(false);
  const mark = (d: boolean) => { setDirty(d); onDirty(d); };

  useEffect(() => {
    let active = true;
    setMemory(null);
    setError("");
    void call(core().call("studioAgent", agent)).then((r) => {
      if (!active) return;
      if (!r.ok) return setError(r.error || "Não deu para abrir a memória do agente.");
      setMemory(r.memory as Memory);
    });
    return () => { active = false; };
  }, [agent, attempt]);

  if (error) return <EmptyState icon="alert-circle" title="Memória indisponível" action={<Button onClick={() => setAttempt((v) => v + 1)}>Tentar de novo</Button>}>{error}</EmptyState>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-fg-muted">
          <strong className="text-fg">{AGENT_LOOK[agent]?.name ?? agent}</strong> · {part === "memoria"
            ? "regras, como executar e falhas que ele já conhece"
            : "notas do Cérebro e texto extra que entram no prompt dele"}
        </p>
        {/* Com alteracao nao salva, a troca de parte espera: salvar ou desfazer primeiro (nada se perde calado) */}
        <Segmented label="Parte da memória" value={part} onValueChange={(v) => !dirty && setPart(v)}
          options={[{ value: "memoria", label: "Memória" }, { value: "contexto", label: "Contexto" }]} />
      </div>
      {!memory ? <Skeleton className="h-64 rounded-r4" />
        : part === "memoria" ? <AgentMemory key={agent} agent={agent} memory={memory} onSaved={setMemory} onDirty={mark} />
        : <AgentContext key={agent} agent={agent} memory={memory} onSaved={setMemory} onDirty={mark} />}
      {dirty && <p className="text-xs text-fg-muted">Salve ou desfaça a alteração para trocar de parte ou de agente.</p>}
    </div>
  );
}
