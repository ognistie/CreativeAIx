import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Button, GlassPanel, Icon, Spinner, StatusDot, type IconName, type Status } from "../../components/ui";
import { agentLabel } from "../../lib/agents";
import { cn } from "../../lib/cn";
import { dispatchTask, useTask } from "../../lib/stores";
import { core, openExternal } from "../../lib/host";

// Markdown (react-markdown + remark-gfm, ~170 KB) carrega sob demanda: a abertura do app nao paga por ele
const Prose = lazy(() => import("../../components/Prose").then((m) => ({ default: m.Prose })));
import { phaseIndex, usageLine, type Step, type TaskState, type Turn } from "../../lib/taskStore";
import { ICONS } from "../../lib/icons.gen";
import { Composer, type ComposerOptions } from "./Composer";

// Panorama do harness ao vivo (Lab): carrega so quando aberto, fora do pacote principal da conversa
const LivePanorama = lazy(() => import("../lab/HarnessPanorama").then((m) => ({ default: m.LivePanorama })));
const PANORAMA_KEY = "creative-aix.live-panorama";

/** A conversa com o panorama do harness ao lado (abre e fecha pelo botao; a escolha fica salva). */
function WithPanorama({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem(PANORAMA_KEY) === "1"; } catch { return false; }
  });
  const toggle = () => setOpen((v) => {
    try { localStorage.setItem(PANORAMA_KEY, v ? "0" : "1"); } catch { /* sem armazenamento: so nesta sessao */ }
    return !v;
  });
  return (
    <div className="task-split">
      <div className="task-split-main">
        <button type="button" className="task-panorama-toggle" aria-pressed={open} onClick={toggle}
          title={open ? "Fechar o panorama do harness" : "Ver o harness trabalhando ao vivo"}>
          <Icon name="layers" size={14} /> <span>Panorama</span>
        </button>
        {children}
      </div>
      {open && (
        <aside className="task-split-aside" aria-label="Panorama do harness ao vivo">
          <Suspense fallback={<div className="h-full w-full animate-pulse rounded-[14px] bg-chip" />}>
            <LivePanorama />
          </Suspense>
        </aside>
      )}
    </div>
  );
}

// TaskView: sem tarefa, saudacao + caixa + sugestoes. Com tarefa: a conversa, o pedido atual, o plano,
// os passos em tempo real e o resultado (o que foi criado e o custo real).

const SUGGESTIONS: Array<{ icon: IconName; text: string }> = [
  { icon: "chart", text: "Crie uma planilha de gastos do mês com gráfico" },
  { icon: "globe", text: "Pesquise no Google sobre inteligência artificial" },
  { icon: "code", text: "Crie um site sobre uma cafeteria artesanal" },
  { icon: "folder", text: "Organize os arquivos da pasta Downloads por tipo" },
];

export function startTask(raw: string, opts: ComposerOptions, heard?: string) {
  const text = raw.trim();
  dispatchTask({ type: "start", text, heard, dryRun: opts.dryRun, now: Date.now() });
  void core().call("executeTask", text, opts.dryRun, opts.report);
}

interface DevMode {
  enabled: boolean;
  greeting: string;
  hint: string;
  shortcuts: unknown[];
  cards: unknown[];
}

type Shortcut = { label?: string; request?: string; icon?: string };
type Card = { title?: string; text?: string; icon?: string; request?: string };

const iconOr = (name: unknown, fallback: IconName): IconName => (typeof name === "string" && name in ICONS ? (name as IconName) : fallback);

