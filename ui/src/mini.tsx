import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Button, Icon, IconButton, Spinner, StatusDot } from "./components/ui";
import { agentLabel } from "./lib/agents";
import { applyAppearance, type Appearance } from "./lib/appearance";
import { cn } from "./lib/cn";
import { taskStore, useTask, useVoice, wireTaskEvents, wireVoiceEvents } from "./lib/stores";
import { core, demoMode, inApp } from "./lib/host";
import { closeMini, restoreMain, submitFromMini, wireMiniWindow } from "./lib/windowing";
import { useCoreStatus } from "./lib/useCore";
import { startTask } from "./views/task/TaskView";
import "./styles/index.css";

// MiniChat, redesenhado: o mesmo papel (a conversa continua no canto enquanto o agente usa outro
// app) e o mesmo cuidado (durante a tarefa nao pega foco nem cliques; parar e pelo atalho global).

wireVoiceEvents();
if (inApp) wireMiniWindow((s) => taskStore.set(s));
else if (demoMode) wireTaskEvents();

function Mini() {
  const s = useTask();
  const voice = useVoice();
  const status = useCoreStatus();
  const [text, setText] = useState("");
  const [stopLabel, setStopLabel] = useState("Ctrl+Alt+X");
  const recording = voice.state === "recording";
  const lastTurn = s.turns.at(-1);
  const current = s.steps.filter((x) => x.kind === "step");
  const running = current.find((x) => x.state === "running");
  const done = current.filter((x) => x.state === "ok").length;

  useEffect(() => {
    if (status !== "open") return;
    core().call("appearance").then((a) => applyAppearance(a as Appearance)).catch(() => {});
    core()
      .call("uiSettings")
      .then((u) => setStopLabel((u as { stop_hotkey_label?: string }).stop_hotkey_label || "Ctrl+Alt+X"))
      .catch(() => {});
  }, [status]);

  const send = () => {
    const t = text.trim();
    if (!t || s.busy) return;
    if (inApp) submitFromMini(t);
    else startTask(t, { dryRun: false, report: false });
    setText("");
  };

  return (
    <div className="flex h-full flex-col justify-end p-2">
      <div className="animate-enter flex max-h-full flex-col overflow-hidden rounded-r4 border border-edge bg-glass-hi shadow-[0_18px_48px_var(--shadow)] backdrop-blur-2xl">
        <header className="flex items-center gap-2 border-b border-hairline py-1.5 pl-3 pr-1.5">
          <Orb busy={s.busy} status={s.status} />
          <span className="flex-1 truncate text-[13px] font-medium text-fg">
            {s.busy ? s.phaseMsg || "Trabalhando" : s.status === "idle" ? "Creative AIx" : statusLabel(s.status)}
          </span>
          {(!s.busy || s.review) && (
            <IconButton icon="external" label="Abrir a janela completa" flat className="size-7" onClick={restoreMain} />
          )}
          {!s.busy && <IconButton icon="x" label="Fechar o mini chat" flat className="size-7" onClick={closeMini} />}
        </header>

        <div className="flex min-h-0 flex-col gap-2 overflow-y-auto px-3 py-2.5 text-[13px]">
          {s.task ? (
            <>
              <p className="ml-auto max-w-[90%] rounded-r3 rounded-br-r1 bg-surface-hi px-3 py-1.5 text-fg">{s.task}</p>
              {current.length > 0 && (
                <div className="flex items-start gap-2 text-fg-muted">
                  {running ? <Spinner size={12} /> : <StatusDot status={s.status === "failed" ? "failed" : "ok"} size={13} />}
                  <span className="min-w-0 flex-1">
                    {running ? (
                      <>
                        {running.agent && <span className="mr-1 text-xs font-medium text-accent-ink">{agentLabel(running.agent)}</span>}
                        {running.desc}
                      </>
                    ) : (
                      `${done} de ${s.plan.length || current.length} passos`
                    )}
                  </span>
                </div>
              )}
              {(s.assistantText || s.question || s.errorMsg) && (
                <p className={cn("text-fg", s.errorMsg && "text-bad-ink")}>{s.assistantText || s.question || s.errorMsg}</p>
              )}
              {s.replies.at(-1) && <p className="text-fg">{s.replies.at(-1)}</p>}
              {s.review && <MiniReview review={s.review} />}
            </>
          ) : lastTurn ? (
            <p className="text-fg-muted">{lastTurn.summary || lastTurn.said}</p>
          ) : (
            <p className="text-fg-muted">Peça algo daqui, sem abrir a janela completa.</p>
          )}
        </div>

        {s.busy ? (
          <footer className="flex items-center gap-2 border-t border-hairline px-3 py-2 text-xs text-fg-muted">
            <Icon name="stop" size={12} />
            Para parar, aperte <kbd className="font-medium text-fg">{stopLabel}</kbd>
          </footer>
        ) : (
          <footer className="flex items-center gap-1.5 border-t border-hairline p-1.5 pl-3">
            <input
              value={text}
              autoFocus
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder={recording ? "Gravando…" : "Peça algo…"}
              aria-label="Pedido"
              className="min-w-0 flex-1 bg-transparent text-[13px] text-fg outline-none placeholder:text-fg-subtle"
            />
            <IconButton
              icon="mic"
              label={recording ? "Enviar áudio" : "Gravar voz"}
              flat
              className={cn("size-8", recording && "bg-bad/15 text-bad-ink")}
              onClick={() => void core().call("voiceRecordToggle")}
            />
            <button
              type="button"
              onClick={send}
              disabled={!text.trim()}
              aria-label="Enviar pedido"
              className="press grid size-8 place-items-center rounded-full bg-primary text-fg-inverse disabled:opacity-30"
            >
              <Icon name="arrow-up" size={14} weight={2} />
            </button>
          </footer>
        )}
      </div>
    </div>
  );
}

