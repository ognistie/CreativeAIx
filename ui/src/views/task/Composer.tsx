import { useEffect, useMemo, useRef, useState } from "react";
import { Hint, Icon, IconButton, TogglePill } from "../../components/ui";
import { cn } from "../../lib/cn";
import { useVoice } from "../../lib/stores";
import { core, inApp, pickFiles, pickFolder } from "../../lib/host";
import { parseSlash, SLASH_COMMANDS, slashMatches, toolName, withTool, type SlashTool } from "../../lib/slash";

// Caixa de pedido. Enter envia, Shift+Enter quebra linha. Microfone grava e envia como mensagem de audio;
// "Conversa" deixa o microfone aberto. Simular e Relatorio vao junto do pedido.
//
// "/claude" e "/codex" chamam o Claude Code ou o Codex so para este pedido. Com a ferramenta escolhida, a
// bandeja de cima pede a pasta do projeto; sem ela, a bandeja de baixo mostra as ferramentas disponiveis.
// As bandejas deslizam por tras da caixa (referencia: o composer que troca a faixa de baixo pela de cima).

// Modo de aprovacao de efeitos sensiveis (config.yaml > execution.authorization), lido uma vez.
// So leitura de proposito: desligar a porta de aprovacao nao pode ser um clique na tela de conversa.
type AuthMode = "enforce" | "shadow" | "off";
let authOnce: Promise<AuthMode> | null = null;
const loadAuth = () =>
  (authOnce ??= core()
    .call("getSettings")
    .then((r) => ((r as { authorization?: AuthMode }).authorization ?? "enforce"))
    .catch(() => "enforce" as AuthMode));

const AUTH: Record<AuthMode, { icon: "hand" | "shield" | "eye"; label: string; hint: string; tone: string }> = {
  enforce: {
    icon: "hand",
    label: "Pede aprovação",
    hint: "Enviar, comprar, pagar, excluir ou publicar só acontece depois que você confirmar.",
    tone: "text-fg-muted hover:bg-hover hover:text-fg",
  },
  shadow: {
    icon: "eye",
    label: "Só registra efeitos",
    hint: "Modo de observação: efeitos sensíveis não pedem aprovação, só ficam registrados. Ajuste em config.yaml.",
    tone: "bg-warn/15 text-warn-ink",
  },
  off: {
    icon: "shield",
    label: "Acesso irrestrito",
    hint: "A porta de aprovação está desligada: o agente pode enviar, pagar ou excluir sem perguntar. Ajuste em config.yaml.",
    tone: "bg-bad/12 text-bad-ink",
  },
};

export interface ComposerOptions {
  dryRun: boolean;
  report: boolean;
}