export function TaskView({ dev }: { dev?: DevMode } = {}) {
  const s = useTask();
  const [prefill, setPrefill] = useState<{ text: string; at: number } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const idle = s.status === "idle";
  const hasConversation = s.turns.length > 0;

  // Acompanha a resposta enquanto ela e escrita (streamText cresce a cada trecho)
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end", behavior: s.streamText ? "auto" : "smooth" });
  }, [s.turns.length, s.steps.length, s.plan.length, s.status, s.assistantText, s.reportSummary, s.streamText, s.review]);

  if (idle && !hasConversation) {
    const devOn = !!dev?.enabled;
    const shortcuts = devOn ? ((dev?.shortcuts ?? []) as Shortcut[]).filter((x) => x.request) : [];
    const cards = devOn ? ((dev?.cards ?? []) as Card[]).filter((x) => x.request) : [];
    return (
      <WithPanorama>
      <div className="chat-font h-full overflow-y-auto px-6">
        {/* Centralizado, um pouco abaixo do meio: o olho cai na caixa de pedido, nao no topo da janela */}
        <div className="chat-landing mx-auto flex min-h-full w-full flex-col justify-center">
          <div className="chat-intro photo-ink mx-auto text-center" data-wallpaper-safe>
            <h1 className="text-fg">{(devOn && dev?.greeting) || "Você é o criador, eu apenas executo."}</h1>
            <p className="photo-ink-muted mx-auto mt-2.5 max-w-lg text-[15px] text-fg-muted">
              {(devOn && dev?.hint) || "Pergunte qualquer coisa, peça para eu ler uma pasta ou descreva uma tarefa."}
            </p>
          </div>
          <div>
            <Composer home running={false} onSubmit={(t, o) => startTask(t, o)} autoFocus prefill={prefill} placeholder="Escreva um pedido ou digite / para selecionar um agente" />
          </div>
          <div className="chat-examples mt-5 flex flex-wrap justify-center gap-2">
            {[
              ...shortcuts.map((x) => ({ icon: iconOr(x.icon, "sparkle"), text: x.label || x.request!, request: x.request! })),
              ...SUGGESTIONS.map((x) => ({ icon: x.icon, text: x.text, request: x.text })),
            ].map((x) => (
              <button
                key={x.text}
                type="button"
                onClick={() => setPrefill({ text: x.request, at: Date.now() })}
                className="press motion-fast inline-flex min-h-8 items-center gap-2 rounded-full px-3.5 text-[13px] text-fg transition-[background-color,transform] hover:-translate-y-px hover:bg-glass-hi"
              >
                <Icon name={x.icon} size={14} className="text-fg-muted" />
                {x.text}
              </button>
            ))}
          </div>
          {cards.length > 0 && (
          <div className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              ...cards.map((c) => ({ icon: iconOr(c.icon, "sparkle"), title: c.title || "", text: c.text || "", run: () => startTask(c.request!, { dryRun: false, report: false }) })),
            ].map((f, i) => (
              <button
                key={`${f.title}-${i}`}
                type="button"
                onClick={f.run}
                style={{ animationDelay: `calc(200ms + var(--stagger) * ${i})` }}
                className="animate-enter press motion-normal group rounded-r3 border border-edge bg-glass-hi p-4 text-left transition-[background-color,border-color,transform,box-shadow] hover:-translate-y-0.5 hover:border-hairline-hi hover:shadow-[0_12px_30px_var(--shadow-soft)]"
              >
                <Icon name={f.icon} size={18} className="text-accent-ink" />
                <span className="mt-3 block text-[15px] font-medium text-fg">{f.title}</span>
                <span className="mt-1 block text-[13px] leading-snug text-fg-muted">{f.text}</span>
              </button>
            ))}
          </div>
          )}
        </div>
      </div>
      </WithPanorama>
    );
  }

  return (
    <WithPanorama>
    <div className="chat-font flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-6">
        <div className="mx-auto flex max-w-[760px] flex-col gap-7 pb-10 pt-14">
          {s.turns.map((t, i) => (
            <TurnView key={i} turn={t} />
          ))}
          {!idle && <Current s={s} />}
          <div ref={bottom} />
        </div>
      </div>
      <div className="relative px-6 pb-5 pt-2">
        <div className="mx-auto max-w-[760px]">
          <Composer
            running={s.busy}
            placeholder={s.status === "clarify" ? "Responda à pergunta..." : "Peça mais alguma coisa..."}
            onSubmit={(t, o) => startTask(t, o)}
            autoFocus
          />
        </div>
      </div>
    </div>
    </WithPanorama>
  );
}

function UserBubble({ text, sub }: { text: string; sub?: string }) {
  return (
    <div className="ml-auto flex max-w-[80%] flex-col items-end">
      <p className="surface-strong select-text whitespace-pre-wrap rounded-[18px] rounded-br-md px-4 py-2.5 text-[14.5px] leading-relaxed text-fg">{text}</p>
      {sub && <p className="photo-ink-muted mt-1.5 max-w-full truncate px-1 text-right text-[12px] text-fg-muted" title={sub}>{sub}</p>}
    </div>
  );
}

