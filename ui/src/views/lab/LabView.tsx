import { useEffect, useRef, useState } from "react";
import { AppDialog, Button, EmptyState, Icon, Segmented, Skeleton } from "../../components/ui";
import { cn } from "../../lib/cn";
import { core } from "../../lib/host";
import { AgentCode } from "./AgentCode";
import { AgentContext } from "./AgentContext";
import { AgentInstructions } from "./AgentInstructions";
import { AgentMemory } from "./AgentMemory";
import { AgentMemoryEditor } from "./AgentMemoryEditor";
import { AgentSpec } from "./AgentSpec";
import { AgentErrors, AgentRoute, AgentSkills } from "./AgentWork";
import { Experiments } from "./Experiments";
import { AgentList, LabHub, type LabArea } from "./LabHub";
import { MemoryTree } from "./MemoryTree";
import { AGENTS, AGENT_LOOK, call, type Memory, type Spec } from "./types";

// AI Research Lab: tres areas na entrada, cada uma SO com o que e dela (antes a ficha do agente misturava edicao,
// experimentos e evidencias numa barra so, e um clique num lado trocava o estado do outro).
//   Agentes      -> lista + ficha do agente (editar: visao, instrucoes, memoria, contexto, rota, skills, erros, codigo)
//   Experimentos -> testes de um agente (comparar versoes; evidencias das comparacoes)
//   Memoria      -> arvore panoramica do Cerebro com os agentes + editor de memoria e contexto do agente escolhido
// Nada aqui amplia permissao: ferramentas e politicas continuam no codigo do executor.

type Area = "hub" | "agents" | "agent" | LabArea;
type Tab = "visao" | "instrucoes" | "memoria" | "contexto" | "rota" | "skills" | "erros" | "codigo";

const TABS: Array<{ id: Tab; label: string; hint: string }> = [
  { id: "visao", label: "Visão geral", hint: "Papel, ferramentas, modelo, limites e políticas" },
  { id: "instrucoes", label: "Instruções", hint: "Seu jeito de pedir: estilo e prioridades" },
  { id: "memoria", label: "Memória", hint: "Regras, como executar e falhas conhecidas" },
  { id: "contexto", label: "Contexto", hint: "Notas do Cérebro e texto extra para o prompt" },
  { id: "rota", label: "Rota", hint: "Por onde o pedido chega até o agente" },
  { id: "skills", label: "Skills", hint: "Manuais do Cérebro que o agente aplica" },
  { id: "erros", label: "Erros", hint: "Execuções que falharam e em que passo" },
  { id: "codigo", label: "Código", hint: "Arquivos do agente e mudanças revisadas" },
];
const INTRO: Record<Area, string> = {
  hub: "Três áreas, cada uma com um trabalho: editar os agentes, testar versões e cuidar da memória.",
  agents: "Escolha um agente para ajustar como ele trabalha, ou crie um novo.",
  agent: "",
  experiments: "Só testes: crie versões de um agente, rode os mesmos casos e compare com a versão ativa.",
  memory: "Só memória e contexto: a árvore do Cérebro com cada agente e o que eles usam em comum.",
};

type Move = { area?: Area; agent?: string; tab?: Tab };

