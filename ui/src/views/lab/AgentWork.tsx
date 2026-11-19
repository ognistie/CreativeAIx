import { useCallback, useEffect, useState } from "react";
import { Button, EmptyState, Field, GlassPanel, Icon, Skeleton } from "../../components/ui";
import { core } from "../../lib/host";
import { appliesTo, attachSkill, newSkillNote, SKILLS_DIR, skillAgents, skillSlug } from "../../lib/skillNote";
import { AGENT_LOOK, call, type Spec } from "./types";

// Abas de trabalho da ficha do agente: Rota (por onde o pedido chega ate ele), Skills (manuais do Cerebro que ele
// aplica; criar e ligar) e Erros (execucoes que falharam e em que passo). Nada aqui amplia permissao: skills e
// notas sao texto de referencia; ferramentas e politicas continuam no codigo do executor.

const textarea = "w-full resize-y rounded-r2 border border-hairline bg-surface p-3 text-sm text-fg";

/** Rota: o caminho fixo da camada de harness, com o que este agente recebe, usa e pode fazer. */
export function AgentRoute({ spec, onInstructions }: { spec: Spec; onInstructions: () => void }) {
  const look = AGENT_LOOK[spec.agent]!;
  const steps = [
    { name: "Pedido", text: "voz ou texto" },
    { name: "Intérprete", text: "completa com a conversa" },
    ...(spec.agent === "MAESTRO" ? [] : [{ name: "Maestro", text: "divide e escolhe o agente" }]),
    { name: look.name, text: "monta os passos", self: true },
    { name: "Políticas", text: "validam antes de agir" },
    { name: "Executor", text: "um passo por vez" },
  ];
  return (
    <div className="space-y-4">
      <GlassPanel className="p-5">
        <h3 className="text-md font-semibold text-fg">Por onde o pedido chega</h3>
        <ol className="lab-route" aria-label="Caminho do pedido">
          {steps.map((s, i) => (
            <li key={s.name} data-self={s.self || undefined} style={{ "--agent": look.color } as React.CSSProperties}>
              <strong>{s.name}</strong><small>{s.text}</small>
              {i < steps.length - 1 && <Icon name="arrow-right" size={14} className="lab-route-arrow" />}
            </li>
          ))}
        </ol>
      </GlassPanel>
      <div className="grid gap-4 md:grid-cols-2">
        <GlassPanel className="space-y-2 p-5">
          <h3 className="text-sm font-semibold text-fg">Recebe</h3>
          <p className="text-sm text-fg-muted">{spec.inputs || "—"}</p>
          <h3 className="pt-2 text-sm font-semibold text-fg">Usa</h3>
          <p className="text-sm text-fg-muted">{spec.uses || "—"}</p>
        </GlassPanel>
        <GlassPanel className="space-y-2 p-5">
          <h3 className="text-sm font-semibold text-fg">Pode fazer ({spec.tools.length} ferramentas)</h3>
          <ul className="flex flex-wrap gap-1.5">
            {spec.tools.map((t) => <li key={t.name} className="rounded-full border border-hairline px-2.5 py-0.5 font-mono text-xs text-fg-muted" title={t.permission}>{t.name}</li>)}
          </ul>
          <p className="pt-1 text-xs text-fg-subtle">{spec.authorization}</p>
        </GlassPanel>
      </div>
      <p className="flex flex-wrap items-center gap-3 text-sm text-fg-muted">
        A rota é código (Maestro + políticas). Para mudar <em>quando</em> este agente é chamado ou como ele responde, ajuste as instruções.
        <Button size="compact" icon="pen" onClick={onInstructions}>Abrir instruções</Button>
      </p>
    </div>
  );
}

type SkillRow = { rel: string; name: string; md: string };

