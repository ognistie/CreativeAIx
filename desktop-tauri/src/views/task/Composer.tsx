import { useEffect, useRef, useState } from "react";
import { Hint, Icon, IconButton, TogglePill } from "../../components/ui";
import { cn } from "../../lib/cn";
import { useVoice } from "../../lib/stores";
import { core } from "../../lib/tauri";

// Composer.qml: caixa de pedido. Enter envia, Shift+Enter quebra linha. Microfone grava e envia como
// mensagem de audio; "Conversa" deixa o microfone aberto. Simular e Relatorio vao junto do pedido.

export interface ComposerOptions {
  dryRun: boolean;
  report: boolean;
}

export function Composer({
  running,
  compact,
  placeholder = "Descreva uma tarefa...",
  onSubmit,
  autoFocus,
  prefill,
}: {
  running: boolean;
  compact?: boolean;
  placeholder?: string;
  onSubmit: (text: string, opts: ComposerOptions) => void;
  autoFocus?: boolean;
  prefill?: { text: string; at: number } | null;
}) {
  const [text, setText] = useState("");
  const [dryRun, setDryRun] = useState(false);
  const [report, setReport] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const voice = useVoice();
  const recording = voice.state === "recording";
  const canSend = !running && text.trim().length > 0;
  const [recSeconds, setRecSeconds] = useState(0);

  useEffect(() => {
    if (prefill) {
      setText(prefill.text);
      input.current?.focus();
    }
  }, [prefill]);

  useEffect(() => {
    if (!recording) return;
    const t = setInterval(() => setRecSeconds(Math.floor((Date.now() - voice.recStartedAt) / 1000)), 250);
    return () => clearInterval(t);
  }, [recording, voice.recStartedAt]);

  // A caixa cresce com o texto (ate um limite)
  useEffect(() => {
    const el = input.current;
    if (!el) return;
    // Vazio: altura natural de uma linha (medir com a janela ainda oculta da um valor errado)
    if (!text) {
      el.style.height = "";
      return;
    }
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const send = () => {
    if (!canSend) return;
    onSubmit(text.trim(), { dryRun, report });
    setText("");
  };

  return (
    <div
      className={cn(
        "rounded-composer border border-edge bg-glass-hi shadow-[0_8px_30px_var(--shadow-soft)] backdrop-blur-2xl",
        "motion-fast transition-[border-color] focus-within:border-accent/45",
      )}
    >
      {recording ? (
        <div className="flex min-h-[52px] items-center gap-3 px-4" role="status" aria-live="polite">
          <span className="size-2.5 animate-pulse rounded-full bg-bad" />
          <span className="text-md text-fg">Gravando… {recSeconds}s</span>
          <span aria-hidden className="h-1.5 flex-1 overflow-hidden rounded-full bg-chip">
            <span className="block h-full rounded-full bg-accent transition-[width] duration-100" style={{ width: `${Math.min(100, voice.level * 100)}%` }} />
          </span>
          <button type="button" onClick={() => void core().call("voiceRecordCancel")} className="text-sm text-fg-muted hover:text-fg">
            Cancelar
          </button>
        </div>
      ) : (
        <textarea
          ref={input}
          rows={1}
          value={text}
          autoFocus={autoFocus}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={voice.live ? "Conversa ao vivo: pode falar (ou digitar)..." : placeholder}
          aria-label="Pedido"
          className="block w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-md text-fg outline-none placeholder:text-fg-subtle"
        />
      )}
      {voice.error && <p className="px-4 pb-1 text-sm text-bad">{voice.error}</p>}
      <div className="flex items-center gap-1.5 px-2.5 pb-2.5 pt-1">
        {!compact && (
          <>
            <TogglePill checked={dryRun} onCheckedChange={setDryRun} icon="eye" title="Só planeja, sem executar nada">
              Simular
            </TogglePill>
            <TogglePill checked={report} onCheckedChange={setReport} icon="file-text" title="Gera um relatório ao terminar">
              Relatório
            </TogglePill>
          </>
        )}
        <TogglePill
          checked={voice.live}
          onCheckedChange={(on) => void core().call("setLiveConversation", on)}
          icon="messages"
          title="Microfone aberto: cada fala vira um pedido"
        >
          Conversa
        </TogglePill>
        {voice.queued > 0 && <span className="text-xs text-fg-muted">{voice.queued} na fila</span>}
        <span className="flex-1" />
        <Hint text={voice.hotkey ? `Gravar voz (${voice.hotkey})` : "Gravar voz"}>
          <IconButton
            icon="mic"
            label={recording ? "Enviar áudio" : "Gravar voz"}
            flat
            onClick={() => void core().call("voiceRecordToggle")}
            className={cn(recording && "bg-bad/15 text-bad hover:text-bad")}
          />
        </Hint>
        {running ? (
          <IconButton icon="stop" label="Parar (Esc)" onClick={() => void core().call("forceStop")} className="bg-primary text-fg-inverse hover:bg-primary hover:text-fg-inverse" />
        ) : (
          <button
            type="button"
            onClick={send}
            disabled={!canSend}
            aria-label="Enviar pedido"
            className="press motion-fast grid size-[34px] place-items-center rounded-full bg-primary text-fg-inverse transition-opacity disabled:opacity-30"
          >
            <Icon name="arrow-up" size={16} weight={2} />
          </button>
        )}
      </div>
    </div>
  );
}
