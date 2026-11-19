import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Chip, Field, GlassPanel, Icon, Spinner } from "../components/ui";
import type { Appearance } from "../lib/appearance";
import { cn } from "../lib/cn";
import { core } from "../lib/host";
import { DevProposals } from "../components/DevProposals";
import { useCoreEvent } from "../lib/useCore";
import { AboutView } from "./AboutView";
import { GeneralSettings } from "./SettingsView";
import { AppearancePanel } from "./AppearancePanel";
import { Page, Switch } from "./Page";

// HarnessView: como os agentes trabalham e como a plataforma se parece. Preferencias validadas no
// nucleo (core/harness.py), com versoes; as regras de seguranca continuam valendo.

export interface Harness {
  agents: Record<string, { instructions: string }>;
  response: { tone: string; length: string; extra: string };
  appearance: { accent: string; palette: string; mode: string; radius: string; motion: boolean; [k: string]: unknown };
  modules: Record<string, boolean>;
  dev: { enabled: boolean; code_changes: boolean; greeting: string; hint: string; shortcuts: unknown[]; cards: unknown[] };
  [k: string]: unknown;
}

interface Proposal {
  id: string;
  summary: string;
  empty?: boolean;
  changes: Array<{ field: string; before: unknown; after: unknown }>;
  notes: Array<{ mode: string; rel: string; content: string }>;
  warnings: string[];
  rejected: string[];
  not_done: string[];
}

type Reply = { ok: boolean; error?: string } & Record<string, unknown>;
const call = (p: Promise<unknown>) => p.then((r) => r as Reply).catch((e: Error) => ({ ok: false, error: e.message }) as Reply);
const TONES = [["natural", "Natural"], ["direto", "Direto"], ["detalhado", "Detalhado"], ["amigavel", "Amigável"], ["formal", "Formal"]] as const;
const LENGTHS = [["curta", "Curta"], ["media", "Média"], ["longa", "Longa"]] as const;
const show = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

type HTab = "geral" | "sobre" | "mudar" | "respostas" | "aparencia" | "dev" | "versoes";
const HTABS: Array<{ id: HTab; label: string; icon: "settings" | "info" | "pen" | "messages" | "palette" | "sidebar" | "code" | "history" }> = [
  { id: "geral", label: "Geral", icon: "settings" },
  { id: "mudar", label: "Mudar com IA", icon: "pen" },
  { id: "respostas", label: "Respostas", icon: "messages" },
  { id: "aparencia", label: "Aparência", icon: "palette" },
  { id: "dev", label: "Desenvolvedor", icon: "code" },
  { id: "versoes", label: "Versões", icon: "history" },
  { id: "sobre", label: "Sobre", icon: "info" },
];

const SECTION_NOTES: Record<HTab, [string, string]> = {
  geral: ["Ajuste notificações de voz, execução e integrações.", "Preferências do aplicativo"],
  sobre: ["Conheça o Creative AIx e seus agentes.", "Sobre o Creative AIx"],
  mudar: ["Descreva um ajuste e revise a proposta.", "Proposta para revisar"],
  respostas: ["Escolha o tom e o tamanho das respostas.", "Estilo da conversa"],
  aparencia: ["Ajuste a luz, o tema e o papel de parede.", "Prévia da aparência"],
  dev: ["Configure a experiência e as propostas de código.", "Modo Desenvolvedor"],
  versoes: ["Consulte e restaure configurações anteriores.", "Histórico de versões"],
};

