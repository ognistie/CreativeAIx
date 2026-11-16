import { useCallback, useEffect, useRef, useState } from "react";
import { AppDialog, Button, EmptyState, GlassPanel, Icon, Skeleton, type IconName } from "../../components/ui";
import { cn } from "../../lib/cn";
import { core } from "../../lib/host";
import { AgentCode } from "./AgentCode";
import { AgentContext } from "./AgentContext";
import { AgentInstructions } from "./AgentInstructions";
import { AgentMemory } from "./AgentMemory";
import { AgentSpec } from "./AgentSpec";
import { Experiments } from "./Experiments";
import { AGENT_LOOK, AGENTS, call, EFFORT_LABEL, type Memory, type Spec } from "./types";

// AI Research Lab: estudio de cada agente. Uma barra com os agentes e, para o escolhido, abas com a
// especificacao, as suas instrucoes, a memoria (nota no Cerebro), o contexto ligado a outras notas, o codigo
// (leitura + mudanca segura pelo Modo Desenvolvedor) e os testes. Nada aqui amplia permissao: ferramentas e
// politicas continuam no codigo do executor.

type Tab = "visao" | "instrucoes" | "memoria" | "contexto" | "codigo" | "testes";

const TABS: Array<{ id: Tab; label: string; icon: IconName; hint: string }> = [
  { id: "visao", label: "Visão geral", icon: "info", hint: "Papel, ferramentas, modelo, limites e políticas" },
  { id: "instrucoes", label: "Instruções", icon: "pen", hint: "Seu jeito de pedir: estilo e prioridades" },
  { id: "memoria", label: "Memória", icon: "brain", hint: "Regras, como executar e falhas conhecidas" },
  { id: "contexto", label: "Contexto", icon: "link", hint: "Notas do Cérebro e texto extra para o prompt" },
  { id: "codigo", label: "Código", icon: "code", hint: "Arquivos do agente e mudanças revisadas" },
  { id: "testes", label: "Testes", icon: "flask", hint: "Versões, experimentos e comparação" },
];

