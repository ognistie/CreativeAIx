import { useState } from "react";
import { AppDialog, Button } from "../../components/ui";
import { AgentMemoryEditor } from "./AgentMemoryEditor";
import { AGENTS, AGENT_LOOK } from "./types";

// Memoria dos agentes a partir da conversa: corrigir na hora o que um agente "lembra errado", sem sair do chat.
// Mesmo editor da area Memoria do Lab (camada pessoal do Cerebro); vale a partir do proximo pedido.

export default function AgentMemoryDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [agent, setAgent] = useState<string>("MAESTRO");
  const [dirty, setDirty] = useState(false);
  const close = (o: boolean) => {
    if (!o && dirty && !window.confirm("Descartar a alteração não salva na memória do agente?")) return;
    if (!o) setDirty(false);
    onOpenChange(o);
  };
  return (
    <AppDialog open={open} onOpenChange={close} title="Memória dos agentes"
      description="O que cada agente lembra entre as conversas. Vale a partir do próximo pedido."
      actions={<Button onClick={() => close(false)}>Fechar</Button>}>
      <div className="grid max-h-[62vh] gap-4 overflow-y-auto pr-1">
        <label className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">Agente
          <select className="rounded-r2 border border-hairline bg-surface px-3 py-1.5 text-sm text-fg" value={agent} disabled={dirty}
            onChange={(e) => setAgent(e.target.value)}>
            {AGENTS.map((id) => <option key={id} value={id}>{AGENT_LOOK[id]!.name}</option>)}
          </select>
        </label>
        <AgentMemoryEditor key={agent} agent={agent} onDirty={setDirty} />
      </div>
    </AppDialog>
  );
}
