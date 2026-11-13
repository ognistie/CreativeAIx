import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AppDialog, AppMenu, Button, Chip, EmptyState, Field, Icon, IconButton, Segmented, Skeleton } from "../components/ui";
import { cn } from "../lib/cn";
import { core, openExternal } from "../lib/tauri";
import { IntroCard } from "../components/IntroCard";

// BrainView.qml: o segundo cerebro. Arvore de notas (fabrica, editadas, suas), leitura em markdown,
// edicao com [[ligacoes]], mapa, ligacoes e mencoes, e as sugestoes que os agentes propoem.
// Toda escrita vai para a camada pessoal (core/brain_store.py): o vault do repositorio nunca muda.

interface Note {
  rel: string;
  title: string;
  folder: string;
  layer: "base" | "editada" | "pessoal";
}

interface Overview {
  personal: string;
  writable: boolean;
  notes: Note[];
  folders: string[];
  removed: string[];
  edited: number;
}

interface Opened {
  rel: string;
  text: string;
  layer: string;
  links: string[];
  backlinks: string[];
}

interface Suggestion {
  id: string;
  kind: "licao" | "procedimento";
  title: string;
  evidence: string;
  body: string;
  hint: string;
}

type Filter = "tudo" | "meus" | "ocultas" | "sugestoes";
type Mode = "ler" | "editar" | "mapa";
type Reply = { ok: boolean; error?: string } & Record<string, unknown>;

const call = (p: Promise<unknown>) => p.then((r) => r as Reply).catch((e: Error) => ({ ok: false, error: e.message }) as Reply);
const fold = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
const titleOf = (rel: string) => rel.split("/").pop()!.replace(/\.md$/, "");
const parentOf = (p: string) => (p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : "");
const LAYER: Record<string, string> = { editada: "Editada por você", pessoal: "Sua nota", base: "De fábrica" };

