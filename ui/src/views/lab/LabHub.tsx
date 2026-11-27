import { useCallback, useEffect, useState } from "react";
import { AppDialog, Button, Field, Icon } from "../../components/ui";
import { core } from "../../lib/host";
import { skillSlug } from "../../lib/skillNote";
import { AgentArtwork } from "./AgentArtwork";
import { DraftRoute } from "./DraftRoute";
import { AGENTS, AGENT_LOOK, call } from "./types";

// Entrada do AI Research Lab: tres areas, cada uma so com o que e dela.
//   Agentes      -> editar cada agente (instrucoes, memoria, contexto, rota, skills, erros, codigo) e criar um novo
//   Experimentos -> so testes: versoes, casos, comparacao medida com a anterior
//   Memoria      -> so memoria e contexto: a arvore panoramica do Cerebro com cada agente e o editor da memoria

export type LabArea = "agents" | "experiments" | "memory";

const AREAS: Array<{ id: LabArea; title: string; lead: string; art: (typeof AGENTS)[number]; what: string; why: string; how: string }> = [
  { id: "agents", title: "Agentes", art: "MAESTRO", lead: "Ajuste como cada agente trabalha.",
    what: "Instruções, memória, contexto, rota, skills, erros e código de cada agente; e criar um agente novo.",
    why: "Corrigir de vez um jeito errado de agir, em vez de repetir a correção em toda conversa.",
    how: "Escolha o agente, abra a aba e salve. Vale a partir do próximo pedido." },
  { id: "experiments", title: "Experimentos", art: "DATA", lead: "Teste uma versão antes de usar.",
    what: "Criar variantes de um agente, rodar os mesmos casos e comparar com a versão ativa.",
    why: "Saber, com números, se a mudança melhorou antes de colocar no dia a dia.",
    how: "Crie a variante, escolha os casos e rode. Promova só o que passar." },
  { id: "memory", title: "Memória", art: "WEB", lead: "Veja e edite o que os agentes lembram.",
    what: "O harness em 3D: por onde os pedidos passam, a memória de cada agente e o que o sistema aprendeu, ao vivo.",
    why: "Entender de onde vem o contexto de uma resposta e limpar o que está velho ou errado.",
    how: "Gire e aproxime a cena, clique num agente ou numa nota e edite logo abaixo." },
];

export function LabHub({ onOpen }: { onOpen: (area: LabArea) => void }) {
  return (
    <div className="lab-hub" role="list" aria-label="Áreas do laboratório">
      {AREAS.map((area) => (
        <button key={area.id} type="button" role="listitem" className="lab-hub-card" onClick={() => onOpen(area.id)}>
          <span className="lab-hub-art"><AgentArtwork agent={area.art} /></span>
          <span className="lab-hub-text">
            <strong>{area.title}</strong>
            <span className="lab-hub-lead">{area.lead}</span>
            <dl>
              <dt>O que dá para fazer</dt><dd>{area.what}</dd>
              <dt>Para que serve</dt><dd>{area.why}</dd>
              <dt>Como usar</dt><dd>{area.how}</dd>
            </dl>
            <span className="lab-hub-go">Abrir {area.title.toLowerCase()} <Icon name="arrow-right" size={14} /></span>
          </span>
        </button>
      ))}
    </div>
  );
}

export const DRAFTS_DIR = "10 Agentes/Rascunhos";
type Draft = { rel: string; name: string };

