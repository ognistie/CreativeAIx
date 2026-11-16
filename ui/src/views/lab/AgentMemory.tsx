import { useEffect, useState } from "react";
import { AppDialog, Button, GlassPanel, Icon, Spinner, type IconName } from "../../components/ui";
import { cn } from "../../lib/cn";
import { core } from "../../lib/host";
import { call, type Memory } from "./types";

// Memoria do agente = a nota dele no Cerebro (10 Agentes/...). Estas tres secoes entram no prompt do agente
// (core/brain.py > agent_notes). Salvar grava na sua camada pessoal; o original de fabrica fica guardado.

const FIELDS: Array<{ key: "rules" | "how" | "failures"; title: string; icon: IconName; hint: string; placeholder: string }> = [
  {
    key: "rules",
    title: "Regras de execução",
    icon: "checklist",
    hint: "O que ele sempre faz ou nunca faz.",
    placeholder: "- Nunca sobrescrever arquivo existente sem perguntar.",
  },
  {
    key: "how",
    title: "Como executar",
    icon: "route",
    hint: "O caminho que funciona, passo a passo.",
    placeholder: "- Listar a pasta, propor o plano, mover e listar de novo para conferir.",
  },
  {
    key: "failures",
    title: "Falhas conhecidas",
    icon: "alert-triangle",
    hint: "Erros que já aconteceram e como evitar.",
    placeholder: "- O Excel demora para abrir: esperar a janela antes de digitar.",
  },
];
const MAX = 2000;

export function AgentMemory({ agent, memory, onSaved, onDirty }: { agent: string; memory: Memory; onSaved: (m: Memory) => void; onDirty: (d: boolean) => void }) {
  const [draft, setDraft] = useState({ rules: memory.rules, how: memory.how, failures: memory.failures });
  const [state, setState] = useState<"" | "saving" | "saved">("");
  const [error, setError] = useState("");
  const [ask, setAsk] = useState(false);

  useEffect(() => setDraft({ rules: memory.rules, how: memory.how, failures: memory.failures }), [memory]);
  const dirty = draft.rules !== memory.rules || draft.how !== memory.how || draft.failures !== memory.failures;
  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);

  const save = async () => {
    setState("saving");
    setError("");
    const r = await call(core().call("studioSave", agent, JSON.stringify(draft)));
    if (!r.ok) return (setState(""), setError(r.error || "Não salvou."));
    onSaved(r.memory as Memory);
    setState("saved");
    setTimeout(() => setState(""), 2200);
  };

  const restore = async () => {
    setAsk(false);
    const r = await call(core().call("brainRestore", memory.note));
    if (!r.ok) return setError(r.error || "Não deu para restaurar.");
    const s = await call(core().call("studioAgent", agent));
    if (s.ok) onSaved(s.memory as Memory);
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <span
          className={cn(
            "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
            memory.layer === "editada" ? "bg-accent/15 text-accent-ink" : "bg-chip text-fg-muted",
          )}
        >
          <Icon name={memory.layer === "editada" ? "pen" : "box"} size={12} />
          {memory.layer === "editada" ? "Editada por você" : "Original de fábrica"}
        </span>
        <span className="truncate font-mono text-xs text-fg-muted">{memory.note}</span>
        <span className="flex-1" />
        {memory.layer === "editada" && (
          <Button size="compact" variant="ghost" icon="undo" onClick={() => setAsk(true)}>
            Restaurar original
          </Button>
        )}
      </div>
      {!memory.writable && <p className="mb-4 rounded-r2 bg-warn/10 p-3 text-sm text-fg">Sem a pasta pessoal do Cérebro: dá para ler, mas não salvar.</p>}

      <div className="grid gap-4 xl:grid-cols-3 [&>*]:min-w-0">
        {FIELDS.map((f) => (
          <GlassPanel key={f.key} className="flex flex-col p-4">
            <label htmlFor={`mem-${f.key}`} className="flex items-center gap-2 text-md font-semibold text-fg">
              <Icon name={f.icon} size={15} className="text-fg-muted" /> {f.title}
            </label>
            <p className="mt-0.5 text-sm text-fg-muted">{f.hint}</p>
            <textarea
              id={`mem-${f.key}`}
              value={draft[f.key]}
              maxLength={MAX}
              disabled={!memory.writable}
              onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
              rows={11}
              placeholder={f.placeholder}
              className="mt-3 w-full flex-1 select-text resize-y rounded-r2 border border-hairline bg-surface p-3 font-mono text-[12.5px] leading-relaxed text-fg outline-none placeholder:text-fg-subtle focus:border-accent/45"
            />
            <p className="mt-1.5 text-right text-xs tabular-nums text-fg-muted">
              {draft[f.key].length}/{MAX}
            </p>
          </GlassPanel>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <p className="flex-1 text-sm text-fg-muted" aria-live="polite">
          {error ? <span className="text-bad-ink">{error}</span> : state === "saved" ? "Memória salva. Vale a partir do próximo pedido." : dirty ? "Alterações não salvas" : "Use uma linha por item, começando com “- ”."}
        </p>
        <Button variant="ghost" disabled={!dirty} onClick={() => setDraft({ rules: memory.rules, how: memory.how, failures: memory.failures })}>
          Descartar
        </Button>
        <Button variant="primary" icon="save" disabled={!dirty || !memory.writable || state === "saving"} onClick={() => void save()}>
          {state === "saving" ? <Spinner size={12} /> : null} Salvar memória
        </Button>
      </div>

      <AppDialog
        open={ask}
        onOpenChange={setAsk}
        title="Voltar a memória original?"
        description="A nota inteira volta a ser a de fábrica, inclusive as notas ligadas e o contexto extra. A sua versão vai para a lixeira do Cérebro."
        actions={
          <>
            <Button variant="ghost" onClick={() => setAsk(false)}>
              Cancelar
            </Button>
            <Button variant="primary" icon="undo" onClick={() => void restore()}>
              Restaurar
            </Button>
          </>
        }
      />
    </div>
  );
}