const TURN_STATUS: Record<string, Status> = { done: "ok", failed: "failed", cancelled: "cancelled", clarify: "clarify", limited: "limited" };

/** Resposta do assistente: marca a esquerda e o conteudo num painel do mesmo material (le sobre qualquer foto). */
function Assistant({ children, status }: { children: React.ReactNode; status?: Status }) {
  return (
    <div className="flex items-start gap-3">
      <span className="surface mt-0.5 grid size-7 shrink-0 place-items-center rounded-full">
        {status ? <StatusDot status={status} size={13} /> : <BrandDot />}
      </span>
      <div className="surface min-w-0 flex-1 select-text rounded-[16px] px-4 py-3 text-[14.5px] leading-relaxed text-fg">{children}</div>
    </div>
  );
}

function BrandDot() {
  return (
    <svg width={13} height={13} viewBox="0 0 24 24" aria-hidden className="text-fg">
      {[0, 1, 2, 3].map((i) => (
        <rect key={i} x={2 + (i % 2) * 11} y={2 + Math.floor(i / 2) * 11} width={9} height={9} rx={2.6} fill={i === 3 ? "var(--accent)" : "currentColor"} />
      ))}
    </svg>
  );
}

/** Resposta do assistente em Markdown (listas, codigo, tabelas); links abrem fora pelo host. */
function Answer({ markdown }: { markdown: string }) {
  return (
    <Suspense fallback={<p className="select-text whitespace-pre-wrap">{markdown}</p>}>
      <Prose markdown={markdown} className="prose-chat" onLink={(href) => void openExternal(href)} />
    </Suspense>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  return (
    <div className="flex flex-col gap-3">
      <UserBubble text={turn.said} sub={turn.resolved ? `Entendi: ${turn.resolved}` : undefined} />
      {turn.summary && (
        <Assistant status={TURN_STATUS[turn.status] ?? "ok"}>
          <Answer markdown={turn.summary} />
        </Assistant>
      )}
    </div>
  );
}

function Current({ s }: { s: TaskState }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!s.busy) return;
    const t = setInterval(() => setElapsed(Date.now() - s.startedAt), 250);
    return () => clearInterval(t);
  }, [s.busy, s.startedAt]);
  const ms = s.busy ? elapsed : (s.finishedMs ?? elapsed);

  return (
    <div className="flex flex-col gap-3">
      <UserBubble
        text={s.task}
        sub={[s.heardText && `Ouvi: “${s.heardText}”`, s.resolvedText && `Entendi: ${s.resolvedText}`].filter(Boolean).join(" · ") || undefined}
      />
      <Assistant>
        <div className="flex flex-col gap-3">
          <PhaseStepper index={phaseIndex(s)} busy={s.busy} msg={s.phaseMsg} dryRun={s.dryRun} />
          {s.review && <ReviewCard review={s.review} />}
          {s.plan.length > 0 && s.steps.length === 0 && <PlanCard plan={s.plan} />}
          {s.steps.length > 0 && <StepList steps={s.steps} />}
          {s.replies.map((r, i) => (
            <p key={i} className="whitespace-pre-wrap text-fg">
              {r}
            </p>
          ))}
          <Outcome s={s} />
          <p className="border-t border-hairline pt-2 text-[12px] tabular-nums text-fg-muted">{usageLine(s, ms)}</p>
        </div>
      </Assistant>
    </div>
  );
}

const PHASES = ["Entender", "Planejar", "Executar", "Concluir"];

function PhaseStepper({ index, busy, msg, dryRun }: { index: number; busy: boolean; msg: string; dryRun: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5" aria-label="Etapas">
      <ol className="flex items-center gap-1.5">
        {PHASES.map((p, i) => (
          <li key={p} className="flex items-center gap-1.5">
            <span
              className={cn(
                "motion-normal h-1.5 rounded-full transition-all",
                i < index ? "w-6 bg-accent" : i === index && busy ? "w-10 animate-pulse bg-accent" : "w-6 bg-chip",
              )}
              title={p}
            />
          </li>
        ))}
      </ol>
      <span className="text-sm text-fg-muted" aria-live="polite">
        {busy ? msg : index >= 4 ? "Concluído" : msg}
        {dryRun && " · simulação"}
      </span>
      {busy && <Spinner size={12} />}
    </div>
  );
}