/** Confirmacao no proprio mini chat: antes a tarefa esperava 3 min por um botao que so existia na janela
 *  completa (minimizada) e terminava como "nao autorizada". */
function MiniReview({ review }: { review: NonNullable<ReturnType<typeof useTask>["review"]> }) {
  const [sent, setSent] = useState(false);
  const decide = (ok: boolean) => {
    setSent(true);
    void core().call("approvePlan", ok, review.token);
  };
  useEffect(() => setSent(false), [review.token]);
  return (
    <div role="alertdialog" aria-label={review.effect ? "Confirme antes de continuar" : "Revise o plano"}
      className="rounded-r3 border border-warn/40 bg-warn/10 p-2.5">
      <p className="mb-1 flex items-center gap-1.5 font-medium text-fg">
        <Icon name="alert-triangle" size={13} className="text-warn-ink" />
        {review.effect ? "Confirme antes de continuar" : "Revise o plano"}
      </p>
      <ul className="mb-2 list-disc space-y-0.5 pl-4 text-fg">
        {review.steps.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
      <div className="flex justify-end gap-1.5">
        <Button variant="ghost" size="compact" disabled={sent} onClick={() => decide(false)}>
          Cancelar
        </Button>
        <Button variant="primary" size="compact" icon="check" disabled={sent} onClick={() => decide(true)}>
          {review.effect ? "Confirmar" : "Aprovar"}
        </Button>
      </div>
    </div>
  );
}

function statusLabel(s: string): string {
  return { done: "Concluído", failed: "Não deu certo", cancelled: "Interrompido", clarify: "Preciso de uma resposta", limited: "Não posso fazer assim" }[s] ?? "";
}

/** TaskOrb, simplificado: a orbe respira enquanto o agente trabalha. */
function Orb({ busy, status }: { busy: boolean; status: string }) {
  const tone = busy ? "bg-accent" : status === "failed" ? "bg-bad" : status === "done" ? "bg-ok" : "bg-fg-subtle";
  return (
    <span className="relative grid size-5 place-items-center" aria-hidden>
      {busy && <span className="absolute inset-0 animate-ping rounded-full bg-accent/40" />}
      <span className={cn("size-2.5 rounded-full", tone)} />
    </span>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Mini />
  </StrictMode>,
);
