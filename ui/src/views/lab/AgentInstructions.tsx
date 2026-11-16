import { useEffect, useState } from "react";
import { Button, GlassPanel, Icon, Skeleton, Spinner } from "../../components/ui";
import { core } from "../../lib/host";
import { AGENT_LOOK, call } from "./types";

// Instrucoes do agente no Harness (core/harness.py): estilo e prioridade, nunca permissao. Entram no prompt
// deste agente a cada pedido. Salvar guarda a versao anterior nas versoes do Harness.

const MAX = 1500;

export function AgentInstructions({ agent, examples, onDirty }: { agent: string; examples: string[]; onDirty: (d: boolean) => void }) {
  const [harness, setHarness] = useState<Record<string, unknown> | null>(null);
  const [text, setText] = useState("");
  const [saved, setSaved] = useState("");
  const [state, setState] = useState<"" | "saving" | "saved" | "error">("");
  const [error, setError] = useState("");

  useEffect(() => {
    void call(core().call("harnessGet")).then((r) => {
      if (!r.ok) return setError(r.error || "Harness indisponível.");
      const h = r.harness as { agents: Record<string, { instructions: string }> };
      setHarness(h as unknown as Record<string, unknown>);
      const t = h.agents?.[agent]?.instructions ?? "";
      setText(t);
      setSaved(t);
    });
  }, [agent]);

  const dirty = text !== saved;
  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);

  const save = async () => {
    if (!harness) return;
    setState("saving");
    const next = JSON.parse(JSON.stringify(harness)) as { agents: Record<string, { instructions: string }> };
    next.agents[agent] = { ...(next.agents[agent] ?? {}), instructions: text.trim() };
    const r = await call(core().call("harnessSave", JSON.stringify(next), `Instruções: ${AGENT_LOOK[agent]?.name ?? agent}`));
    if (!r.ok) return (setState("error"), setError(r.error || "Não salvou."));
    setHarness(r.harness as Record<string, unknown>);
    setSaved(text.trim());
    setText(text.trim());
    setState("saved");
    setTimeout(() => setState(""), 2200);
  };

  if (!harness) return error ? <p className="rounded-r2 bg-bad/10 p-3 text-sm text-bad-ink">{error}</p> : <Skeleton className="h-64 rounded-r4" />;

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px] [&>*]:min-w-0">
      <GlassPanel className="p-5">
        <label htmlFor="agent-instr" className="text-md font-semibold text-fg">
          Suas instruções para {AGENT_LOOK[agent]?.name}
        </label>
        <p className="mt-1 text-sm text-fg-muted">Escreva como você prefere que ele trabalhe. Frases curtas, uma por linha, funcionam melhor.</p>
        <textarea
          id="agent-instr"
          value={text}
          maxLength={MAX}
          onChange={(e) => setText(e.target.value)}
          rows={12}
          placeholder={"Ex.:\n- Confira o destino antes de mover arquivos.\n- Prefira nomes de arquivo com data no começo."}
          className="mt-4 w-full select-text resize-y rounded-r3 border border-hairline bg-surface p-3.5 text-md leading-relaxed text-fg outline-none placeholder:text-fg-subtle focus:border-accent/45"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className="text-xs tabular-nums text-fg-muted" aria-live="polite">
            {text.length}/{MAX}
          </span>
          <span className="flex-1 text-xs text-fg-muted" aria-live="polite">
            {state === "saved" ? "Salvo. Vale a partir do próximo pedido." : state === "error" ? error : dirty ? "Alterações não salvas" : ""}
          </span>
          <Button variant="ghost" disabled={!dirty} onClick={() => setText(saved)}>
            Descartar
          </Button>
          <Button variant="primary" icon="save" disabled={!dirty || state === "saving"} onClick={() => void save()}>
            {state === "saving" ? <Spinner size={12} /> : null} Salvar
          </Button>
        </div>
      </GlassPanel>

      <aside className="space-y-4">
        <GlassPanel className="p-4" raised={false}>
          <p className="flex items-center gap-2 text-sm font-medium text-fg">
            <Icon name="info" size={14} /> Como isso é usado
          </p>
          <ul className="mt-2 space-y-1.5 text-sm text-fg-muted">
            <li>Entra no prompt deste agente a cada pedido, depois das regras dele.</li>
            <li>Muda estilo e prioridade. Não libera ferramenta nem passa por cima das políticas.</li>
            <li>Cada vez que você salva, a versão anterior fica no Harness › Versões.</li>
          </ul>
        </GlassPanel>
        {examples.length > 0 && (
          <GlassPanel className="p-4" raised={false}>
            <p className="text-sm font-medium text-fg">Pedidos que ele recebe</p>
            <ul className="mt-2 space-y-1 text-sm text-fg-muted">
              {examples.map((e) => (
                <li key={e}>“{e}”</li>
              ))}
            </ul>
          </GlassPanel>
        )}
      </aside>
    </div>
  );
}