const baseName = (p: string) => p.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || p;

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
  const [tool, setTool] = useState<SlashTool | null>(null);
  const [folder, setFolder] = useState("");
  const [menuIndex, setMenuIndex] = useState(0);
  const input = useRef<HTMLTextAreaElement>(null);
  const voice = useVoice();
  const recording = voice.state === "recording";
  const canSend = !running && text.trim().length > 0;
  const [recSeconds, setRecSeconds] = useState(0);
  const [attachments, setAttachments] = useState<string[]>([]);
  const [auth, setAuth] = useState<AuthMode | null>(null);
  const matches = useMemo(() => (tool ? [] : slashMatches(text)), [text, tool]);
  const menuOpen = matches.length > 0;

  useEffect(() => {
    if (!compact) void loadAuth().then(setAuth);
  }, [compact]);
  useEffect(() => setMenuIndex(0), [matches.length]);

  const addFiles = (paths: string[]) => {
    setAttachments((cur) => [...cur, ...paths.filter((p) => p && !cur.includes(p))].slice(-6));
    input.current?.focus();
  };

  useEffect(() => {
    if (prefill) {
      onText(prefill.text);
      input.current?.focus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    if (!text) {
      el.style.height = "";
      return;
    }
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  /** Texto digitado: "/codex " no inicio vira a ficha da ferramenta e sai do texto. */
  function onText(value: string) {
    const parsed = compact ? null : parseSlash(value);
    if (parsed && /\s/.test(value.slice(parsed.tool.length + 1, parsed.tool.length + 2))) {
      setTool(parsed.tool);
      setText(parsed.rest);
      return;
    }
    setText(value);
  }

  const chooseTool = (t: SlashTool) => {
    setTool(t);
    setText((cur) => (slashMatches(cur).length ? "" : cur));
    requestAnimationFrame(() => input.current?.focus());
  };

  const clearTool = () => {
    setTool(null);
    setFolder("");
    input.current?.focus();
  };

  const askFolder = async () => {
    const picked = await pickFolder().catch(() => "");
    if (picked) setFolder(picked);
    input.current?.focus();
  };

  const send = async () => {
    if (!canSend) return;
    let t = withTool(text, tool, folder);
    if (attachments.length) {
      // Os anexos ficam na conversa (o assistente pode ler) e o pedido cita o caminho para os agentes
      try {
        const ok = (await core().call("attachFiles", JSON.stringify(attachments))) as string[];
        if (ok.length) t += ["", "", "Arquivos anexados:", ...ok.map((x) => `- ${x}`)].join("\n");
      } catch {
        /* sem anexos: o pedido segue so com o texto */
      }
      setAttachments([]);
    }
    onSubmit(t, { dryRun, report });
    setText("");
    // A ferramenta vale so para este pedido; a pasta fica, porque o proximo pedido costuma ser no mesmo projeto
    setTool(null);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (menuOpen) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setMenuIndex((i) => (i + (e.key === "ArrowDown" ? 1 : matches.length - 1)) % matches.length);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        const pick = matches[menuIndex] ?? matches[0];
        if (pick) chooseTool(pick.tool);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setText("");
        return;
      }
    }
    if (e.key === "Backspace" && tool && !text && e.currentTarget.selectionStart === 0) {
      e.preventDefault();
      clearTool();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send();
    }
  };

  const a = auth ? AUTH[auth] : null;
  const full = !compact;

  // @container: os rotulos encolhem pela largura da propria caixa (com a barra lateral aberta a janela engana)
  return (
    <div className="@container relative">
      {/* Bandeja de cima: pasta do projeto (so com /claude ou /codex) */}
      {full && (
        <div className="tray" data-open={!!tool} aria-hidden={!tool}>
          <div className="tray-inner">
            <div className="composer-tray -mb-5 flex h-[54px] items-start gap-2 rounded-t-composer px-4 pt-2.5 text-[13px]">
              <button
                type="button"
                tabIndex={tool ? 0 : -1}
                onClick={() => void askFolder()}
                className="press motion-fast flex min-w-0 items-center gap-2 rounded-full px-1.5 py-0.5 text-fg-muted transition-colors hover:text-fg"
              >
                <Icon name="folder" size={15} className="shrink-0 text-accent-ink" />
                <span className="truncate">{folder ? baseName(folder) : "Selecionar projeto"}</span>
              </button>
              {folder ? (
                <span className="hidden min-w-0 truncate text-xs leading-6 text-fg-subtle @lg:block" title={folder}>
                  {folder}
                </span>
              ) : (
                <span className="hidden truncate text-xs leading-6 text-fg-subtle @lg:block">ou use o projeto desta conversa</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Menu dos comandos com barra */}
      {menuOpen && (
        <ul role="listbox" aria-label="Comandos" className="animate-pop absolute inset-x-3 bottom-[calc(100%+8px)] z-30 rounded-r3 border border-hairline-hi bg-surface p-1.5 shadow-[0_18px_40px_var(--shadow)]">
          {matches.map((c, i) => (
            <li key={c.tool} role="option" aria-selected={i === menuIndex}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setMenuIndex(i)}
                onClick={() => chooseTool(c.tool)}
                className={cn("motion-fast flex w-full items-center gap-3 rounded-r2 px-3 py-2 text-left transition-colors", i === menuIndex ? "bg-row-hover" : "hover:bg-hover")}
              >
                <span className="grid size-8 place-items-center rounded-r2 bg-chip text-accent-ink">
                  <Icon name={c.icon} size={15} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-md font-medium text-fg">
                    {c.command} <span className="font-normal text-fg-muted">· {c.name}</span>
                  </span>
                  <span className="block truncate text-xs text-fg-muted">{c.hint}</span>
                </span>
                {i === menuIndex && <span className="text-xs text-fg-subtle">Enter</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* A caixa */}
      <div
        className={cn(
          "surface-strong relative z-10 rounded-[22px]",
          "motion-normal transition-[border-color,box-shadow] focus-within:border-[color-mix(in_oklab,var(--accent)_45%,var(--edge))]",
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
          <div className="flex items-start gap-2 px-[18px] pb-1 pt-4">
            {tool && (
              <span className="animate-pop mt-px inline-flex shrink-0 items-center gap-1 rounded-full bg-accent/14 py-0.5 pl-2 pr-1 text-[13px] font-medium text-accent-ink">
                <Icon name={tool === "claude" ? "bolt" : "terminal"} size={12} />/{tool}
                <button type="button" aria-label={`Tirar ${toolName(tool)}`} onClick={clearTool} className="grid size-4 place-items-center rounded-full hover:bg-hover">
                  <Icon name="x" size={9} />
                </button>
              </span>
            )}
            <textarea
              ref={input}
              rows={1}
              value={text}
              autoFocus={autoFocus}
              onChange={(e) => onText(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={
                voice.live
                  ? "Conversa ao vivo: pode falar (ou digitar)..."
                  : tool
                    ? `O que o ${toolName(tool)} deve fazer no projeto?`
                    : placeholder
              }
              aria-label="Pedido"
              aria-autocomplete="list"
              aria-expanded={menuOpen}
              className="block min-h-6 w-full flex-1 resize-none bg-transparent text-[15px] leading-6 text-fg outline-none placeholder:text-fg-muted"
            />
          </div>
        )}
        {voice.error && <p className="px-4 pb-1 text-sm text-bad-ink">{voice.error}</p>}
        {attachments.length > 0 && (
          <ul className="flex flex-wrap gap-1.5 px-3 pb-1" aria-label="Anexos">
            {attachments.map((f) => (
              <li key={f} className="animate-pop flex items-center gap-1.5 rounded-full bg-chip py-1 pl-2.5 pr-1 text-xs text-fg" title={f}>
                <Icon name="file" size={12} />
                <span className="max-w-[180px] truncate">{baseName(f)}</span>
                <button type="button" aria-label={`Remover ${f}`} onClick={() => setAttachments((c) => c.filter((x) => x !== f))} className="grid size-5 place-items-center rounded-full hover:bg-hover">
                  <Icon name="x" size={10} />
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex items-center gap-1.5 px-2.5 pb-2.5 pt-1.5">
          {full && inApp && (
            <Hint text="Anexar arquivos">
              <IconButton icon="plus" label="Anexar arquivos" flat className="size-7" onClick={() => void pickFiles().then(addFiles)} />
            </Hint>
          )}
          {full && a && (
            <Hint text={a.hint}>
              {/* key: trocar de modo refaz a entrada com desfoque (a ficha "muda de estado", nao pisca) */}
              <span key={auth} tabIndex={0} aria-label={a.label} className={cn("swap-in motion-fast inline-flex h-7 shrink-0 cursor-default items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-sm font-medium transition-colors", a.tone)}>
                <Icon name={a.icon} size={13} /> <span className="hidden @lg:inline">{a.label}</span>
              </span>
            </Hint>
          )}
          {full && (
            <>
              <TogglePill checked={dryRun} onCheckedChange={setDryRun} icon="eye" aria-label="Simular" title="Simular: só planeja, sem executar nada" className="shrink-0 whitespace-nowrap">
                <span className="hidden @xl:inline">Simular</span>
              </TogglePill>
              <TogglePill checked={report} onCheckedChange={setReport} icon="file-text" aria-label="Relatório" title="Relatório: gera um relatório ao terminar" className="shrink-0 whitespace-nowrap">
                <span className="hidden @xl:inline">Relatório</span>
              </TogglePill>
            </>
          )}
          <TogglePill
            checked={voice.live}
            onCheckedChange={(on) => void core().call("setLiveConversation", on)}
            icon="messages"
            aria-label="Conversa"
            title="Conversa: microfone aberto, cada fala vira um pedido"
            className="shrink-0 whitespace-nowrap"
          >
            {compact ? "Conversa" : <span className="hidden @md:inline">Conversa</span>}
          </TogglePill>
          {voice.queued > 0 && <span className="whitespace-nowrap text-xs text-fg-muted">{voice.queued} na fila</span>}
          <span className="min-w-0 flex-1" />
          <Hint text={voice.hotkey ? `Gravar voz (${voice.hotkey})` : "Gravar voz"}>
            <IconButton
              icon="mic"
              label={recording ? "Enviar áudio" : "Gravar voz"}
              flat
              onClick={() => void core().call("voiceRecordToggle")}
              className={cn(recording && "bg-bad/15 text-bad-ink hover:text-bad-ink")}
            />
          </Hint>
          {running ? (
            <IconButton icon="stop" label="Parar (Esc)" onClick={() => void core().call("forceStop")} className="bg-primary text-fg-inverse hover:bg-primary hover:text-fg-inverse" />
          ) : (
            <button
              type="button"
              onClick={() => void send()}
              disabled={!canSend}
              aria-label="Enviar pedido"
              className="press motion-normal grid size-[34px] shrink-0 place-items-center rounded-full bg-primary text-fg-inverse transition-[opacity,transform] disabled:scale-95 disabled:opacity-30"
            >
              <Icon name="arrow-up" size={16} weight={2} />
            </button>
          )}
        </div>
      </div>

      {/* Bandeja de baixo: ferramentas que o "/" chama (some quando uma esta escolhida) */}
      {full && (
        <div className="tray" data-open={!tool} aria-hidden={!!tool}>
          <div className="tray-inner">
            <div className="composer-tray -mt-5 flex h-[56px] items-end gap-2 rounded-b-composer px-4 pb-2.5 text-[13px]">
              {SLASH_COMMANDS.map((c) => (
                <Hint key={c.tool} text={`${c.command} · ${c.hint}`}>
                  <button
                    type="button"
                    tabIndex={tool ? -1 : 0}
                    onClick={() => chooseTool(c.tool)}
                    className="press motion-fast inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-1 text-fg-muted transition-colors hover:bg-hover hover:text-fg"
                  >
                    <Icon name={c.icon} size={13} className="text-accent-ink" />
                    {c.name}
                  </button>
                </Hint>
              ))}
              <span className="ml-1 hidden whitespace-nowrap text-xs text-fg-subtle @xl:inline">
                digite <kbd className="rounded bg-chip px-1 font-mono">/</kbd> para chamar
              </span>
              <span className="flex-1" />
              <span className="hidden items-center gap-1.5 whitespace-nowrap text-xs text-fg-subtle @3xl:flex">
                <Icon name="command" size={12} /> Enter envia · Shift+Enter quebra linha
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