/** Markdown do vault para leitura: tira o frontmatter, o titulo repetido e vira [[ligacoes]] em links. */
export function previewMarkdown(md: string, rel: string): string {
  let out = (md || "").replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, "");
  const t = titleOf(rel);
  out = out.replace(/^\s*#\s+(.+)\n/, (m, h: string) => (fold(h) === fold(t) ? "" : m));
  out = out.replace(/\[\[([^[\]|#]+)(#[^[\]|]*)?(\|([^[\]]*))?\]\]/g, (_m, target: string, _h, _a, alias?: string) => `[${alias || target}](nota:${encodeURIComponent(target.trim())})`);
  return out.replace(/^>\s*\[!(\w+)\]\s*/gm, "> **$1** · ");
}

export function BrainView({ onOpenYou }: { onOpenYou?: () => void }) {
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [filter, setFilter] = useState<Filter>("tudo");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Array<{ rel: string; title: string; snippet: string }> | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [note, setNote] = useState<Opened | null>(null);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [mode, setMode] = useState<Mode>("ler");
  const [draft, setDraft] = useState("");
  const [graph, setGraph] = useState<{ nodes: Array<{ id: string; title: string }>; edges: Array<{ from: string; to: string }> } | null>(null);
  const [dialog, setDialog] = useState<"" | "note" | "folder" | "rename" | "delete">("");
  const [nameField, setNameField] = useState("");
  const [folderField, setFolderField] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const dirty = !!note && draft !== note.text;

  const say = (m: string) => {
    setToast(m);
    setTimeout(() => setToast(""), 2600);
  };

  const reload = useCallback(() => {
    void call(core().call("brainOverview")).then((r) => (r.ok ? setOv(r as unknown as Overview) : setError(r.error || "")));
    void call(core().call("suggestionsList")).then((r) => r.ok && setSuggestions((r.items as Suggestion[]) ?? []));
  }, []);
  useEffect(reload, [reload]);

  useEffect(() => {
    if (mode === "mapa" && !graph) void call(core().call("brainGraph")).then((r) => r.ok && setGraph(r as never));
  }, [mode, graph]);

  useEffect(() => {
    if (!query.trim()) {
      setResults(null);
      return;
    }
    const t = setTimeout(() => {
      void call(core().call("brainSearch", query)).then((r) => setResults(r.ok ? ((r.items ?? r.data) as never) ?? [] : []));
    }, 220);
    return () => clearTimeout(t);
  }, [query]);

  const open = useCallback(
    async (rel: string) => {
      if (dirty && note) await save(true);
      const r = await call(core().call("brainRead", rel));
      if (!r.ok) return setError(r.error || "");
      const o = r as unknown as Opened;
      setNote(o);
      setDraft(o.text);
      setSuggestion(null);
      setMode((m) => (m === "mapa" ? "ler" : m));
      setError("");
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [dirty, note],
  );

  const openByTitle = (title: string) => {
    const hit = ov?.notes.find((n) => fold(n.title) === fold(title));
    if (hit) void open(hit.rel);
    else say(`Nota “${title}” não existe ainda`);
  };

  async function save(quiet = false) {
    if (!note) return;
    const r = await call(core().call("brainSave", note.rel, draft));
    if (!r.ok) return setError(r.error || "Não salvou.");
    const again = await call(core().call("brainRead", note.rel));
    if (again.ok) setNote(again as unknown as Opened);
    if (!quiet) say("Salvo");
    reload();
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key.toLowerCase() === "s" && dirty) {
        e.preventDefault();
        void save();
      } else if (e.ctrlKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const rows = useMemo(() => buildRows(ov, filter, expanded, suggestions), [ov, filter, expanded, suggestions]);

  const decide = async (approve: boolean, title: string, body: string) => {
    if (!suggestion) return;
    const r = await call(approve ? core().call("suggestionApprove", suggestion.id, title, body) : core().call("suggestionDismiss", suggestion.id));
    if (!r.ok) return setError(r.error || "");
    setSuggestion(null);
    say(approve ? "Aprovada: os agentes passam a usar" : "Recusada");
    reload();
  };

  const createNote = async () => {
    const folder = folderField.trim().replace(/^\/+|\/+$/g, "");
    const rel = `${folder ? `${folder}/` : ""}${nameField.trim()}.md`;
    const r = await call(core().call("brainCreate", rel, ""));
    if (!r.ok) return setError(r.error || "");
    setDialog("");
    reload();
    void open((r.rel as string) || rel);
    setMode("editar");
  };

  const createFolder = async () => {
    const r = await call(core().call("brainCreateFolder", nameField.trim()));
    if (!r.ok) return setError(r.error || "");
    setDialog("");
    say("Pasta criada");
    reload();
  };

  const rename = async () => {
    if (!note) return;
    const folder = parentOf(note.rel);
    const r = await call(core().call("brainRename", note.rel, `${folder ? `${folder}/` : ""}${nameField.trim()}.md`));
    if (!r.ok) return setError(r.error || "");
    setDialog("");
    reload();
    void open((r.rel as string) || `${folder ? `${folder}/` : ""}${nameField.trim()}.md`);
  };

  const remove = async () => {
    if (!note) return;
    const r = await call(core().call("brainDelete", note.rel));
    if (!r.ok) return setError(r.error || "");
    setDialog("");
    setNote(null);
    say("Nota removida");
    reload();
  };

  if (!ov) {
    return (
      <div className="grid h-full grid-cols-[280px_1fr] gap-4 p-6 pt-14">
        <Skeleton className="h-full rounded-r3" />
        <Skeleton className="h-full rounded-r3" />
      </div>
    );
  }

  return (
    <div className="grid h-full grid-cols-[240px_1fr] xl:grid-cols-[270px_1fr_230px]">
      {/* Arvore */}
      <aside className="flex min-h-0 flex-col border-r border-hairline px-3 pb-3 pt-14">
        <Field ref={searchRef} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar no cérebro · Ctrl+K" aria-label="Buscar no cérebro" className="mb-2 h-9 text-sm" />
        {!results && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            <Chip selected={filter === "tudo"} onClick={() => setFilter("tudo")}>
              Tudo
            </Chip>
            <Chip selected={filter === "meus"} onClick={() => setFilter("meus")}>
              Minhas
            </Chip>
            {ov.removed.length > 0 && (
              <Chip selected={filter === "ocultas"} onClick={() => setFilter("ocultas")}>
                Ocultas
              </Chip>
            )}
            {suggestions.length > 0 && (
              <Chip selected={filter === "sugestoes"} onClick={() => setFilter("sugestoes")}>
                Sugestões · {suggestions.length}
              </Chip>
            )}
          </div>
        )}
        <ul className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1 text-[13px]">
          {results ? (
            results.length === 0 ? (
              <li className="px-2 py-3 text-fg-subtle">Nada encontrado</li>
            ) : (
              results.map((r) => (
                <li key={r.rel}>
                  <button type="button" onClick={() => void open(r.rel)} className="w-full rounded-r2 px-2 py-1.5 text-left hover:bg-hover">
                    <span className="block truncate text-fg">{r.title}</span>
                    {r.snippet && <span className="line-clamp-2 text-xs text-fg-subtle">{r.snippet}</span>}
                  </button>
                </li>
              ))
            )
          ) : (
            rows.map((row) => <TreeRow key={row.key} row={row} current={note?.rel} sid={suggestion?.id} onToggle={(p) => setExpanded((e) => ({ ...e, [p]: !e[p] }))} onOpen={(rel) => void open(rel)} onSuggestion={(id) => setSuggestion(suggestions.find((s) => s.id === id) ?? null)} onRestore={async (rel) => { const r = await call(core().call("brainRestore", rel)); if (r.ok) { say("Nota restaurada"); reload(); } }} />)
          )}
        </ul>
        <div className="mt-2 flex gap-1.5 border-t border-hairline pt-3">
          <Button size="compact" variant="primary" icon="plus" disabled={!ov.writable} onClick={() => { setNameField(""); setFolderField(""); setDialog("note"); }}>
            Nova nota
          </Button>
          <Button size="compact" icon="folder-plus" disabled={!ov.writable} onClick={() => { setNameField(""); setDialog("folder"); }}>
            Pasta
          </Button>
          <IconButton icon="folder-open" label="Abrir a pasta do cérebro no Explorer" flat className="ml-auto size-[30px]" onClick={() => void core().call("openBrainFolder")} />
        </div>
      </aside>

      {/* Leitura / edicao / mapa */}
      <section className="flex min-h-0 min-w-0 flex-col">
        {error && <p className="m-4 mb-0 rounded-r2 bg-bad/10 p-3 text-sm text-bad">{error}</p>}
        {suggestion ? (
          <SuggestionPanel key={suggestion.id} s={suggestion} onDecide={decide} />
        ) : !note && mode !== "mapa" ? (
          <Welcome ov={ov} onOpenYou={onOpenYou} onMap={() => setMode("mapa")} />
        ) : (
          <>
            <header className="flex flex-wrap items-center gap-3 px-8 pb-3 pt-12">
              <div className="min-w-[200px] flex-1">
                {note && mode !== "mapa" && (
                  <>
                    <p className="text-xs text-fg-subtle">
                      {parentOf(note.rel) || "Raiz"} · {LAYER[note.layer] ?? note.layer}
                      {dirty && " · não salvo"}
                    </p>
                    <h1 className="truncate font-display text-[26px] font-medium tracking-[-0.03em] text-fg">{titleOf(note.rel)}</h1>
                  </>
                )}
              </div>
              <Segmented
                label="Modo"
                value={mode}
                onValueChange={setMode}
                options={[
                  { value: "ler", label: "Ler", icon: "eye" },
                  { value: "editar", label: "Editar", icon: "edit" },
                  { value: "mapa", label: "Mapa", icon: "link" },
                ]}
              />
              {note && mode !== "mapa" && (
                <>
                  {dirty && (
                    <Button size="compact" variant="primary" icon="save" onClick={() => void save()}>
                      Salvar
                    </Button>
                  )}
                  <AppMenu
                    trigger={<IconButton icon="more" label="Ações da nota" />}
                    items={[
                      { label: "Renomear", icon: "edit", onSelect: () => { setNameField(titleOf(note.rel)); setDialog("rename"); } },
                      ...(note.layer === "editada" ? [{ label: "Restaurar original de fábrica", icon: "refresh" as const, onSelect: async () => { const r = await call(core().call("brainRestore", note.rel)); if (r.ok) { say("Original restaurado"); reload(); void open(note.rel); } } }] : []),
                      { label: "Inserir ligação [[ ]]", icon: "link", onSelect: () => { setMode("editar"); setDraft((d) => `${d}[[]]`); } },
                      "separator",
                      { label: "Remover nota…", icon: "x", danger: true, onSelect: () => setDialog("delete") },
                    ]}
                  />
                </>
              )}
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto px-8 pb-10">
              {mode === "mapa" ? (
                <BrainMap graph={graph} current={note?.rel} onOpen={(rel) => { void open(rel); setMode("ler"); }} />
              ) : mode === "editar" ? (
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Escreva aqui. Use [[Nome da nota]] para ligar ideias."
                  aria-label="Texto da nota"
                  disabled={!ov.writable}
                  className="h-full min-h-[50vh] w-full select-text resize-none rounded-r3 border border-hairline bg-surface p-4 font-mono text-[13px] leading-relaxed text-fg outline-none focus:border-accent/45"
                />
              ) : (
                note && <Markdown md={previewMarkdown(draft, note.rel)} onNote={openByTitle} />
              )}
            </div>
          </>
        )}
      </section>

      {/* Ligacoes */}
      <aside className="hidden min-h-0 overflow-y-auto border-l border-hairline px-4 pb-6 pt-14 xl:block">
        {note && !suggestion && (
          <>
            <LinkList title="Liga para" empty="Nenhuma ligação. Use [[ ]] no texto." items={note.links} onOpen={openByTitle} />
            <LinkList title="Mencionada em" empty="Nenhuma nota cita esta ainda." items={note.backlinks} onOpen={(x) => (x.endsWith(".md") ? void open(x) : openByTitle(x))} />
          </>
        )}
      </aside>

      {toast && (
        <div role="status" className="animate-enter fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-primary px-4 py-2 text-[13px] text-fg-inverse shadow-lg">
          {toast}
        </div>
      )}

      <AppDialog
        open={dialog === "note"}
        onOpenChange={(o) => !o && setDialog("")}
        title="Nova nota"
        actions={
          <>
            <Button variant="ghost" onClick={() => setDialog("")}>
              Cancelar
            </Button>
            <Button variant="primary" disabled={!nameField.trim()} onClick={() => void createNote()}>
              Criar
            </Button>
          </>
        }
      >
        <label className="mb-1 block text-sm text-fg-muted">Pasta</label>
        <Field list="brain-folders" value={folderField} onChange={(e) => setFolderField(e.target.value)} placeholder="Raiz do cérebro (ou digite uma pasta nova)" />
        <datalist id="brain-folders">
          {ov.folders.map((f) => (
            <option key={f} value={f} />
          ))}
        </datalist>
        <label className="mb-1 mt-3 block text-sm text-fg-muted">Nome</label>
        <Field value={nameField} onChange={(e) => setNameField(e.target.value)} placeholder="Nome da nota" autoFocus />
      </AppDialog>
      <AppDialog
        open={dialog === "folder"}
        onOpenChange={(o) => !o && setDialog("")}
        title="Nova pasta"
        actions={
          <>
            <Button variant="ghost" onClick={() => setDialog("")}>
              Cancelar
            </Button>
            <Button variant="primary" disabled={!nameField.trim()} onClick={() => void createFolder()}>
              Criar
            </Button>
          </>
        }
      >
        <Field value={nameField} onChange={(e) => setNameField(e.target.value)} placeholder="Ex.: Projetos/Ideias" autoFocus />
      </AppDialog>
      <AppDialog
        open={dialog === "rename"}
        onOpenChange={(o) => !o && setDialog("")}
        title="Renomear nota"
        description="As ligações [[ ]] para ela continuam valendo pelo nome novo."
        actions={
          <>
            <Button variant="ghost" onClick={() => setDialog("")}>
              Cancelar
            </Button>
            <Button variant="primary" disabled={!nameField.trim()} onClick={() => void rename()}>
              Renomear
            </Button>
          </>
        }
      >
        <Field value={nameField} onChange={(e) => setNameField(e.target.value)} autoFocus />
      </AppDialog>
      <AppDialog
        open={dialog === "delete"}
        onOpenChange={(o) => !o && setDialog("")}
        title="Remover nota"
        description={note ? `“${titleOf(note.rel)}” sai do cérebro e os agentes deixam de usá-la. Notas de fábrica podem ser restauradas em Ocultas.` : ""}
        actions={
          <>
            <Button variant="ghost" onClick={() => setDialog("")}>
              Cancelar
            </Button>
            <Button variant="danger" onClick={() => void remove()}>
              Remover
            </Button>
          </>
        }
      />
    </div>
  );
}

type Row =
  | { key: string; kind: "folder"; path: string; title: string; depth: number; open: boolean; count: number }
  | { key: string; kind: "note"; rel: string; title: string; layer: string; depth: number }
  | { key: string; kind: "hidden"; rel: string; title: string; depth: number }
  | { key: string; kind: "suggestion"; sid: string; title: string; depth: number };

function buildRows(ov: Overview | null, filter: Filter, expanded: Record<string, boolean>, suggestions: Suggestion[]): Row[] {
  if (!ov) return [];
  if (filter === "sugestoes") return suggestions.map((x) => ({ key: x.id, kind: "suggestion", sid: x.id, depth: 0, title: `${x.kind === "licao" ? "Lição" : "Procedimento"} · ${x.title}` }));
  if (filter === "ocultas") return ov.removed.map((r) => ({ key: r, kind: "hidden", rel: r, title: titleOf(r), depth: 0 }));
  const list = ov.notes.filter((n) => filter === "tudo" || n.layer !== "base");
  const byFolder = new Map<string, Note[]>();
  for (const n of list) byFolder.set(n.folder, [...(byFolder.get(n.folder) ?? []), n]);
  const all = new Set<string>(filter === "tudo" ? ov.folders : []);
  for (const f of byFolder.keys()) for (let p = f; p; p = parentOf(p)) all.add(p);
  const count = new Map<string, number>();
  for (const n of list) for (let p = n.folder; p; p = parentOf(p)) count.set(p, (count.get(p) ?? 0) + 1);
  const out: Row[] = [];
  const walk = (parent: string, depth: number) => {
    const kids = [...all].filter((f) => f && parentOf(f) === parent).sort((a, b) => a.localeCompare(b));
    for (const f of kids) {
      const open = filter === "meus" || expanded[f] === true;
      out.push({ key: `f:${f}`, kind: "folder", path: f, title: f.split("/").pop()!, depth, open, count: count.get(f) ?? 0 });
      if (open) walk(f, depth + 1);
    }
    for (const n of byFolder.get(parent) ?? []) out.push({ key: n.rel, kind: "note", rel: n.rel, title: n.title, layer: n.layer, depth });
  };
  walk("", 0);
  return out;
}

function TreeRow(props: {
  row: Row;
  current?: string;
  sid?: string;
  onToggle: (p: string) => void;
  onOpen: (rel: string) => void;
  onSuggestion: (id: string) => void;
  onRestore: (rel: string) => void;
}) {
  const { row } = props;
  const pad = { paddingLeft: 8 + row.depth * 14 };
  if (row.kind === "folder") {
    return (
      <li>
        <button type="button" aria-expanded={row.open} onClick={() => props.onToggle(row.path)} style={pad} className="flex h-8 w-full items-center gap-1.5 rounded-r2 pr-2 text-left text-fg-muted hover:bg-hover hover:text-fg">
          <Icon name={row.open ? "chevron-down" : "chevron-right"} size={12} />
          <Icon name="folder" size={14} />
          <span className="flex-1 truncate">{row.title}</span>
          <span className="text-xs text-fg-subtle">{row.count}</span>
        </button>
      </li>
    );
  }
  if (row.kind === "hidden") {
    return (
      <li className="flex h-8 items-center gap-2 px-2 text-fg-subtle">
        <Icon name="eye-off" size={14} />
        <span className="flex-1 truncate">{row.title}</span>
        <button type="button" onClick={() => props.onRestore(row.rel)} className="text-xs text-accent hover:underline">
          Restaurar
        </button>
      </li>
    );
  }
  const active = row.kind === "note" ? props.current === row.rel : props.sid === row.sid;
  return (
    <li>
      <button
        type="button"
        onClick={() => (row.kind === "note" ? props.onOpen(row.rel) : props.onSuggestion(row.sid))}
        style={pad}
        className={cn("flex h-8 w-full items-center gap-2 rounded-r2 pr-2 text-left", active ? "bg-row-hover text-fg" : "text-fg-muted hover:bg-hover hover:text-fg")}
      >
        <Icon name={row.kind === "suggestion" ? "sparkle" : "file-text"} size={14} />
        <span className="flex-1 truncate">{row.title}</span>
        {row.kind === "note" && row.layer !== "base" && <span className="size-1.5 rounded-full bg-accent" title={LAYER[row.layer]} />}
      </button>
    </li>
  );
}

function Markdown({ md, onNote }: { md: string; onNote: (title: string) => void }) {
  return (
    <div className="prose-brain max-w-[70ch] select-text text-md leading-relaxed text-fg">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => (url.startsWith("nota:") || /^https?:/.test(url) ? url : "")}
        components={{
          a: ({ href, children }) =>
            href?.startsWith("nota:") ? (
              <button type="button" onClick={() => onNote(decodeURIComponent(href.slice(5)))} className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent">
                {children}
              </button>
            ) : (
              <button type="button" title={href} onClick={() => href && void openExternal(href)} className="text-accent underline decoration-accent/40 underline-offset-2">
                {children}
              </button>
            ),
          h1: ({ children }) => <h2 className="mb-2 mt-6 font-display text-xl font-medium">{children}</h2>,
          h2: ({ children }) => <h3 className="mb-2 mt-6 font-display text-lg font-medium">{children}</h3>,
          h3: ({ children }) => <h4 className="mb-1.5 mt-5 font-medium">{children}</h4>,
          p: ({ children }) => <p className="my-2.5">{children}</p>,
          ul: ({ children }) => <ul className="my-2.5 list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="my-2.5 list-decimal space-y-1 pl-5">{children}</ol>,
          blockquote: ({ children }) => <blockquote className="my-3 rounded-r2 border-l-2 border-accent bg-chip px-4 py-2 text-fg-muted">{children}</blockquote>,
          code: ({ children }) => <code className="rounded-r1 bg-chip px-1 py-0.5 font-mono text-[12.5px]">{children}</code>,
          pre: ({ children }) => <pre className="my-3 overflow-x-auto rounded-r2 bg-surface p-3 font-mono text-[12.5px]">{children}</pre>,
          table: ({ children }) => <table className="my-3 w-full border-collapse text-sm">{children}</table>,
          th: ({ children }) => <th className="border-b border-hairline-hi px-2 py-1.5 text-left font-medium">{children}</th>,
          td: ({ children }) => <td className="border-b border-hairline px-2 py-1.5">{children}</td>,
        }}
      >
        {md}
      </ReactMarkdown>
    </div>
  );
}

function LinkList({ title, empty, items, onOpen }: { title: string; empty: string; items: string[]; onOpen: (x: string) => void }) {
  return (
    <div className="mb-6">
      <p className="mb-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">{title}</p>
      {items.length === 0 ? (
        <p className="text-sm text-fg-subtle">{empty}</p>
      ) : (
        <ul className="space-y-0.5">
          {items.map((x) => (
            <li key={x}>
              <button type="button" onClick={() => onOpen(x)} className="flex w-full items-center gap-2 rounded-r2 px-2 py-1 text-left text-[13px] text-fg-muted hover:bg-hover hover:text-fg">
                <Icon name="link" size={12} />
                <span className="truncate">{titleOf(x)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Welcome({ ov, onOpenYou, onMap }: { ov: Overview; onOpenYou?: () => void; onMap: () => void }) {
  return (
    <div className="h-full overflow-y-auto px-8 pt-12">
      <IntroCard which="brain" />
      <div className="animate-enter mx-auto mt-10 max-w-lg text-center">
        <h1 className="font-display text-[28px] font-medium tracking-[-0.03em] text-fg">Seu segundo cérebro</h1>
        <p className="mt-2 text-md text-fg-muted">
          Os agentes consultam estas notas para planejar cada tarefa. Edite, ligue com [[colchetes duplos]] e crie as suas: o que vem de fábrica nunca é apagado.
        </p>
        <p className="mt-3 text-sm text-fg-subtle">
          {ov.notes.length} notas · {ov.edited} suas ou editadas
        </p>
        <div className="mt-5 flex justify-center gap-2">
          {onOpenYou && (
            <Button variant="primary" icon="user" onClick={onOpenYou}>
              Contar sobre você
            </Button>
          )}
          <Button icon="link" onClick={onMap}>
            Ver o mapa
          </Button>
        </div>
        {ov.personal && <p className="mt-6 break-all text-xs text-fg-subtle">Sua pasta: {ov.personal}</p>}
        {!ov.writable && <p className="mt-2 text-xs text-warn">A pasta do seu cérebro não está disponível: só leitura.</p>}
      </div>
    </div>
  );
}

function SuggestionPanel({ s, onDecide }: { s: Suggestion; onDecide: (approve: boolean, title: string, body: string) => void }) {
  const [title, setTitle] = useState(s.title);
  const [body, setBody] = useState(s.body);
  return (
    <div className="overflow-y-auto px-8 pb-10 pt-12">
      <div className="animate-enter max-w-[70ch]">
        <p className="text-xs uppercase tracking-[0.1em] text-fg-muted">Sugestão · {s.kind === "licao" ? "lição de uma falha" : "procedimento que deu certo"}</p>
        <Field value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Título" className="mt-2 h-11 font-display text-lg" />
        <p className="mt-3 text-sm text-fg-muted">{s.evidence}</p>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={s.hint}
          rows={8}
          aria-label="Texto"
          className="mt-3 w-full select-text resize-y rounded-r3 border border-hairline bg-surface p-4 text-md text-fg outline-none focus:border-accent/45"
        />
        <p className="mt-2 text-sm text-fg-subtle">{s.hint}</p>
        <div className="mt-4 flex gap-2">
          <Button variant="primary" icon="check" disabled={!title.trim() || !body.trim()} onClick={() => onDecide(true, title, body)}>
            Aprovar
          </Button>
          <Button onClick={() => onDecide(false, title, body)}>Recusar</Button>
        </div>
      </div>
    </div>
  );
}

/** NoteMap.qml simplificado: notas num circulo, ligacoes como linhas finas; a atual em destaque. */
function BrainMap({ graph, current, onOpen }: { graph: { nodes: Array<{ id: string; title: string }>; edges: Array<{ from: string; to: string }> } | null; current?: string; onOpen: (rel: string) => void }) {
  if (!graph) return <Skeleton className="h-[60vh] rounded-r3" />;
  if (graph.nodes.length === 0) return <EmptyState icon="link" title="Nada para mapear ainda" />;
  const W = 900;
  const H = 620;
  const degree = new Map<string, number>();
  for (const e of graph.edges) {
    degree.set(e.from, (degree.get(e.from) ?? 0) + 1);
    degree.set(e.to, (degree.get(e.to) ?? 0) + 1);
  }
  const nodes = [...graph.nodes].sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0));
  const pos = new Map(
    nodes.map((n, i) => {
      const ring = i < 8 ? 0.22 : i < 30 ? 0.36 : 0.46;
      const angle = (i / Math.max(1, nodes.length)) * Math.PI * 2 * (i < 8 ? 1 : 3.7);
      return [n.id, { x: W / 2 + Math.cos(angle) * W * ring, y: H / 2 + Math.sin(angle) * H * ring * 1.05 }];
    }),
  );
  const near = new Set(graph.edges.filter((e) => e.from === current || e.to === current).flatMap((e) => [e.from, e.to]));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-[65vh] w-full" role="img" aria-label={`Mapa com ${nodes.length} notas e ${graph.edges.length} ligações`}>
      {graph.edges.map((e, i) => {
        const a = pos.get(e.from);
        const b = pos.get(e.to);
        if (!a || !b) return null;
        const hot = e.from === current || e.to === current;
        return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={hot ? "var(--accent)" : "var(--hairline-hi)"} strokeWidth={hot ? 1.5 : 1} />;
      })}
      {nodes.map((n) => {
        const p = pos.get(n.id)!;
        const deg = degree.get(n.id) ?? 0;
        const hot = n.id === current || near.has(n.id);
        return (
          <g key={n.id} transform={`translate(${p.x},${p.y})`} className="cursor-pointer" onClick={() => onOpen(n.id)}>
            <title>{n.title}</title>
            <circle r={Math.min(12, 4 + deg)} fill={n.id === current ? "var(--accent)" : "var(--bg-surface-hi)"} stroke={hot ? "var(--accent)" : "var(--hairline-hi)"} strokeWidth={2} />
            {(deg >= 3 || hot) && (
              <text y={-Math.min(12, 4 + deg) - 5} textAnchor="middle" fontSize={11} fill={hot ? "var(--text-primary)" : "var(--text-secondary)"}>
                {n.title.length > 22 ? `${n.title.slice(0, 21)}…` : n.title}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
