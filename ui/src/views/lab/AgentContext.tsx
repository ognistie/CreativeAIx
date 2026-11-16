import { useEffect, useMemo, useState } from "react";
import { Button, Field, GlassPanel, Icon, Spinner } from "../../components/ui";
import { cn } from "../../lib/cn";
import { core } from "../../lib/host";
import { AGENT_LOOK, call, type Memory } from "./types";

// Contexto ligado: notas do Cerebro e um texto extra que entram no prompt deste agente a cada pedido
// (core/agent_studio.py > linked_context). Sao referencia; nunca ampliam permissao.

const MAX_LINKS = 12;
const MAX_EXTRA = 1500;
interface Hit {
  rel: string;
  title: string;
  snippet: string;
}

export function AgentContext({ agent, memory, onSaved, onDirty }: { agent: string; memory: Memory; onSaved: (m: Memory) => void; onDirty: (d: boolean) => void }) {
  const [links, setLinks] = useState(memory.links);
  const [extra, setExtra] = useState(memory.extra);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [state, setState] = useState<"" | "saving" | "saved">("");
  const [error, setError] = useState("");

  useEffect(() => {
    setLinks(memory.links);
    setExtra(memory.extra);
  }, [memory]);

  const dirty = extra !== memory.extra || JSON.stringify(links.map((l) => l.title)) !== JSON.stringify(memory.links.map((l) => l.title));
  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return setHits(null);
    const t = setTimeout(() => {
      void call(core().call("brainSearch", q)).then((r) => setHits(r.ok ? ((r.items as Hit[]) ?? []).slice(0, 8) : []));
    }, 180);
    return () => clearTimeout(t);
  }, [query]);

  const has = useMemo(() => new Set(links.map((l) => l.title.toLowerCase())), [links]);
  const add = (h: Hit) => {
    if (has.has(h.title.toLowerCase()) || links.length >= MAX_LINKS) return;
    setLinks((l) => [...l, { title: h.title, rel: h.rel }]);
  };

  const save = async () => {
    setState("saving");
    setError("");
    const r = await call(core().call("studioSave", agent, JSON.stringify({ links: links.map((l) => l.title), extra })));
    if (!r.ok) return (setState(""), setError(r.error || "Não salvou."));
    onSaved(r.memory as Memory);
    setState("saved");
    setTimeout(() => setState(""), 2200);
  };

  const preview = [extra.trim(), ...links.filter((l) => l.rel).map((l) => `[${l.title}] …trecho da nota…`)].filter(Boolean).join("\n");

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px] [&>*]:min-w-0">
      <div className="space-y-5">
        <GlassPanel className="relative z-30 p-5">
          <h3 className="flex items-center gap-2 text-md font-semibold text-fg">
            <Icon name="link" size={16} className="text-fg-muted" /> Notas ligadas
            <span className="ml-auto text-xs font-normal tabular-nums text-fg-muted">
              {links.length}/{MAX_LINKS}
            </span>
          </h3>
          <p className="mt-1 text-sm text-fg-muted">Um trecho de cada nota vai junto com os pedidos para {AGENT_LOOK[agent]?.name}.</p>

          <div
            className="relative mt-4"
            onKeyDown={(e) => e.key === "Escape" && setQuery("")}
            onBlur={(e) => !e.currentTarget.contains(e.relatedTarget as Node | null) && setQuery("")}
          >
            <Field
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar nota no Cérebro para ligar"
              aria-label="Buscar nota para ligar"
              aria-expanded={!!hits}
              aria-controls="ctx-hits"
            />
            {hits && (
              <ul id="ctx-hits" className="animate-enter absolute inset-x-0 top-full z-20 mt-1.5 max-h-72 overflow-y-auto rounded-r3 border border-hairline-hi bg-glass-hi p-1 shadow-[0_18px_40px_-12px_rgb(0_0_0/0.45)] backdrop-blur-2xl">
                {hits.length === 0 ? (
                  <li className="px-3 py-2 text-sm text-fg-muted">Nenhuma nota com esse termo.</li>
                ) : (
                  hits.map((h) => {
                    const linked = has.has(h.title.toLowerCase());
                    return (
                      <li key={h.rel}>
                        <button
                          type="button"
                          disabled={linked || links.length >= MAX_LINKS}
                          onClick={() => (add(h), setQuery(""))}
                          className="flex w-full items-start gap-2.5 rounded-r2 px-2.5 py-2 text-left transition-colors hover:bg-row-hover disabled:opacity-60"
                        >
                          <Icon name={linked ? "check-circle" : "plus"} size={15} className={cn("mt-0.5 shrink-0", linked ? "text-ok-ink" : "text-fg-muted")} />
                          <span className="min-w-0">
                            <span className="block text-sm font-medium text-fg">{h.title}</span>
                            <span className="block truncate text-xs text-fg-muted">{h.rel.replace(/\.md$/, "")}</span>
                          </span>
                        </button>
                      </li>
                    );
                  })
                )}
              </ul>
            )}
          </div>

          {links.length === 0 ? (
            <p className="mt-4 rounded-r3 border border-dashed border-hairline-hi p-4 text-center text-sm text-fg-muted">
              Nenhuma nota ligada. Busque acima: playbooks, notas suas, glossários do seu trabalho.
            </p>
          ) : (
            <ul className="mt-4 grid gap-2 sm:grid-cols-2">
              {links.map((l) => (
                <li key={l.title} className={cn("flex items-center gap-2.5 rounded-r3 border px-3 py-2.5", l.rel ? "border-hairline bg-surface/40" : "border-warn/40 bg-warn/10")}>
                  <Icon name={l.rel ? "file-text" : "alert-triangle"} size={16} className={cn("shrink-0", l.rel ? "text-fg-muted" : "text-warn-ink")} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-fg">{l.title}</span>
                    <span className="block truncate text-xs text-fg-muted">{l.rel ? l.rel.replace(/\.md$/, "") : "Nota não encontrada: não entra no prompt"}</span>
                  </span>
                  <button
                    type="button"
                    aria-label={`Desligar ${l.title}`}
                    onClick={() => setLinks((x) => x.filter((y) => y.title !== l.title))}
                    className="grid size-7 shrink-0 place-items-center rounded-full text-fg-muted transition-colors hover:bg-hover hover:text-fg"
                  >
                    <Icon name="x" size={13} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </GlassPanel>

        <GlassPanel className="p-5">
          <label htmlFor="ctx-extra" className="flex items-center gap-2 text-md font-semibold text-fg">
            <Icon name="file-text" size={16} className="text-fg-muted" /> Contexto extra
          </label>
          <p className="mt-1 text-sm text-fg-muted">Fatos que ele deve saber sempre: nomes de pastas, sistemas que você usa, padrões do seu trabalho.</p>
          <textarea
            id="ctx-extra"
            value={extra}
            maxLength={MAX_EXTRA}
            disabled={!memory.writable}
            onChange={(e) => setExtra(e.target.value)}
            rows={6}
            placeholder={"Ex.: Minhas planilhas ficam em Documentos/Financeiro.\nRelatórios mensais fecham no dia 5."}
            className="mt-3 w-full select-text resize-y rounded-r3 border border-hairline bg-surface p-3.5 text-md leading-relaxed text-fg outline-none placeholder:text-fg-subtle focus:border-accent/45"
          />
          <p className="mt-1.5 text-right text-xs tabular-nums text-fg-muted">
            {extra.length}/{MAX_EXTRA}
          </p>
        </GlassPanel>

        <div className="flex flex-wrap items-center gap-3">
          <p className="flex-1 text-sm text-fg-muted" aria-live="polite">
            {error ? <span className="text-bad-ink">{error}</span> : state === "saved" ? "Contexto salvo. Vale a partir do próximo pedido." : dirty ? "Alterações não salvas" : ""}
          </p>
          <Button
            variant="ghost"
            disabled={!dirty}
            onClick={() => {
              setLinks(memory.links);
              setExtra(memory.extra);
            }}
          >
            Descartar
          </Button>
          <Button variant="primary" icon="save" disabled={!dirty || !memory.writable || state === "saving"} onClick={() => void save()}>
            {state === "saving" ? <Spinner size={12} /> : null} Salvar contexto
          </Button>
        </div>
      </div>

      <aside className="space-y-4">
        <GlassPanel className="p-4" raised={false}>
          <p className="flex items-center gap-2 text-sm font-medium text-fg">
            <Icon name="eye" size={14} /> O que vai para o prompt
          </p>
          {preview ? (
            <pre className="mt-2.5 max-h-72 overflow-auto whitespace-pre-wrap rounded-r2 bg-surface/60 p-3 font-mono text-[11.5px] leading-relaxed text-fg">{preview}</pre>
          ) : (
            <p className="mt-2 text-sm text-fg-muted">Nada por enquanto.</p>
          )}
          <p className="mt-2.5 text-xs leading-relaxed text-fg-muted">Até 1.400 caracteres por pedido, junto com as regras e as suas instruções. Notas longas entram resumidas.</p>
        </GlassPanel>
        <GlassPanel className="p-4" raised={false}>
          <p className="flex items-center gap-2 text-sm font-medium text-fg">
            <Icon name="shield-check" size={14} /> Seguro por padrão
          </p>
          <p className="mt-1.5 text-sm text-fg-muted">Notas ligadas são referência. Elas não dão novas ferramentas ao agente nem passam por cima das políticas.</p>
        </GlassPanel>
      </aside>
    </div>
  );
}