/** Skills: as do catalogo que o agente aplica, criar uma nova e ligar uma existente a ele. */
export function AgentSkills({ agent }: { agent: string }) {
  const [rows, setRows] = useState<SkillRow[] | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState<null | { mode: "new" } | { mode: "attach"; row: SkillRow }>(null);
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [line, setLine] = useState("");
  const [triggers, setTriggers] = useState("");
  const [busy, setBusy] = useState(false);
  const look = AGENT_LOOK[agent]!;

  const load = useCallback(async () => {
    setError("");
    const ov = await call(core().call("brainOverview"));
    if (!ov.ok) return setError(ov.error || "Não deu para ler o Cérebro.");
    const rels = ((ov.notes as Array<{ rel: string; folder: string }>) ?? []).filter((n) => n.folder === SKILLS_DIR).map((n) => n.rel);
    const read = await Promise.all(rels.map(async (rel) => {
      const r = await call(core().call("brainRead", rel));
      return { rel, name: rel.split("/").pop()!.replace(/\.md$/i, ""), md: String(r.text ?? "") };
    }));
    setRows(read.filter((r) => /^tipo:\s*skill\s*$/m.test(r.md)));
  }, []);
  useEffect(() => { setRows(null); void load(); }, [load, agent]);

  const reset = () => { setForm(null); setName(""); setPurpose(""); setLine(""); setTriggers(""); };
  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      if (form?.mode === "new") {
        const md = newSkillNote({ name, purpose, agent, line, triggers, today: new Date().toLocaleDateString("sv-SE") });
        const r = await call(core().call("brainCreate", `${SKILLS_DIR}/${skillSlug(name)}.md`, md));
        if (!r.ok) return setError(r.error || "A skill não foi criada.");
        setNotice(`Skill “${name.trim()}” criada para ${look.name}.`);
      } else if (form?.mode === "attach") {
        const r = await call(core().call("brainSave", form.row.rel, attachSkill(form.row.md, agent, line)));
        if (!r.ok) return setError(r.error || "A skill não foi ligada.");
        setNotice(`${look.name} agora aplica “${form.row.name}”.`);
      }
      reset();
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (!rows) return error ? <EmptyState icon="alert-circle" title="Skills indisponíveis">{error}</EmptyState> : <Skeleton className="h-64 rounded-r4" />;
  const mine = rows.filter((r) => skillAgents(r.md).includes(agent) && appliesTo(r.md, agent));
  const others = rows.filter((r) => !mine.includes(r));
  const ready = form?.mode === "new" ? name.trim().length >= 3 && purpose.trim() && line.trim() : line.trim().length >= 6;

  return (
    <div className="space-y-4">
      {notice && <p role="status" className="text-sm text-fg">{notice}</p>}
      {error && <p role="alert" className="rounded-r2 bg-bad/10 p-3 text-sm text-bad-ink">{error}</p>}
      <GlassPanel className="space-y-3 p-5">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-md font-semibold text-fg">Skills de {look.name} ({mine.length})</h3>
            <p className="text-xs text-fg-muted">Entram no prompt quando o pedido fala das palavras de ativação. Skill é manual de uso: não dá permissão nova.</p>
          </div>
          <Button size="compact" icon="plus" disabled={!!form} onClick={() => setForm({ mode: "new" })}>Nova skill</Button>
        </header>
        {mine.length === 0 ? <p className="text-sm text-fg-muted">Nenhuma skill aplicada a este agente ainda.</p> : (
          <ul className="grid gap-2 md:grid-cols-2">
            {mine.map((r) => (
              <li key={r.rel} className="rounded-r3 border border-hairline p-3">
                <strong className="text-sm text-fg">{r.name}</strong>
                <p className="mt-1 line-clamp-2 text-xs text-fg-muted">{/>\s*\[!skill\][^\n]*\n>\s*(.+)/.exec(r.md)?.[1] ?? ""}</p>
              </li>
            ))}
          </ul>
        )}
      </GlassPanel>

      {form && (
        <GlassPanel className="space-y-3 p-5">
          <h3 className="text-md font-semibold text-fg">{form.mode === "new" ? `Nova skill para ${look.name}` : `Ligar “${form.row.name}” a ${look.name}`}</h3>
          {form.mode === "new" && <>
            <Field aria-label="Nome da skill" placeholder="Nome (ex.: Revisar planilha)" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
            <Field aria-label="O que a skill faz" placeholder="O que faz, em uma frase" value={purpose} maxLength={200} onChange={(e) => setPurpose(e.target.value)} />
            <Field aria-label="Palavras de ativação" placeholder="Palavras que ativam, separadas por vírgula (ex.: planilha, total)" value={triggers} maxLength={200} onChange={(e) => setTriggers(e.target.value)} />
          </>}
          <textarea className={textarea} rows={3} maxLength={300} aria-label="Como o agente aplica"
            placeholder={`Como ${look.name} aplica a skill (uma instrução curta e conferível)`} value={line} onChange={(e) => setLine(e.target.value)} />
          <div className="flex gap-2">
            <Button variant="primary" size="compact" disabled={!ready || busy} onClick={() => void submit()}>{form.mode === "new" ? "Criar skill" : "Ligar skill"}</Button>
            <Button variant="ghost" size="compact" onClick={reset}>Cancelar</Button>
          </div>
          <p className="text-xs text-fg-subtle">Fica na camada pessoal do Cérebro ({SKILLS_DIR}/). Dá para desfazer pelo Cérebro.</p>
        </GlassPanel>
      )}

      {others.length > 0 && (
        <GlassPanel className="space-y-3 p-5">
          <h3 className="text-sm font-semibold text-fg">Outras skills do catálogo</h3>
          <ul className="grid gap-2 md:grid-cols-2">
            {others.map((r) => (
              <li key={r.rel} className="flex items-start justify-between gap-3 rounded-r3 border border-hairline p-3">
                <span className="min-w-0">
                  <strong className="text-sm text-fg">{r.name}</strong>
                  <span className="mt-1 block line-clamp-2 text-xs text-fg-muted">{/>\s*\[!skill\][^\n]*\n>\s*(.+)/.exec(r.md)?.[1] ?? ""}</span>
                </span>
                <Button size="compact" disabled={!!form} onClick={() => setForm({ mode: "attach", row: r })}>Usar</Button>
              </li>
            ))}
          </ul>
        </GlassPanel>
      )}
    </div>
  );
}

