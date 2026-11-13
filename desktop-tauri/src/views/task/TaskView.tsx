import { useEffect, useRef, useState } from "react";
import { Button, GlassPanel, Icon, Spinner, StatusDot, type IconName, type Status } from "../../components/ui";
import { agentLabel } from "../../lib/agents";
import { cn } from "../../lib/cn";
import { dispatchTask, useTask } from "../../lib/stores";
import { core } from "../../lib/tauri";
import { phaseIndex, usageLine, type Step, type TaskState, type Turn } from "../../lib/taskStore";
import { Composer, type ComposerOptions } from "./Composer";

// TaskView.qml: sem tarefa, saudacao + caixa + sugestoes. Com tarefa: a conversa, o pedido atual, o plano,
// os passos em tempo real e o resultado (o que foi criado e o custo real).

const SUGGESTIONS: Array<{ icon: IconName; text: string }> = [
  { icon: "chart", text: "Crie uma planilha de gastos do mês com gráfico" },
  { icon: "globe", text: "Pesquise no Google sobre inteligência artificial" },
  { icon: "code", text: "Crie um site sobre uma cafeteria artesanal" },
  { icon: "folder", text: "Organize os arquivos da pasta Downloads por tipo" },
];

export function startTask(text: string, opts: ComposerOptions, heard?: string) {
  dispatchTask({ type: "start", text, heard, dryRun: opts.dryRun, now: Date.now() });
  void core().call("executeTask", text, opts.dryRun, opts.report);
}

export function TaskView() {
  const s = useTask();
  const [prefill, setPrefill] = useState<{ text: string; at: number } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const idle = s.status === "idle";
  const hasConversation = s.turns.length > 0;

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [s.turns.length, s.steps.length, s.plan.length, s.status, s.assistantText, s.review]);

  if (idle && !hasConversation) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 pb-16">
        <div className="animate-enter w-full max-w-[var(--content-max)]">
          <h1 className="text-center font-display text-hero font-medium tracking-[-0.03em] text-fg">Como posso ajudar?</h1>
          <p className="mx-auto mb-7 mt-2 max-w-md text-center text-md text-fg-muted">
            Digite ou fale um pedido. O Maestro escolhe o agente certo e executa no seu computador.
          </p>
          <Composer running={false} onSubmit={(t, o) => startTask(t, o)} autoFocus prefill={prefill} />
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((x) => (
              <button
                key={x.text}
                type="button"
                onClick={() => setPrefill({ text: x.text, at: Date.now() })}
                className="press motion-fast inline-flex items-center gap-2 rounded-full bg-chip px-3.5 py-1.5 text-[13px] text-fg-muted transition-colors hover:bg-row-hover hover:text-fg"
              >
                <Icon name={x.icon} size={13} />
                {x.text}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-6">
        <div className="mx-auto flex max-w-[var(--content-max)] flex-col gap-5 py-8">
          {s.turns.map((t, i) => (
            <TurnView key={i} turn={t} />
          ))}
          {!idle && <Current s={s} />}
          <div ref={bottom} />
        </div>
      </div>
      <div className="px-6 pb-5">
        <div className="mx-auto max-w-[var(--content-max)]">
          <Composer
            running={s.busy}
            placeholder={s.status === "clarify" ? "Responda à pergunta..." : "Peça mais alguma coisa..."}
            onSubmit={(t, o) => startTask(t, o)}
            autoFocus
          />
        </div>
      </div>
    </div>
  );
}

function UserBubble({ text, sub }: { text: string; sub?: string }) {
  return (
    <div className="ml-auto max-w-[85%]">
      <p className="rounded-r4 rounded-br-r1 bg-surface-hi px-4 py-2.5 text-md text-fg">{text}</p>
      {sub && <p className="mt-1 text-right text-xs text-fg-subtle">{sub}</p>}
    </div>
  );
}

const TURN_STATUS: Record<string, Status> = { done: "ok", failed: "failed", cancelled: "cancelled", clarify: "clarify", limited: "limited" };

function TurnView({ turn }: { turn: Turn }) {
  return (
    <div className="flex flex-col gap-2">
      <UserBubble text={turn.said} sub={turn.resolved ? `Entendi: ${turn.resolved}` : undefined} />
      {turn.summary && (
        <div className="flex max-w-[85%] items-start gap-2.5">
          <span className="mt-0.5">
            <StatusDot status={TURN_STATUS[turn.status] ?? "ok"} size={14} />
          </span>
          <p className="text-md text-fg-muted">{turn.summary}</p>
        </div>
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
      <PhaseStepper index={phaseIndex(s)} busy={s.busy} msg={s.phaseMsg} dryRun={s.dryRun} />
      {s.review && <ReviewCard review={s.review} />}
      {s.plan.length > 0 && s.steps.length === 0 && <PlanCard plan={s.plan} />}
      {s.steps.length > 0 && <StepList steps={s.steps} />}
      {s.replies.map((r, i) => (
        <p key={i} className="max-w-[85%] text-md text-fg">
          {r}
        </p>
      ))}
      <Outcome s={s} />
      <p className="text-xs tabular-nums text-fg-subtle">{usageLine(s, ms)}</p>
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
    <GlassPanel className="animate-enter p-4" raised={false}>
      <p className="mb-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">Plano do Maestro</p>
      <ol className="space-y-1.5">
        {plan.map((p, i) => (
          <li key={i} className="flex gap-2.5 text-md">
            <span className="w-5 shrink-0 text-right tabular-nums text-fg-subtle">{i + 1}.</span>
            <span className="text-fg">
              {p.agent && <span className="mr-1.5 text-xs font-medium text-accent">{agentLabel(p.agent)}</span>}
              {p.text}
            </span>
          </li>
        ))}
      </ol>
    </GlassPanel>
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
              {st.agent && <span className="mr-1.5 text-xs font-medium text-accent">{agentLabel(st.agent)}</span>}
              {st.desc}
            </p>
            {st.result && st.state !== "running" && (
              <p className={cn("mt-0.5 line-clamp-3 break-words text-sm", st.state === "fail" ? "text-bad" : "text-fg-subtle")}>{st.result}</p>
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
        <Icon name="alert-triangle" size={15} className="text-warn" />
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
        <p className="flex items-center gap-2 text-md font-medium text-bad">
          <Icon name="alert-circle" size={15} /> Não deu certo
        </p>
        <p className="mt-1 text-md text-fg">{s.errorMsg}</p>
      </div>
    );
  }
  if (s.status === "cancelled") return <p className="text-md text-fg-muted">Execução interrompida.</p>;
  const answer = s.assistantText || s.reportSummary;
  const files = s.artifacts.files;
  if (s.status !== "done" && !answer) return null;
  return (
    <div className="flex flex-col gap-2.5">
      {answer && <p className="max-w-[85%] text-md text-fg">{answer}</p>}
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