export function LabView() {
  const [agent, setAgent] = useState<string>("MAESTRO");
  const [tab, setTab] = useState<Tab>("visao");
  const [spec, setSpec] = useState<Spec | null>(null);
  const [memory, setMemory] = useState<Memory | null>(null);
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState<{ agent?: string; tab?: Tab } | null>(null);
  const tabsRef = useRef<HTMLDivElement>(null);

  const load = useCallback((a: string) => {
    setSpec(null);
    setError("");
    void call(core().call("studioAgent", a)).then((r) => {
      if (!r.ok) return setError(r.error || "Não deu para abrir o agente.");
      setSpec(r.spec as Spec);
      setMemory(r.memory as Memory);
    });
  }, []);
  useEffect(() => load(agent), [agent, load]);

  // Trocar de agente ou aba com alteracao nao salva pede confirmacao
  const go = (next: { agent?: string; tab?: Tab }) => {
    if (dirty) return setPending(next);
    if (next.agent) setAgent(next.agent);
    if (next.tab) setTab(next.tab);
  };

  const onTabKey = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const i = TABS.findIndex((t) => t.id === tab);
    const next = TABS[(i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length]!;
    go({ tab: next.id });
    requestAnimationFrame(() => tabsRef.current?.querySelector<HTMLButtonElement>(`[data-tab="${next.id}"]`)?.focus());
  };

  const look = AGENT_LOOK[agent]!;

  return (
    <div className="h-full overflow-y-auto px-8">
      <div className="mx-auto max-w-[1180px] py-10">
        <header className="on-photo animate-enter mb-7">
          <h1 className="font-display text-[28px] font-medium tracking-[-0.03em] text-fg">AI Research Lab</h1>
          <p className="mt-1.5 max-w-2xl text-md text-fg-muted">
            O estúdio de cada agente: veja como ele funciona, ajuste instruções e memória, ligue notas do Cérebro, peça mudanças de código revisadas e teste
            antes de publicar.
          </p>
        </header>

        <div className="grid items-start gap-6 xl:grid-cols-[232px_minmax(0,1fr)]">
          {/* Agentes */}
          <nav aria-label="Agentes" className="min-w-0 xl:sticky xl:top-4">
            <p className="mb-2 px-1 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">Agentes</p>
            <ul className="no-scrollbar flex gap-2 overflow-x-auto pb-1 xl:flex-col xl:overflow-visible">
              {AGENTS.map((a) => {
                const l = AGENT_LOOK[a]!;
                const on = a === agent;
                return (
                  <li key={a} className="shrink-0">
                    <button
                      type="button"
                      aria-current={on ? "true" : undefined}
                      onClick={() => !on && go({ agent: a })}
                      className={cn(
                        "press group flex w-full items-center gap-3 rounded-r3 border p-2.5 pr-3 text-left transition-colors",
                        on ? "border-hairline-hi bg-glass-hi shadow-[0_6px_20px_var(--shadow-soft)]" : "border-transparent hover:bg-hover",
                      )}
                    >
                      <span className="grid size-9 shrink-0 place-items-center rounded-r2 text-white" style={{ background: l.color }}>
                        <Icon name={l.icon} size={17} />
                      </span>
                      <span className="min-w-0">
                        <span className={cn("block text-md", on ? "font-semibold text-fg" : "text-fg")}>{l.name}</span>
                        <span className="block truncate font-mono text-[11px] text-fg-muted">{a}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>

          <section aria-label={`Agente ${look.name}`} className="min-w-0">
            {/* Cabecalho do agente */}
            <GlassPanel className="mb-5 overflow-hidden p-0">
              <div aria-hidden className="h-1.5" style={{ background: `linear-gradient(90deg, ${look.color}, transparent)` }} />
              <div className="flex flex-wrap items-start gap-4 p-5">
                <span className="grid size-14 shrink-0 place-items-center rounded-r3 text-white shadow-[0_10px_24px_-10px_rgb(0_0_0/0.5)]" style={{ background: look.color }}>
                  <Icon name={look.icon} size={26} />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="font-display text-[22px] font-semibold tracking-[-0.02em] text-fg">{look.name}</h2>
                  {spec ? <p className="mt-1 max-w-2xl text-md leading-relaxed text-fg-muted">{spec.role}</p> : <Skeleton className="mt-2 h-4 w-80 rounded" />}
                  {spec && (
                    <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
                      <Pill icon="sparkle">{spec.config.model}</Pill>
                      <Pill icon="sliders">Esforço {EFFORT_LABEL[spec.config.effort] ?? spec.config.effort}</Pill>
                      <Pill icon="brain">Raciocínio {spec.config.thinking}</Pill>
                      <Pill icon="wrench">{spec.tools.length} ferramentas</Pill>
                      <Pill icon="shield-check">{spec.policies.length} políticas</Pill>
                      {memory?.layer === "editada" && <Pill icon="pen">Memória editada por você</Pill>}
                    </div>
                  )}
                </div>
              </div>
            </GlassPanel>

            {/* Abas */}
            <div ref={tabsRef} role="tablist" aria-label="Seções do agente" onKeyDown={onTabKey} className="no-scrollbar mb-5 flex gap-1 overflow-x-auto rounded-full border border-edge bg-glass p-1 backdrop-blur-xl">
              {TABS.map((t) => {
                const on = t.id === tab;
                return (
                  <button
                    key={t.id}
                    data-tab={t.id}
                    type="button"
                    role="tab"
                    aria-selected={on}
                    tabIndex={on ? 0 : -1}
                    title={t.hint}
                    onClick={() => !on && go({ tab: t.id })}
                    className={cn(
                      "flex shrink-0 items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm transition-colors",
                      on ? "bg-primary font-medium text-fg-inverse" : "text-fg-muted hover:bg-hover hover:text-fg",
                    )}
                  >
                    <Icon name={t.icon} size={14} /> {t.label}
                  </button>
                );
              })}
            </div>

            <div role="tabpanel" aria-label={TABS.find((t) => t.id === tab)?.label} key={`${agent}-${tab}`} className="animate-enter">
              {error ? (
                <EmptyState icon="alert-circle" title="Agente indisponível" action={<Button onClick={() => load(agent)}>Tentar de novo</Button>}>
                  {error}
                </EmptyState>
              ) : !spec || !memory ? (
                <div className="space-y-4">
                  <Skeleton className="h-40 rounded-r4" />
                  <Skeleton className="h-64 rounded-r4" />
                </div>
              ) : tab === "visao" ? (
                <AgentSpec spec={spec} onGo={(t) => go({ tab: t as Tab })} />
              ) : tab === "instrucoes" ? (
                <AgentInstructions agent={agent} examples={spec.examples} onDirty={setDirty} />
              ) : tab === "memoria" ? (
                <AgentMemory agent={agent} memory={memory} onSaved={setMemory} onDirty={setDirty} />
              ) : tab === "contexto" ? (
                <AgentContext agent={agent} memory={memory} onSaved={setMemory} onDirty={setDirty} />
              ) : tab === "codigo" ? (
                <AgentCode agent={agent} name={look.name} files={spec.files} />
              ) : (
                <TestsTab agent={agent} />
              )}
            </div>
          </section>
        </div>
      </div>

      <AppDialog
        open={!!pending}
        onOpenChange={(o) => !o && setPending(null)}
        title="Descartar o que não foi salvo?"
        description="Você mudou algo nesta aba e ainda não salvou. Se sair agora, a alteração se perde."
        actions={
          <>
            <Button variant="ghost" onClick={() => setPending(null)}>
              Continuar editando
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setDirty(false);
                if (pending?.agent) setAgent(pending.agent);
                if (pending?.tab) setTab(pending.tab);
                setPending(null);
              }}
            >
              Descartar
            </Button>
          </>
        }
      />
    </div>
  );
}

function Pill({ icon, children }: { icon: IconName; children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-1.5 rounded-full border border-hairline bg-chip px-2.5 py-1 text-fg-muted">
      <Icon name={icon} size={12} /> {children}
    </span>
  );
}

function TestsTab({ agent }: { agent: string }) {
  if (agent !== "FILE") {
    return (
      <div className="space-y-5">
        <GlassPanel className="p-5">
          <p className="flex items-center gap-2 text-md font-medium text-fg">
            <Icon name="flask" size={16} /> Experimentos medidos
          </p>
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-fg-muted">
            Por enquanto, a comparação com estado final conferido de forma independente existe para o agente de Arquivos, que é declarativo: o mesmo caso
            roda em cada versão numa pasta temporária, passa pela política real e o resultado é checado no disco. Para os outros agentes, crie versões das
            instruções aqui e use o modo Simular da conversa para ver o plano sem executar.
          </p>
        </GlassPanel>
        <Experiments agent={agent} />
      </div>
    );
  }
  return <Experiments agent={agent} />;
}