type TaskEvent = { type: string; step?: number; agent: string; action: string; status: string; result: string; ok?: boolean | null };
type Task = { id: string; goal: string; state: string; started_at: string; events: TaskEvent[] };

/** Passos que falharam (step_finished ok=false), com o agente de cada passo (vem do step_started). */
export function failedSteps(task: Task): TaskEvent[] {
  const owner = new Map<number | undefined, string>();
  for (const e of task.events) if (e.type === "step_started") owner.set(e.step, e.agent);
  return task.events.filter((e) => e.type === "step_finished" && e.ok === false).map((e) => ({ ...e, agent: e.agent || owner.get(e.step) || "" }));
}

/** Execucao entra na aba Erros: terminou em falha/interrompida, ou um passo DESTE agente falhou no caminho. */
export function isFailure(task: Task, agent: string): boolean {
  return task.state === "failed" || task.state === "interrupted" || failedSteps(task).some((e) => e.agent === agent);
}

/** Erros: execucoes que falharam com este agente e o passo onde deu errado (registro de tarefas). */
export function AgentErrors({ agent }: { agent: string }) {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setTasks(null);
    void call(core().call("labObserve", agent, "")).then((r) => {
      if (!active) return;
      if (!r.ok) return setError(r.error || "Registro indisponível.");
      setTasks(((r.tasks as Task[]) ?? []).filter((t) => isFailure(t, agent)));
    });
    return () => { active = false; };
  }, [agent]);

  if (error) return <EmptyState icon="alert-circle" title="Registro indisponível">{error}</EmptyState>;
  if (!tasks) return <Skeleton className="h-64 rounded-r4" />;
  if (tasks.length === 0) return <EmptyState icon="check" title="Nenhuma falha registrada">As execuções com {AGENT_LOOK[agent]!.name} que falharem aparecem aqui, com o passo onde deu errado.</EmptyState>;
  return (
    <ul className="space-y-3" aria-label="Execuções que falharam">
      {tasks.map((t) => {
        const steps = failedSteps(t);
        const where = steps.find((e) => e.agent === agent) ?? steps.at(-1);
        return (
          <li key={t.id}>
            <GlassPanel className="space-y-2 p-4">
              <header className="flex flex-wrap items-baseline justify-between gap-2">
                <strong className="text-sm text-fg">{t.goal || "(sem objetivo registrado)"}</strong>
                <span className="font-mono text-xs text-fg-subtle">{t.started_at.replace("T", " ").slice(0, 16)} · {t.id}</span>
              </header>
              {where ? (
                <p className="text-sm text-bad-ink">
                  Passo {where.step ?? "?"} · <span className="font-mono">{where.action || where.type}</span>{where.agent && where.agent !== agent ? ` (${AGENT_LOOK[where.agent]?.name ?? where.agent})` : ""}: {where.result || where.status || "falhou sem mensagem"}
                </p>
              ) : <p className="text-sm text-fg-muted">{t.state === "interrupted" ? "Interrompida (o app fechou ou a tarefa foi parada) antes de terminar." : "Terminou como falha sem um passo marcado: o erro foi no plano ou na validação."}</p>}
              <details className="text-xs text-fg-muted">
                <summary className="cursor-pointer">Todos os eventos ({t.events.length})</summary>
                <ol className="mt-2 space-y-1">
                  {t.events.map((e, i) => <li key={i} className="font-mono">{e.step ?? "·"} {e.type} {e.agent} {e.action} {e.status} {e.result && `— ${e.result}`}</li>)}
                </ol>
              </details>
            </GlassPanel>
          </li>
        );
      })}
    </ul>
  );
}