function PlanCard({ plan }: { plan: TaskState["plan"] }) {
  return (
    <div className="animate-enter rounded-r3 border border-hairline bg-chip p-3.5">
      <p className="mb-2 text-[12px] font-medium text-fg-muted">Plano do Maestro</p>
      <ol className="space-y-1.5">
        {plan.map((p, i) => (
          <li key={i} className="flex gap-2.5 text-md">
            <span className="w-5 shrink-0 text-right tabular-nums text-fg-subtle">{i + 1}.</span>
            <span className="text-fg">
              {p.agent && <span className="mr-1.5 text-xs font-medium text-accent-ink">{agentLabel(p.agent)}</span>}
              {p.text}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

const STEP_ICON: Record<Step["state"], Status | null> = { running: null, ok: "ok", fail: "failed", warn: "warn" };

function StepList({ steps }: { steps: Step[] }) {
  return (
    <ol className="flex flex-col gap-1">
      {steps.map((st, i) => (
        <li key={i} className="animate-enter flex items-start gap-3 rounded-r2 px-2 py-1.5">
          <span className="mt-0.5 grid w-[15px] place-items-center">
            {st.state === "running" ? <Spinner size={13} /> : <StatusDot status={STEP_ICON[st.state] ?? "ok"} size={15} />}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-md text-fg">
              {st.agent && <span className="mr-1.5 text-xs font-medium text-accent-ink">{agentLabel(st.agent)}</span>}
              {st.desc}
            </p>
            {st.result && st.state !== "running" && (
              <p className={cn("mt-0.5 line-clamp-3 break-words text-sm", st.state === "fail" ? "text-bad-ink" : "text-fg-subtle")}>{st.result}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

function ReviewCard({ review }: { review: NonNullable<TaskState["review"]> }) {
  const decide = (ok: boolean) => {
    dispatchTask({ type: "reviewDecided" });
    void core().call("approvePlan", ok, review.token);
  };
  return (
    <GlassPanel className="animate-enter border-warn/40 p-4">
      <p className="mb-1 flex items-center gap-2 text-md font-semibold text-fg">
        <Icon name="alert-triangle" size={15} className="text-warn-ink" />
        {review.effect ? "Confirme antes de continuar" : "Revise o plano"}
      </p>
      {review.summary && <p className="mb-2 text-md text-fg-muted">{review.summary}</p>}
      <ul className="mb-4 list-disc space-y-1 pl-5 text-md text-fg">
        {review.steps.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={() => decide(false)}>
          Cancelar
        </Button>
        <Button variant="primary" icon="check" onClick={() => decide(true)}>
          Aprovar e executar
        </Button>
      </div>
    </GlassPanel>
  );
}

function Outcome({ s }: { s: TaskState }) {
  if (s.status === "clarify" || s.status === "limited") {
    return (
      <div className="flex max-w-[85%] items-start gap-2.5">
        <StatusDot status={s.status} />
        <p className="text-md text-fg">{s.question}</p>
      </div>
    );
  }
  if (s.status === "failed") {
    return (
      <div className="rounded-r3 border border-bad/30 bg-bad/10 p-3.5">
        <p className="flex items-center gap-2 text-md font-medium text-bad-ink">
          <Icon name="alert-circle" size={15} /> Não deu certo
        </p>
        <p className="mt-1 text-md text-fg">{s.errorMsg}</p>
      </div>
    );
  }
  if (s.status === "cancelled") return <p className="text-md text-fg-muted">Execução interrompida.</p>;
  const answer = s.assistantText || s.reportSummary || s.streamText;
  const files = s.artifacts.files;
  if (s.status !== "done" && !answer) return null;
  return (
    <div className="flex flex-col gap-2.5">
      {answer && <Answer markdown={answer} />}
      {(files.length > 0 || s.artifacts.url) && (
        <div className="flex flex-wrap gap-2">
          {files.slice(0, 6).map((f) => (
            <span key={f} className="inline-flex items-center gap-1.5 rounded-full bg-chip px-3 py-1 text-[13px] text-fg" title={s.artifacts.folder ? `${s.artifacts.folder}\\${f}` : f}>
              <Icon name="file" size={13} /> {f}
            </span>
          ))}
          {s.artifacts.url && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-chip px-3 py-1 text-[13px] text-fg">
              <Icon name="link" size={13} /> {s.artifacts.url}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