export function HarnessView({ onChanged, onPreview, onOpenLab }: {
  onChanged?: (h: Harness) => void;
  onPreview: (look: Appearance | null) => void;
  onOpenLab?: () => void;
}) {
  const [tab, setTab] = useState<HTab>("geral");
  const [saved, setSaved] = useState<Harness | null>(null);
  const [draft, setDraft] = useState<Harness | null>(null);
  const [versions, setVersions] = useState<Array<{ id: string; label: string; when: string }>>([]);
  const [writable, setWritable] = useState(true);
  const [error, setError] = useState("");
  const writing = useRef(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const dirty = !!draft && !!saved && JSON.stringify(draft) !== JSON.stringify(saved);

  const say = (m: string) => {
    setToast(m);
    setTimeout(() => setToast(""), 2600);
  };

  // Recarregar (abrir, restaurar versao) remonta o painel de Aparencia com o que esta salvo
  const [loads, setLoads] = useState(0);
  const load = useCallback(() => {
    void call(core().call("harnessGet")).then((r) => {
      if (!r.ok) return setError(r.error || "");
      const h = r.harness as Harness;
      setLoads((n) => n + 1);
      setSaved(h);
      setDraft(clone(h));
      setVersions((r.versions as never) ?? []);
      setWritable(r.writable !== false);
    });
  }, []);
  useEffect(load, [load]);

  const patch = (path: string[], value: unknown) =>
    setDraft((d) => {
      if (!d) return d;
      const next = clone(d) as Record<string, unknown>;
      let o = next;
      for (const k of path.slice(0, -1)) o = (o[k] ??= {}) as Record<string, unknown>;
      o[path.at(-1)!] = value;
      return next as Harness;
    });

  const save = async (h: Harness, label: string, quiet = false) => {
    if (writing.current || !writable) return;
    writing.current = true;
    setSaving(true);
    setError("");
    try {
      const updates: Record<string, unknown> = {};
      for (const [section, value] of Object.entries(h)) {
        const before = saved?.[section as keyof Harness];
        if (JSON.stringify(value) === JSON.stringify(before)) continue;
        updates[section] = value && typeof value === "object" && !Array.isArray(value)
          ? Object.fromEntries(Object.entries(value).filter(([key, item]) =>
              JSON.stringify(item) !== JSON.stringify((before as Record<string, unknown> | undefined)?.[key])))
          : value;
      }
      const r = await call(core().call("harnessPatch", JSON.stringify(updates), label));
      if (!r.ok) return setError(r.error || "Não salvou.");
      const result = r.harness as Harness;
      setSaved(result);
      setDraft((previous) => quiet && previous ? { ...previous, appearance: result.appearance } : clone(result));
      onChanged?.(result);
      if (!quiet) say("Salvo");
      void call(core().call("harnessGet")).then((g) => g.ok && setVersions((g.versions as never) ?? []));
    } finally {
      writing.current = false;
      setSaving(false);
    }
  };

  const onAppearanceSaved = useCallback((h: Harness) => {
    setSaved(h);
    setDraft((previous) => (previous ? { ...previous, appearance: h.appearance } : clone(h)));
    onChanged?.(h);
    void call(core().call("harnessGet")).then((g) => g.ok && setVersions((g.versions as never) ?? []));
  }, [onChanged]);

  return (
    <Page
      wide
      title="Configurações"
      subtitle="Preferências do aplicativo, dos agentes e da aparência."
      actions={
        dirty && draft && saved ? (
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setDraft(clone(saved))}>
              Descartar
            </Button>
            <Button variant="primary" icon="save" disabled={!writable || saving} onClick={() => void save(draft, "Configurações")}>
              Salvar
            </Button>
          </div>
        ) : undefined
      }
    >
      {error && <p className="mb-4 rounded-r2 bg-bad/10 p-3 text-sm text-bad-ink">{error}</p>}
      {!writable && <p className="mb-4 rounded-r2 bg-warn/10 p-3 text-sm text-fg">A pasta do seu cérebro não está disponível: dá para ver, mas não salvar.</p>}

      <div className="harness-region">
      <div className="harness-studio">
        <div role="tablist" aria-label="Seções de Configurações" aria-orientation="vertical" className="harness-index"
          onKeyDown={(event) => {
            const step = event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0;
            if (!step) return;
            event.preventDefault();
            const next = (HTABS.findIndex((item) => item.id === tab) + step + HTABS.length) % HTABS.length;
            setTab(HTABS[next]!.id);
            event.currentTarget.querySelectorAll("button")[next]?.focus();
          }}>
          {HTABS.map((item) => (
            <button key={item.id} type="button" role="tab" id={`h-tab-${item.id}`}
              aria-selected={item.id === tab} aria-controls="h-console" tabIndex={item.id === tab ? 0 : -1}
              onClick={() => setTab(item.id)}>
              <span><Icon name={item.icon} size={17} /> {item.label}</span>
              {item.id === tab && <small>{SECTION_NOTES[item.id][0]}</small>}
            </button>
          ))}
        </div>

        <div role="tabpanel" id="h-console" aria-labelledby={`h-tab-${tab}`} className="harness-console" data-section={tab}>
          {tab !== "geral" && tab !== "sobre" && tab !== "aparencia" && <div className="harness-visual">
            <div className="harness-float" key={tab}>
              <Icon name={HTABS.find((item) => item.id === tab)!.icon} size={22} />
              <span>{SECTION_NOTES[tab][1]}</span>
            </div>
          </div>}
          <div className="harness-controls" hidden={tab !== "geral"}><GeneralSettings /></div>
          {tab !== "geral" && <div className="harness-controls" key={tab}>
      {tab === "sobre" ? <AboutView /> : !draft || !saved ? (error ? <Button onClick={load}>Tentar de novo</Button> : <Spinner />) : (<>
      {tab === "mudar" && (
        <>
      <Creator disabled={dirty || !writable} onApplied={() => (load(), say("Mudança aplicada"))} />

          <GlassPanel className="mb-5 flex flex-wrap items-center gap-4 p-5">
            <span className="grid size-11 shrink-0 place-items-center rounded-r3 bg-accent/15 text-accent-ink">
              <Icon name="flask" size={20} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-md font-semibold text-fg">Instruções, memória e código de cada agente</p>
              <p className="mt-0.5 text-sm text-fg-muted">Ficam no AI Research Lab: especificação, notas ligadas, mudanças de código revisadas e testes.</p>
            </div>
            {onOpenLab && (
              <Button icon="arrow-right" onClick={onOpenLab}>
                Abrir o Lab
              </Button>
            )}
          </GlassPanel>
        </>
      )}
      {tab === "respostas" && (
      <Block title="Padrão das respostas" note="Como o agente fala com você ao terminar cada pedido. Vale depois de Salvar.">
        <Labeled label="Tom">
          {TONES.map(([v, l]) => (
            <Chip key={v} selected={draft.response.tone === v} onClick={() => patch(["response", "tone"], v)}>
              {l}
            </Chip>
          ))}
        </Labeled>
        <Labeled label="Tamanho">
          {LENGTHS.map(([v, l]) => (
            <Chip key={v} selected={draft.response.length === v} onClick={() => patch(["response", "length"], v)}>
              {l}
            </Chip>
          ))}
        </Labeled>
        <textarea
          value={draft.response.extra}
          maxLength={1500}
          onChange={(e) => patch(["response", "extra"], e.target.value)}
          rows={3}
          placeholder="Algo mais sobre as respostas (ex.: termine com o próximo passo sugerido)"
          aria-label="Instrução extra para as respostas"
          className="mt-3 w-full select-text resize-y rounded-r2 border border-hairline bg-surface p-3 text-md text-fg outline-none focus:border-accent/45"
        />
      </Block>
      )}
      {tab === "aparencia" && (
        <AppearancePanel key={loads} harness={saved} writable={writable} onPreview={onPreview} onSaved={onAppearanceSaved} />
      )}
      {tab === "dev" && <Developer draft={draft} patch={patch} />}
      {tab === "versoes" && (
      <Block title="Versões" note="Cada vez que você salva, a versão anterior fica guardada aqui.">
        {versions.length === 0 ? (
          <p className="text-sm text-fg-subtle">Nenhuma versão anterior ainda.</p>
        ) : (
          <ul className="overflow-hidden rounded-r3 border border-hairline">
            {versions.slice(0, 15).map((v) => (
              <li key={v.id} className="flex items-center gap-3 border-b border-hairline px-3 py-2 last:border-0">
                <span className="w-32 text-xs tabular-nums text-fg-subtle">{v.when.replace(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2}).*/, "$3/$2 $4:$5")}</span>
                <span className="flex-1 text-sm text-fg">{v.label || "Configurações"}</span>
                <Button
                  size="compact"
                  variant="ghost"
                  icon="undo"
                  disabled={!writable || saving}
                  onClick={async () => {
                    const r = await call(core().call("harnessRestore", v.id));
                    if (!r.ok) return setError(r.error || "");
                    load();
                    onChanged?.(r.harness as Harness);
                    say("Versão restaurada");
                  }}
                >
                  Restaurar
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Block>
      )}
      </>)}
      </div>}
      </div>
      </div>
      </div>
      {toast && (
        <div role="status" className="animate-enter fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-primary px-4 py-2 text-[13px] text-fg-inverse shadow-lg">
          {toast}
        </div>
      )}
    </Page>
  );
}

function Block({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <GlassPanel className="mb-5 p-5">
      <h2 className="text-md font-medium text-fg">{title}</h2>
      {note && <p className="mb-4 mt-0.5 text-sm text-fg-muted">{note}</p>}
      {children}
    </GlassPanel>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <span className="w-24 shrink-0 text-sm text-fg-muted">{label}</span>
      {children}
    </div>
  );
}

/** Criador: descreva a mudanca em linguagem natural; o modelo propoe e voce aprova. */
function Creator({ disabled, onApplied }: { disabled: boolean; onApplied: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [error, setError] = useState("");

  useCoreEvent(
    "creatorReady",
    useCallback((p: unknown) => {
      setBusy(false);
      const r = p as Reply;
      if (!r.ok) return setError(r.error || "Não deu para propor.");
      setProposal(r.proposal as Proposal);
    }, []),
  );

  const discard = () => {
    if (proposal) void core().call("creatorDiscard", proposal.id);
    setProposal(null);
  };

  return (
    <Block title="Descreva a mudança" note="Em linguagem natural. O modelo propõe, as regras conferem e nada muda sem você aprovar.">
      <div className="flex gap-2">
        <Field
          value={text}
          disabled={disabled || busy}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && text.trim().length >= 3 && (setBusy(true), setError(""), setProposal(null), void core().call("creatorPropose", text))}
          placeholder={disabled ? "Salve ou descarte as alterações abaixo antes" : "O que você quer mudar? (ex.: respostas mais curtas e diretas)"}
          aria-label="Mudança desejada"
        />
        <Button
          variant="primary"
          disabled={disabled || busy || text.trim().length < 3}
          onClick={() => {
            setBusy(true);
            setError("");
            setProposal(null);
            void core().call("creatorPropose", text);
          }}
        >
          {busy ? <Spinner size={12} /> : null} Propor
        </Button>
      </div>
      {error && <p className="mt-3 text-sm text-bad-ink">{error}</p>}
      {proposal && (
        <div className="animate-enter mt-4 rounded-r3 border border-hairline bg-surface p-4">
          <p className="text-md text-fg">{proposal.empty ? "Nada para mudar com esse pedido." : proposal.summary}</p>
          {proposal.changes.length > 0 && (
            <ul className="mt-3 space-y-1.5 text-sm">
              {proposal.changes.map((c, i) => (
                <li key={i} className="grid grid-cols-[160px_1fr] gap-3">
                  <span className="text-fg-muted">{c.field}</span>
                  <span>
                    {show(c.before) !== "—" && <span className="mr-2 text-fg-subtle line-through">{show(c.before)}</span>}
                    <span className="text-fg">{show(c.after)}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {proposal.notes.map((n, i) => (
            <p key={i} className="mt-2 text-sm text-fg-muted">
              {n.mode === "criar" ? "Nota nova · " : "Acrescentar em · "}
              {n.rel.replace(/\.md$/, "")}: <span className="text-fg">{n.content.slice(0, 200)}</span>
            </p>
          ))}
          {[...proposal.warnings.map((w) => ["warn", w]), ...proposal.rejected.map((w) => ["bad", `Recusado: ${w}`]), ...proposal.not_done.map((w) => ["muted", `Não feito: ${w}`])].map(([k, w], i) => (
            <p key={i} className={cn("mt-2 text-sm", k === "warn" ? "text-warn-ink" : k === "bad" ? "text-bad-ink" : "text-fg-muted")}>
              {w}
            </p>
          ))}
          <div className="mt-4 flex gap-2">
            {!proposal.empty && (
              <Button
                variant="primary"
                icon="check"
                onClick={async () => {
                  const r = await call(core().call("creatorApply", proposal.id));
                  if (!r.ok) return setError(r.error || "");
                  setProposal(null);
                  setText("");
                  onApplied();
                }}
              >
                Aplicar
              </Button>
            )}
            <Button onClick={discard}>{proposal.empty ? "Fechar" : "Descartar"}</Button>
          </div>
        </div>
      )}
    </Block>
  );
}

/** Desenvolvedor: niveis 1 e 2 sem codigo (saudacao, dica); nivel 3 com Claude Code/Codex numa worktree. */
function Developer({ draft, patch }: { draft: Harness; patch: (path: string[], v: unknown) => void }) {
  return (
    <Block
      title="Desenvolvedor"
      note="Níveis 1 e 2 são ajustes sem código, validados e com versões. O nível 3 pede ao Claude Code ou ao Codex uma mudança de código numa cópia separada: você vê o diff, o gate roda e só entra se você aplicar."
    >
      <Labeled label="Modo dev">
        <Switch label="Modo desenvolvedor" checked={draft.dev.enabled} onChange={(v) => patch(["dev", "enabled"], v)} />
      </Labeled>
      {draft.dev.enabled && (
        <>
          <Labeled label="Saudação">
            <Field value={draft.dev.greeting} onChange={(e) => patch(["dev", "greeting"], e.target.value)} placeholder="Como posso ajudar?" className="max-w-md" />
          </Labeled>
          <Labeled label="Dica">
            <Field value={draft.dev.hint} onChange={(e) => patch(["dev", "hint"], e.target.value)} placeholder="Texto abaixo da saudação" className="max-w-md" />
          </Labeled>
          <Labeled label="Mudanças de código">
            <Switch label="Mudanças de código (nível 3)" checked={draft.dev.code_changes} onChange={(v) => patch(["dev", "code_changes"], v)} />
          </Labeled>
          {draft.dev.code_changes && (
            <div className="mt-4 rounded-r3 border border-hairline p-4">
              <DevProposals />
            </div>
          )}
        </>
      )}
    </Block>
  );
}
