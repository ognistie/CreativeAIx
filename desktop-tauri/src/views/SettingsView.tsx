import { useCallback, useEffect, useState } from "react";
import { Button, Spinner, StatusDot } from "../components/ui";
import { checkUpdate, core, inTauri, installUpdate, restartCore, type UpdateInfo } from "../lib/tauri";
import { useCoreEvent, useCoreStatus } from "../lib/useCore";
import { Page, Row, Section, Switch } from "./Page";

// SettingsView.qml: execucao, voz, interface, instrucoes e atalhos (desktop/data/settings.json via saveSettings).
// Mais o estado do nucleo e dos provedores (antes na tela de diagnostico da Fase 2).

interface Settings {
  instructions: string;
  plan_review: boolean;
  barge_in: boolean;
  earcon: boolean;
  live_conversation: boolean;
  splash: boolean;
  mini_chat: boolean;
  coding_mcp: boolean;
  hotkeys?: { voice?: string; stop?: string; quick?: string };
}

interface Provider {
  name: string;
  use: string;
  configured: boolean;
  next: string;
}

const MAX_INSTRUCTIONS = 1500;

interface CodingTool {
  tool: string;
  name: string;
  installed: boolean;
  version: string;
  logged_in: boolean;
  detail: string;
  login_help: string;
  install_help: string;
}

const mcpHint = (m: unknown) => {
  const v = (m ?? {}) as { ok?: boolean; tools?: string[]; error?: string };
  return v.ok ? `Respondendo com ${v.tools?.length ?? 0} ferramentas.` : v.error || "Não respondeu.";
};
const pretty = (k?: string) => (k ? k.split("+").map((x) => (x === "space" ? "Espaço" : x[0]!.toUpperCase() + x.slice(1))).join(" + ") : "—");