export function LabView() {
  const [area, setArea] = useState<Area>("hub");
  const [agent, setAgent] = useState<string>("MAESTRO");
  const [tab, setTab] = useState<Tab>("visao");
  const [evidence, setEvidence] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [loadedSpec, setSpec] = useState<Spec | null>(null);
  const spec = loadedSpec?.agent === agent ? loadedSpec : null;
  const [memory, setMemory] = useState<Memory | null>(null);
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState<Move | null>(null);
  const tabsRef = useRef<HTMLDivElement>(null);

  // A ficha so carrega quando esta aberta (e recarrega ao trocar de agente)
  useEffect(() => {
    if (area !== "agent") return;
    let active = true;
    setSpec(null);
    setError("");
    void call(core().call("studioAgent", agent)).then((r) => {
      if (!active) return;
      if (!r.ok) return setError(r.error || "Não deu para abrir o agente.");
      setSpec(r.spec as Spec);
      setMemory(r.memory as Memory);
    });
    return () => { active = false; };
  }, [agent, attempt, area]);

  const apply = (m: Move) => {
    if (m.agent) setAgent(m.agent);
    if (m.tab) setTab(m.tab);
    if (m.area) setArea(m.area);
  };
  // Sair de uma edicao nao salva pede confirmacao (vale para trocar de area, agente ou aba)
  const go = (m: Move) => (dirty ? setPending(m) : apply(m));

  const onTabKey = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const i = TABS.findIndex((t) => t.id === tab);
    const next = TABS[(i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length]!;
    go({ tab: next.id });
    requestAnimationFrame(() => tabsRef.current?.querySelector<HTMLButtonElement>(`[data-tab="${next.id}"]`)?.focus());
  };

  const look = AGENT_LOOK[agent]!;
  const agentPicker = (
    <label className="lab-agent-select">
      <span className="sr-only">Agente</span>
      <select value={agent} onChange={(e) => go({ agent: e.target.value })}>
        {AGENTS.map((id) => <option key={id} value={id}>{AGENT_LOOK[id]!.name}</option>)}
      </select>
    </label>
  );

  return (
    <div className={cn("h-full", area === "agent" || area === "experiments" ? "overflow-y-auto px-4 md:px-8" : "lab-landing")}>
      {area === "hub" || area === "agents" || area === "memory" ? (
        <>
          <header className="lab-intro photo-ink">
            <h1 className="text-fg">{area === "hub" ? "AI Research Lab" : area === "agents" ? "Agentes" : "Memória dos agentes"}</h1>
            <p className="text-fg-muted">{INTRO[area]}</p>
          </header>
          {area !== "hub" && <div className="lab-back"><Button size="compact" icon="arrow-left" onClick={() => go({ area: "hub" })}>Laboratório</Button></div>}
          {area === "hub" && <LabHub onOpen={(next) => go({ area: next })} />}
          {area === "agents" && <AgentList onOpen={(id) => go({ agent: id, tab: "visao", area: "agent" })} />}
          {area === "memory" && (
            <div className="lab-memory">
              <MemoryTree selected={agent} onSelect={(id) => id !== agent && go({ agent: id })} />
              <section className="lab-memory-editor" aria-label={`Memória de ${look.name}`}>
                <header>
                  <span className="lab-editor-emblem" style={{ "--agent-color": look.color } as React.CSSProperties}><Icon name={look.icon} size={18} /></span>
                  <h2 className="text-lg font-semibold text-fg">Memória e contexto de {look.name}</h2>
                  <span className="flex-1" />
                  {agentPicker}
                </header>
                <AgentMemoryEditor key={agent} agent={agent} onDirty={setDirty} />
              </section>
            </div>
          )}
        </>
      ) : (
        <div className="mx-auto max-w-[1450px] py-5">
          <section aria-label={area === "agent" ? `Agente ${look.name}` : `Experimentos de ${look.name}`} className="lab-workbench">
            <header className="lab-workbench-title">
              <Button icon="arrow-left" size="compact" onClick={() => go({ area: area === "agent" ? "agents" : "hub" })}>
                {area === "agent" ? "Agentes" : "Laboratório"}
              </Button>
              <span className="lab-editor-emblem" style={{ "--agent-color": look.color } as React.CSSProperties}><Icon name={look.icon} size={18} /></span>
              <div className="min-w-0">
                <h2 className="truncate text-lg font-semibold text-fg">{area === "agent" ? look.name : `Experimentos · ${look.name}`}</h2>
                <p className="truncate text-xs text-fg-muted">{area === "agent" ? spec?.role ?? "" : "Variantes, casos e comparação com a versão ativa"}</p>
              </div>
              {agentPicker}
            </header>

            {area === "agent" ? <>
              <div ref={tabsRef} role="tablist" aria-label="Seções do agente" onKeyDown={onTabKey} className="no-scrollbar lab-editor-tabs flex gap-1 overflow-x-auto p-1">
                {TABS.map((t) => {
                  const on = t.id === tab;
                  return (
                    <button key={t.id} data-tab={t.id} type="button" role="tab" aria-selected={on} tabIndex={on ? 0 : -1} title={t.hint}
                      onClick={() => !on && go({ tab: t.id })}
                      className={cn("flex shrink-0 items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm transition-colors",
                        on ? "bg-primary font-medium text-fg-inverse" : "text-fg-muted hover:bg-hover hover:text-fg")}>
                      {t.label}
                    </button>
                  );
                })}
              </div>
              <div role="tabpanel" aria-label={TABS.find((t) => t.id === tab)?.label} key={`${agent}-${tab}`} className="lab-editor-panel">
                {error ? (
                  <EmptyState icon="alert-circle" title="Agente indisponível" action={<Button onClick={() => setAttempt((v) => v + 1)}>Tentar de novo</Button>}>{error}</EmptyState>
                ) : !spec || !memory ? (
                  <div className="space-y-4"><Skeleton className="h-40 rounded-r4" /><Skeleton className="h-64 rounded-r4" /></div>
                ) : tab === "visao" ? <AgentSpec spec={spec} onGo={(t) => go({ tab: t as Tab })} />
                  : tab === "instrucoes" ? <AgentInstructions agent={agent} examples={spec.examples} onDirty={setDirty} />
                  : tab === "memoria" ? <AgentMemory agent={agent} memory={memory} onSaved={setMemory} onDirty={setDirty} />
                  : tab === "contexto" ? <AgentContext agent={agent} memory={memory} onSaved={setMemory} onDirty={setDirty} />
                  : tab === "rota" ? <AgentRoute spec={spec} onInstructions={() => go({ tab: "instrucoes" })} />
                  : tab === "skills" ? <AgentSkills agent={agent} />
                  : tab === "erros" ? <AgentErrors agent={agent} />
                  : <AgentCode agent={agent} name={look.name} files={spec.files} />}
              </div>
            </> : <>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-hairline px-3 py-2">
                <Segmented label="Parte dos experimentos" value={evidence ? "evidencias" : "comparar"} onValueChange={(v) => setEvidence(v === "evidencias")}
                  options={[{ value: "comparar", label: "Comparar versões" }, { value: "evidencias", label: "Evidências" }]} />
              </div>
              <div className="lab-editor-panel">
                <Experiments key={agent} agent={agent} evidence={evidence} onEvidence={() => setEvidence(true)} onExperiments={() => setEvidence(false)} />
              </div>
            </>}
          </section>
        </div>
      )}

      <AppDialog
        open={!!pending}
        onOpenChange={(o) => !o && setPending(null)}
        title="Descartar o que não foi salvo?"
        description="Você mudou algo e ainda não salvou. Se sair agora, a alteração se perde."
        actions={<>
          <Button variant="ghost" onClick={() => setPending(null)}>Continuar editando</Button>
          <Button variant="danger" onClick={() => { setDirty(false); if (pending) apply(pending); setPending(null); }}>Descartar</Button>
        </>}
      />
    </div>
  );
}
