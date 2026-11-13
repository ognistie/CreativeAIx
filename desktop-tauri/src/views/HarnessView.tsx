import { useCallback, useEffect, useState } from "react";
import { AppDialog, Button, Chip, EmptyState, Field, GlassPanel, Icon, Segmented, Spinner, StatusDot } from "../components/ui";
import { agentLabel } from "../lib/agents";
import { applyAppearance } from "../lib/appearance";
import { cn } from "../lib/cn";
import { core } from "../lib/tauri";
import { IntroCard } from "../components/IntroCard";
import { useCoreEvent } from "../lib/useCore";
import { Page, Switch } from "./Page";

// HarnessView.qml: como os agentes trabalham e como a plataforma se parece. Preferencias validadas no
// nucleo (core/harness.py), com versoes; as regras de seguranca continuam valendo.

export interface Harness {
  agents: Record<string, { instructions: string }>;
  response: { tone: string; length: string; extra: string };
  appearance: { accent: string; palette: string; mode: string; radius: string; motion: boolean; [k: string]: unknown };
  modules: Record<string, boolean>;
  dev: { enabled: boolean; code_changes: boolean; greeting: string; hint: string; shortcuts: unknown[]; cards: unknown[] };
  [k: string]: unknown;
}

interface Profile {
  agent: string;
  role: string;
  does: string[];
  uses: string;
  inputs: string;
  limits: string[];
  examples: string[];
  tools: string[];
  rules: string[];
  skills: Array<{ name: string; purpose: string }>;
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

interface DevProposal {
  id: string;
  tool: string;
  request: string;
  status: string;
  summary: string;
  files: string[];
  gate: { ok: boolean } | null;
}

type Reply = { ok: boolean; error?: string } & Record<string, unknown>;
const call = (p: Promise<unknown>) => p.then((r) => r as Reply).catch((e: Error) => ({ ok: false, error: e.message }) as Reply);
const AGENTS = ["MAESTRO", "WEB", "DESKTOP", "CODE", "DATA", "FILE", "EXTCODE"];
const TONES = [["natural", "Natural"], ["direto", "Direto"], ["detalhado", "Detalhado"], ["amigavel", "Amigável"], ["formal", "Formal"]] as const;
const LENGTHS = [["curta", "Curta"], ["media", "Média"], ["longa", "Longa"]] as const;
const PALETTES = ["abismo", "aurora", "ameixa", "nevoa", "matcha", "seda", "brisa", "coral", "menta", "lavanda", "areia", "oceano", "aurora-boreal"];
const ACCENTS = ["#16897E", "#2F6FDB", "#7A4FD6", "#C2417A", "#D9622B", "#3F8F3A"];
const MODULES = [["brain", "Cérebro"], ["you", "Você"], ["history", "Histórico"]] as const;
const devStatus = (p: DevProposal) =>
  p.status === "applied" || (p.status === "checked" && p.gate?.ok)
    ? "ok"
    : ["failed", "rejected", "gate_failed"].includes(p.status)
      ? "failed"
      : ["reverted", "discarded"].includes(p.status)
        ? "cancelled"
        : "warn";
const show = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

export function HarnessView({ onChanged }: { onChanged?: (h: Harness) => void }) {
  const [saved, setSaved] = useState<Harness | null>(null);
  const [draft, setDraft] = useState<Harness | null>(null);
  const [versions, setVersions] = useState<Array<{ id: string; label: string; when: string }>>([]);
  const [writable, setWritable] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const dirty = !!draft && !!saved && JSON.stringify(draft) !== JSON.stringify(saved);

  const say = (m: string) => {
    setToast(m);
    setTimeout(() => setToast(""), 2600);
  };

  const load = useCallback(() => {
    void call(core().call("harnessGet")).then((r) => {
      if (!r.ok) return setError(r.error || "");
      const h = r.harness as Harness;
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
    const r = await call(core().call("harnessSave", JSON.stringify(h), label));
    if (!r.ok) return setError(r.error || "Não salvou.");
    const next = r.harness as Harness;
    setSaved(next);
    setDraft(clone(next));
    onChanged?.(next);
    if (!quiet) say("Salvo");
    void call(core().call("harnessGet")).then((g) => g.ok && setVersions((g.versions as never) ?? []));
  };

  // Aparencia: aplica e salva na hora (como no QML), sem esperar o Salvar
  const setAppearance = (key: string, value: unknown) => {
    if (!saved) return;
    const next = clone(saved);
    (next.appearance as Record<string, unknown>)[key] = value;
    applyAppearance(next.appearance);
    void save({ ...next, agents: draft?.agents ?? next.agents, response: draft?.response ?? next.response }, "Aparência", true);
  };

  if (!draft || !saved) {
    return (
      <Page title="Harness">
        {error ? <p className="rounded-r2 bg-bad/10 p-3 text-sm text-bad">{error}</p> : <Spinner />}
      </Page>
    );
  }

  return (
    <Page
      wide
      title="Harness"
      subtitle="Ajuste como os agentes trabalham juntos e como a plataforma se parece. São preferências: as regras de segurança continuam valendo."
      actions={
        dirty ? (
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setDraft(clone(saved))}>
              Descartar
            </Button>
            <Button variant="primary" icon="save" disabled={!writable} onClick={() => void save(draft, "Harness")}>
              Salvar
            </Button>
          </div>
        ) : undefined
      }
    >
      {error && <p className="mb-4 rounded-r2 bg-bad/10 p-3 text-sm text-bad">{error}</p>}
      <IntroCard which="harness" />
      {!writable && <p className="mb-4 rounded-r2 bg-warn/10 p-3 text-sm text-fg">A pasta do seu cérebro não está disponível: dá para ver, mas não salvar.</p>}

      <Creator disabled={dirty || !writable} onApplied={() => (load(), say("Mudança aplicada"))} />
      <Agents draft={draft} patch={patch} />

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

      <Block title="Aparência" note="Muda e fica salva na hora, sem precisar de Salvar. A anterior vai para Versões.">
        <Labeled label="Tema">
          <Segmented
            label="Tema"
            value={saved.appearance.mode as "escuro" | "claro"}
            onValueChange={(v) => setAppearance("mode", v)}
            options={[
              { value: "escuro", label: "Escuro" },
              { value: "claro", label: "Claro" },
            ]}
          />
        </Labeled>
        <Labeled label="Paleta">
          {PALETTES.map((p) => (
            <Chip key={p} selected={saved.appearance.palette === p} onClick={() => setAppearance("palette", p)}>
              {p}
            </Chip>
          ))}
        </Labeled>
        <Labeled label="Destaque">
          {ACCENTS.map((c) => (
            <button
              key={c}
              type="button"
              aria-label={`Cor de destaque ${c}`}
              aria-pressed={saved.appearance.accent.toUpperCase() === c}
              onClick={() => setAppearance("accent", c)}
              className={cn("size-7 rounded-full border-2", saved.appearance.accent.toUpperCase() === c ? "border-fg" : "border-transparent")}
              style={{ background: c }}
            />
          ))}
        </Labeled>
        <Labeled label="Cantos">
          <Segmented
            label="Cantos"
            value={saved.appearance.radius as "suave" | "reto" | "redondo"}
            onValueChange={(v) => setAppearance("radius", v)}
            options={[
              { value: "suave", label: "Suave" },
              { value: "reto", label: "Reto" },
              { value: "redondo", label: "Redondo" },
            ]}
          />
        </Labeled>
        <Labeled label="Movimento">
          <Switch label="Movimento" checked={!!saved.appearance.motion} onChange={(v) => setAppearance("motion", v)} />
        </Labeled>
        <Labeled label="Luzes">
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={Number(saved.appearance.ambient ?? 0.55)}
            onChange={(e) => applyAppearance({ ambient: Number(e.target.value) })}
            onPointerUp={(e) => setAppearance("ambient", Number((e.target as HTMLInputElement).value))}
            onKeyUp={(e) => setAppearance("ambient", Number((e.target as HTMLInputElement).value))}
            aria-label="Intensidade das luzes de fundo"
            className="w-48 accent-[var(--accent)]"
          />
        </Labeled>
        <Labeled label="Desfoque">
          <Switch label="Vidro com desfoque" checked={saved.appearance.blur !== false} onChange={(v) => setAppearance("blur", v)} />
        </Labeled>
        <p className="mt-3 text-xs text-fg-subtle">Papel de parede com foto: por enquanto, na interface Qt.</p>
      </Block>

      <Block title="Barra lateral" note="Escolha as telas que aparecem. O Harness fica sempre na barra lateral. Vale depois de Salvar.">
        <div className="flex flex-wrap gap-2">
          {MODULES.map(([k, l]) => (
            <Chip key={k} selected={draft.modules[k] !== false} onClick={() => patch(["modules", k], draft.modules[k] === false)}>
              {l}
            </Chip>
          ))}
        </div>
      </Block>

      <Developer draft={draft} patch={patch} />

      <Block title="Versões" note="Cada vez que você salva, a versão anterior fica guardada aqui.">
        {versions.length === 0 ? (
          <p className="text-sm text-fg-subtle">Nenhuma versão anterior ainda.</p>
        ) : (
          <ul className="overflow-hidden rounded-r3 border border-hairline">
            {versions.slice(0, 15).map((v) => (
              <li key={v.id} className="flex items-center gap-3 border-b border-hairline px-3 py-2 last:border-0">
                <span className="w-32 text-xs tabular-nums text-fg-subtle">{v.when.replace(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2}).*/, "$3/$2 $4:$5")}</span>
                <span className="flex-1 text-sm text-fg">{v.label || "Harness"}</span>
                <Button
                  size="compact"
                  variant="ghost"
                  icon="refresh"
                  disabled={!writable}
                  onClick={async () => {
                    const r = await call(core().call("harnessRestore", v.id));
                    if (!r.ok) return setError(r.error || "");
                    load();
                    applyAppearance((r.harness as Harness).appearance);
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
      {error && <p className="mt-3 text-sm text-bad">{error}</p>}
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
            <p key={i} className={cn("mt-2 text-sm", k === "warn" ? "text-warn" : k === "bad" ? "text-bad" : "text-fg-muted")}>
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

function Agents({ draft, patch }: { draft: Harness; patch: (path: string[], v: unknown) => void }) {
  const [agent, setAgent] = useState("MAESTRO");
  const [profile, setProfile] = useState<Profile | null>(null);
  useEffect(() => {
    setProfile(null);
    void call(core().call("agentProfile", agent)).then((r) => r.ok && setProfile(r as unknown as Profile));
  }, [agent]);

  return (
    <Block title="Como os agentes trabalham" note="O papel de cada agente, o que ele recebe e usa, os limites, e instruções suas que valem depois de Salvar.">
      <div className="mb-4 flex flex-wrap gap-1.5">
        {AGENTS.map((a) => (
          <Chip key={a} selected={agent === a} onClick={() => setAgent(a)}>
            {agentLabel(a)}
          </Chip>
        ))}
      </div>
      {!profile ? (
        <Spinner />
      ) : (
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-3 text-sm">
            <p className="text-md text-fg">{profile.role}</p>
            <List title="Faz" items={profile.does} />
            <List title="Limites" items={profile.limits} />
            <p className="text-fg-muted">
              <span className="text-fg">Recebe:</span> {profile.inputs}
            </p>
            {profile.tools.length > 0 && (
              <p className="text-fg-muted">
                <span className="text-fg">Ferramentas:</span> {profile.tools.join(", ")}
              </p>
            )}
            {profile.skills.length > 0 && <List title="Skills" items={profile.skills.map((s) => `${s.name}: ${s.purpose}`)} />}
          </div>
          <div>
            <label className="mb-1.5 block text-sm text-fg-muted">Suas instruções para {agentLabel(agent)}</label>
            <textarea
              value={draft.agents[agent]?.instructions ?? ""}
              onChange={(e) => patch(["agents", agent, "instructions"], e.target.value)}
              rows={8}
              placeholder="Ex.: sempre confira o destino antes de copiar arquivos."
              className="w-full select-text resize-y rounded-r2 border border-hairline bg-surface p-3 text-md text-fg outline-none focus:border-accent/45"
            />
            {profile.examples.length > 0 && <p className="mt-2 text-xs text-fg-subtle">Exemplos de pedido: {profile.examples.join(" · ")}</p>}
          </div>
        </div>
      )}
    </Block>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-[0.08em] text-fg-muted">{title}</p>
      <ul className="list-disc space-y-0.5 pl-5 text-fg">
        {items.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </div>
  );
}

/** Desenvolvedor: niveis 1 e 2 sem codigo (saudacao, dica); nivel 3 com Claude Code/Codex numa worktree. */
function Developer({ draft, patch }: { draft: Harness; patch: (path: string[], v: unknown) => void }) {
  const [items, setItems] = useState<DevProposal[]>([]);
  const [request, setRequest] = useState("");
  const [tool, setTool] = useState<"claude" | "codex">("claude");
  const [progress, setProgress] = useState("");
  const [diff, setDiff] = useState<{ id: string; text: string } | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(() => void call(core().call("devList")).then((r) => r.ok && setItems((r.items as DevProposal[]) ?? [])), []);
  useEffect(refresh, [refresh]);
  useCoreEvent(
    "devChanged",
    useCallback(
      (p: unknown) => {
        const e = p as { status: string; message: string };
        setProgress(e.status === "progress" ? e.message : "");
        if (e.status === "error") setError(e.message);
        refresh();
      },
      [refresh],
    ),
  );

  const act = async (id: string, action: string) => {
    const r = await call(core().call("devAct", id, action));
    if (!r.ok) setError(r.error || "");
    refresh();
  };

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
              <div className="flex flex-wrap gap-2">
                <Field value={request} onChange={(e) => setRequest(e.target.value)} placeholder="Descreva a mudança de código" className="min-w-[260px] flex-1" aria-label="Mudança de código" />
                <Segmented
                  label="Ferramenta"
                  value={tool}
                  onValueChange={setTool}
                  options={[
                    { value: "claude", label: "Claude Code" },
                    { value: "codex", label: "Codex" },
                  ]}
                />
                <Button
                  variant="primary"
                  disabled={request.trim().length < 5}
                  onClick={async () => {
                    setError("");
                    const r = await call(core().call("devPropose", request, tool));
                    if (!r.ok) setError(r.error || "");
                    else setRequest("");
                  }}
                >
                  Pedir
                </Button>
              </div>
              {progress && (
                <p className="mt-2 flex items-center gap-2 text-sm text-fg-muted">
                  <Spinner size={12} /> {progress}
                </p>
              )}
              {error && <p className="mt-2 text-sm text-bad">{error}</p>}
              {items.length === 0 ? (
                <EmptyState icon="code" title="Nenhuma proposta de código" />
              ) : (
                <ul className="mt-3 space-y-2">
                  {items.map((p) => (
                    <li key={p.id} className="rounded-r2 border border-hairline p-3 text-sm">
                      <p className="flex items-center gap-2 text-fg">
                        <StatusDot status={devStatus(p)} size={13} />
                        <span className="flex-1">{p.request}</span>
                        <span className="text-xs text-fg-subtle">
                          {p.tool} · {p.status}
                        </span>
                      </p>
                      {p.summary && <p className="mt-1 text-fg-muted">{p.summary}</p>}
                      {p.files.length > 0 && <p className="mt-1 text-xs text-fg-subtle">{p.files.join(", ")}</p>}
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <Button size="compact" variant="ghost" icon="file-text" onClick={async () => { const r = await call(core().call("devDiff", p.id)); if (r.ok) setDiff({ id: p.id, text: String(r.diff ?? "") }); }}>
                          Ver diff
                        </Button>
                        {(p.status === "proposed" || p.status === "gate_failed") && (
                          <Button size="compact" icon="refresh" onClick={() => void core().call("devCheck", p.id)}>
                            Rodar o gate
                          </Button>
                        )}
                        {p.status === "checked" && p.gate?.ok && (
                          <Button size="compact" variant="primary" icon="check" onClick={() => void act(p.id, "apply")}>
                            Aplicar
                          </Button>
                        )}
                        {p.status === "applied" && (
                          <Button size="compact" icon="refresh" onClick={() => void act(p.id, "undo")}>
                            Desfazer
                          </Button>
                        )}
                        {!["applied", "reverted", "discarded"].includes(p.status) && (
                          <Button size="compact" variant="ghost" onClick={() => void act(p.id, "discard")}>
                            Descartar
                          </Button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}
      <AppDialog open={!!diff} onOpenChange={(o) => !o && setDiff(null)} title="Diff da proposta">
        <pre className="max-h-[60vh] select-text overflow-auto rounded-r2 bg-surface p-3 font-mono text-[12px] text-fg">{diff?.text || "Sem diferenças."}</pre>
        <div className="mt-4 flex justify-end">
          <Button onClick={() => setDiff(null)}>
            <Icon name="x" size={12} /> Fechar
          </Button>
        </div>
      </AppDialog>
    </Block>
  );
}