/** Lista dos agentes (cartoes grandes com a ilustracao) + rascunhos de agentes novos + o cartao "+". */
export function AgentList({ onOpen }: { onOpen: (agent: string) => void }) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [creating, setCreating] = useState(false);
  const [view, setView] = useState<{ rel: string; text: string } | null>(null);

  const load = useCallback(async () => {
    const ov = await call(core().call("brainOverview"));
    const notes = ((ov.notes as Array<{ rel: string; folder: string }>) ?? []).filter((n) => n.folder === DRAFTS_DIR);
    setDrafts(notes.map((n) => ({ rel: n.rel, name: n.rel.split("/").pop()!.replace(/\.md$/i, "") })));
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <>
      <div className="lab-agents" role="list" aria-label="Agentes">
        {AGENTS.map((id) => (
          <button key={id} type="button" role="listitem" className="lab-agent-card" onClick={() => onOpen(id)}>
            <span className="lab-agent-art"><AgentArtwork agent={id} /></span>
            <strong>{AGENT_LOOK[id]!.name}</strong>
          </button>
        ))}
        {drafts.map((d) => (
          <button key={d.rel} type="button" role="listitem" className="lab-agent-card lab-agent-draft"
            onClick={() => void call(core().call("brainRead", d.rel)).then((r) => setView({ rel: d.rel, text: String(r.text ?? "") }))}>
            <span className="lab-agent-art lab-agent-art-draft" aria-hidden><Icon name="file-text" size={34} weight={1.3} /></span>
            <strong>{d.name}<small>Rascunho</small></strong>
          </button>
        ))}
        <button type="button" role="listitem" className="lab-agent-card lab-agent-add" onClick={() => setCreating(true)} aria-label="Adicionar um agente">
          <span className="lab-agent-art" aria-hidden><Icon name="plus" size={40} weight={1.4} /></span>
          <strong>Novo agente</strong>
        </button>
      </div>
      <NewAgentDialog open={creating} onOpenChange={setCreating} onCreated={() => { setCreating(false); void load(); }} />
      <AppDialog open={!!view} onOpenChange={(o) => !o && setView(null)} title={view?.rel.split("/").pop()?.replace(/\.md$/i, "") ?? ""}
        description="Revise o rascunho e teste a rota com pedidos sintéticos no laboratório."
        actions={<>
          <Button variant="danger" onClick={() => view && void call(core().call("brainDelete", view.rel)).then(() => { setView(null); void load(); })}>Excluir rascunho</Button>
          <Button onClick={() => setView(null)}>Fechar</Button>
        </>}>
        {view && <DraftRoute key={view.rel} note={view.rel} />}
        <details className="mt-4 text-sm text-fg-muted">
          <summary>Ver descrição do rascunho</summary>
          <pre className="mt-2 max-h-[30vh] overflow-auto whitespace-pre-wrap rounded-r2 bg-surface p-3 text-xs">{view?.text}</pre>
        </details>
      </AppDialog>
    </>
  );
}

function NewAgentDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (o: boolean) => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [base, setBase] = useState<string>("DESKTOP");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState("");
  const ready = name.trim().length >= 3 && role.trim().length >= 10;

  const create = async () => {
    setError("");
    const text = [
      "---", "tipo: agente-rascunho", `base: ${base}`, `criado: ${new Date().toLocaleDateString("sv-SE")}`, "---",
      `# ${name.trim()}`, "", "> [!info] Rascunho", "> A rota pode ser testada no laboratório.", "",
      "## Papel", role.trim(), "",
      "## Ferramentas", `Mesmas de [[${AGENT_LOOK[base]!.name}]] (o executor valida o agente dono de cada ação).`, "",
      "## Instruções", instructions.trim() || "-", "",
    ].join("\n");
    const r = await call(core().call("brainCreate", `${DRAFTS_DIR}/${skillSlug(name) || "agente"}.md`, text));
    if (!r.ok) return setError(r.error || "O rascunho não foi criado.");
    setName(""); setRole(""); setInstructions("");
    onCreated();
  };

  return (
    <AppDialog open={open} onOpenChange={onOpenChange} title="Novo agente"
      description="Descreva um rascunho para testar sua rota no laboratório."
      actions={<>
        <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancelar</Button>
        <Button variant="primary" disabled={!ready} onClick={() => void create()}>Criar rascunho</Button>
      </>}>
      <div className="grid gap-3">
        <Field aria-label="Nome do agente" placeholder="Nome (ex.: Agenda)" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} />
        <Field aria-label="Papel do agente" placeholder="O que ele faz (ex.: marca e confere compromissos)" value={role} maxLength={200} onChange={(e) => setRole(e.target.value)} />
        <label className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">Ferramentas de
          <select className="rounded-r2 border border-hairline bg-surface px-3 py-2 text-sm text-fg" value={base} onChange={(e) => setBase(e.target.value)}>
            {AGENTS.filter((a) => a !== "MAESTRO").map((a) => <option key={a} value={a}>{AGENT_LOOK[a]!.name}</option>)}
          </select>
        </label>
        <textarea className="w-full resize-y rounded-r2 border border-hairline bg-surface p-3 text-sm text-fg" rows={4} maxLength={700}
          aria-label="Instruções do agente" placeholder="Instruções: estilo, prioridades, o que conferir antes de concluir" value={instructions} onChange={(e) => setInstructions(e.target.value)} />
        {error && <p role="alert" className="text-sm text-bad-ink">{error}</p>}
      </div>
    </AppDialog>
  );
}