export function SettingsView() {
  const status = useCoreStatus();
  const [s, setS] = useState<Settings | null>(null);
  const [instructions, setInstructions] = useState("");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [coding, setCoding] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [update, setUpdate] = useState<UpdateInfo | null | "checking" | "none" | "installing">(null);

  useEffect(() => {
    if (status !== "open") return;
    core()
      .call("getSettings")
      .then((r) => {
        const v = r as Settings;
        setS(v);
        setInstructions(v.instructions || "");
      })
      .catch((e: Error) => setError(e.message));
    core()
      .call("providerStatus")
      .then((r) => setProviders((r as { providers?: Provider[] }).providers ?? []))
      .catch(() => {});
  }, [status]);

  useCoreEvent("codingStatus", useCallback((p: unknown) => setCoding(p as Record<string, unknown>), []));

  const save = (patch: Partial<Settings>) => {
    core()
      .call("saveSettings", JSON.stringify(patch))
      .then((r) => {
        const v = r as Settings & { ok?: boolean };
        if (v.ok === false) setError("Não deu para salvar.");
        else setS((cur) => ({ ...(cur ?? v), ...v }));
      })
      .catch((e: Error) => setError(e.message));
  };

  return (
    <Page title="Configurações" subtitle="Como o app executa, fala e se conecta. Muda na hora; nada aqui libera o que o agente não pode fazer.">
      {error && <p className="mb-4 rounded-r2 bg-bad/10 p-3 text-sm text-bad">{error}</p>}

      <Section title="Núcleo">
        <Row label="Núcleo Python" hint={status === "open" ? "Conectado por WebSocket local com token." : "Sem conexão com o núcleo."}>
          <StatusDot status={status === "open" ? "ok" : "warn"} />
          {inTauri && (
            <Button size="compact" icon="refresh" onClick={() => restartCore().catch((e: unknown) => setError(String(e)))}>
              Reiniciar
            </Button>
          )}
        </Row>
        {inTauri && (
          <Row
            label="Atualizações"
            hint={
              update === "none"
                ? "Você está na versão mais nova."
                : update && typeof update === "object"
                  ? `Versão ${update.version} disponível. O pacote é conferido pela assinatura antes de instalar.`
                  : "Procura uma versão nova assinada."
            }
          >
            {update && typeof update === "object" ? (
              <Button
                size="compact"
                variant="primary"
                onClick={() => {
                  setUpdate("installing");
                  installUpdate().catch((e: unknown) => (setError(String(e)), setUpdate(null)));
                }}
              >
                Instalar e reiniciar
              </Button>
            ) : (
              <Button
                size="compact"
                icon="refresh"
                disabled={update === "checking" || update === "installing"}
                onClick={() => {
                  setUpdate("checking");
                  checkUpdate()
                    .then((u) => setUpdate(u ?? "none"))
                    .catch((e: unknown) => (setError(String(e)), setUpdate(null)));
                }}
              >
                {update === "checking" ? "Procurando…" : update === "installing" ? "Instalando…" : "Procurar"}
              </Button>
            )}
          </Row>
        )}
        {providers.map((p) => (
          <Row key={p.name} label={p.name} hint={p.configured ? p.use : p.next}>
            <StatusDot status={p.configured ? "ok" : "warn"} />
          </Row>
        ))}
      </Section>

      {!s ? (
        <Spinner />
      ) : (
        <>
          <Section title="Instruções personalizadas" hint="O agente segue isto em todo pedido (tom, preferências, o que evitar).">
            <div className="p-3">
              <textarea
                value={instructions}
                maxLength={MAX_INSTRUCTIONS}
                onChange={(e) => setInstructions(e.target.value)}
                rows={5}
                aria-label="Instruções personalizadas"
                className="w-full resize-y rounded-r2 border border-hairline bg-surface p-3 text-md text-fg outline-none focus:border-accent/45"
              />
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs tabular-nums text-fg-subtle">
                  {instructions.length} / {MAX_INSTRUCTIONS}
                </span>
                <Button size="compact" variant="primary" disabled={instructions === (s.instructions || "")} onClick={() => save({ instructions })}>
                  Salvar
                </Button>
              </div>
            </div>
          </Section>

          <Section title="Execução">
            <Row label="Revisar o plano antes de executar" hint="O Maestro mostra o plano e espera sua aprovação.">
              <Switch label="Revisar o plano" checked={s.plan_review} onChange={(v) => save({ plan_review: v })} />
            </Row>
          </Section>

          <Section title="Voz">
            <Row label="Conversa em tempo real com GPT-Live" hint="Precisa de OPENAI_API_KEY. O microfone vai para a OpenAI durante a conversa.">
              <Switch label="GPT-Live" checked={s.live_conversation} onChange={(v) => save({ live_conversation: v })} />
            </Row>
            <Row label="Interromper falando" hint="Falar por cima faz o agente parar de falar.">
              <Switch label="Interromper falando" checked={s.barge_in} onChange={(v) => save({ barge_in: v })} />
            </Row>
            <Row label="Sinal sonoro ao terminar de falar">
              <Switch label="Sinal sonoro" checked={s.earcon} onChange={(v) => save({ earcon: v })} />
            </Row>
          </Section>

          <Section title="Claude Code e Codex">
            <Row label="Deixar o Claude e o Codex consultarem o Cérebro (MCP)">
              <Switch label="MCP do Cérebro" checked={s.coding_mcp} onChange={(v) => save({ coding_mcp: v })} />
            </Row>
            <Row label="Conferir as CLIs instaladas" hint={coding?.ok === false ? String(coding.error ?? "Falhou.") : "Leva cerca de 1 s por CLI."}>
              <Button size="compact" icon="refresh" onClick={() => void core().call("codingAgentsCheck")}>
                Conferir
              </Button>
            </Row>
            {Array.isArray(coding?.tools) &&
              (coding.tools as CodingTool[]).map((t) => (
                <Row
                  key={t.tool}
                  label={`${t.name}${t.version ? ` · ${t.version}` : ""}`}
                  hint={!t.installed ? t.install_help : !t.logged_in ? t.login_help : t.detail || "Instalado e com sessão."}
                >
                  <StatusDot status={t.installed && t.logged_in ? "ok" : t.installed ? "warn" : "failed"} />
                </Row>
              ))}
            {coding?.mcp != null && (
              <Row label="Servidor MCP do Cérebro" hint={mcpHint(coding.mcp)}>
                <StatusDot status={(coding.mcp as { ok?: boolean }).ok ? "ok" : "warn"} />
              </Row>
            )}
          </Section>

          <Section title="Interface">
            <Row label="Tela de abertura">
              <Switch label="Tela de abertura" checked={s.splash} onChange={(v) => save({ splash: v })} />
            </Row>
            <Row label="Mini chat quando o agente vai para outro app">
              <Switch label="Mini chat" checked={s.mini_chat} onChange={(v) => save({ mini_chat: v })} />
            </Row>
          </Section>

          <Section title="Atalhos" hint="Os atalhos ficam em config.yaml (seções ui e voice).">
            <Row label="Gravar voz">
              <kbd className="text-sm text-fg-muted">{pretty(s.hotkeys?.voice)}</kbd>
            </Row>
            <Row label="Parar a tarefa (de qualquer app)">
              <kbd className="text-sm text-fg-muted">{pretty(s.hotkeys?.stop)}</kbd>
            </Row>
            <Row label="Acesso rápido">
              <kbd className="text-sm text-fg-muted">{pretty(s.hotkeys?.quick)}</kbd>
            </Row>
            <Row label="Nova conversa · Histórico · Cérebro · Configurações">
              <kbd className="text-sm text-fg-muted">Ctrl N · Ctrl H · Ctrl B · Ctrl ,</kbd>
            </Row>
          </Section>
        </>
      )}
    </Page>
  );
}
