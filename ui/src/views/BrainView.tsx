import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AppDialog, AppMenu, Button, Chip, EmptyState, Field, Icon, IconButton, Segmented, Skeleton, type IconName } from "../components/ui";
import { cn } from "../lib/cn";
import { core, openExternal } from "../lib/host";
import { IntroCard } from "../components/IntroCard";

// BrainView: o segundo cerebro. Arvore de notas (fabrica, editadas, suas), leitura em markdown,
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
  links: LinkRef[];
  backlinks: LinkRef[];
}

/** Ligacao como o nucleo devolve: `links` = {target, rel|null}, `backlinks` = {rel, title}. */
interface LinkRef {
  label: string;
  rel: string | null;
}

/** Aceita o formato do nucleo e strings soltas; nunca deixa um item invalido chegar na tela. */
export function toLinks(raw: unknown): LinkRef[] {
  if (!Array.isArray(raw)) return [];
  const out: LinkRef[] = [];
  for (const x of raw) {
    if (typeof x === "string") out.push({ label: x.endsWith(".md") ? titleOf(x) : x, rel: x.endsWith(".md") ? x : null });
    else if (x && typeof x === "object") {
      const o = x as { target?: unknown; title?: unknown; rel?: unknown };
      const rel = typeof o.rel === "string" && o.rel ? o.rel : null;
      const label = typeof o.title === "string" ? o.title : typeof o.target === "string" ? o.target : rel ? titleOf(rel) : "";
      if (label) out.push({ label, rel });
    }
  }
  return out;
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
/** "10 Agentes" -> "Agentes": o numero so ordena as pastas no disco. */
export const cleanFolder = (name: string) => name.replace(/^\d+\s+/, "") || name;
const LAYER: Record<string, string> = { editada: "Editada por você", pessoal: "Sua nota", base: "De fábrica" };

/** Markdown do vault para leitura: tira o frontmatter, o titulo repetido e vira [[ligacoes]] em links. */
export function previewMarkdown(md: string, rel: string): string {
  let out = (md || "").replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, "");
  const t = titleOf(rel);
  out = out.replace(/^\s*#\s+(.+)\n/, (m, h: string) => (fold(h) === fold(t) ? "" : m));
  out = out.replace(/\[\[([^[\]|#]+)(#[^[\]|]*)?(\|([^[\]]*))?\]\]/g, (_m, target: string, _h, _a, alias?: string) => `[${alias || target}](nota:${encodeURIComponent(target.trim())})`);
  return out.replace(/^>\s*\[!(\w+)\]\s*/gm, "> **$1** · ");
}

// Ultimo estado visto: voltar ao Cerebro mostra a arvore na hora e atualiza em seguida (a leitura das
// notas leva de 0,1 a 0,8 s no nucleo; antes a tela ficava em esqueleto a cada visita).
let cachedOverview: Overview | null = null;
let cachedSuggestions: Suggestion[] = [];

export function BrainView({ onOpenYou }: { onOpenYou?: () => void }) {
  const [ov, setOv] = useState<Overview | null>(cachedOverview);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [filter, setFilter] = useState<Filter>("tudo");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Array<{ rel: string; title: string; snippet: string }> | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>(cachedSuggestions);
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
    void call(core().call("brainOverview")).then((r) => {
      if (!r.ok) return setError(r.error || "");
      cachedOverview = r as unknown as Overview;
      setOv(cachedOverview);
    });
    void call(core().call("suggestionsList")).then((r) => {
      if (!r.ok) return;
      cachedSuggestions = (r.items as Suggestion[]) ?? [];
      setSuggestions(cachedSuggestions);
    });
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
      const o = { ...(r as unknown as Opened), text: String(r.text ?? ""), links: toLinks(r.links), backlinks: toLinks(r.backlinks) };
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
    if (again.ok) setNote({ ...(again as unknown as Opened), text: String(again.text ?? ""), links: toLinks(again.links), backlinks: toLinks(again.backlinks) });
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
      <div className="flex h-full gap-3 px-4 pb-4 pt-1">
        <Skeleton className="h-full w-[268px] rounded-r4" />
        <Skeleton className="h-full flex-1 rounded-r4" />
      </div>
    );
  }

  const goOverview = () => {
    setNote(null);
    setSuggestion(null);
    setMode("ler");
  };
  const openFolder = (folder: string) => {
    setFilter("tudo");
    setQuery("");
    setExpanded((e) => {
      const next = { ...e };
      for (let p = folder; p; p = parentOf(p)) next[p] = true;
      return next;
    });
  };

  return (
    <div className="flex h-full gap-3 px-4 pb-4 pt-1">
      {/* Arvore */}
      <aside className="brain-panel flex w-[268px] shrink-0 flex-col p-3">
        <label className="relative mb-2 block">
          <Icon name="nav-search" size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle" />
          <Field ref={searchRef} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar notas · Ctrl+K" aria-label="Buscar no cérebro" className="h-9 pl-9 text-sm" />
        </label>
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
              <li className="px-2 py-3 text-fg-muted">Nada encontrado</li>
            ) : (
              results.map((r) => (
                <li key={r.rel}>
                  <button type="button" onClick={() => void open(r.rel)} className="w-full rounded-r2 px-2 py-1.5 text-left hover:bg-hover">
                    <span className="block truncate font-medium text-fg">{r.title}</span>
                    {r.snippet && <span className="line-clamp-2 text-xs text-fg-muted">{r.snippet}</span>}
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

      {/* Visao geral / leitura / edicao / mapa */}
      <section className="brain-panel flex min-h-0 min-w-0 flex-1 flex-col">
        {error && <p className="m-4 mb-0 rounded-r2 bg-bad/10 p-3 text-sm text-bad-ink">{error}</p>}
        {suggestion ? (
          <SuggestionPanel key={suggestion.id} s={suggestion} onDecide={decide} onBack={goOverview} />
        ) : !note && mode !== "mapa" ? (
          <Overview
            ov={ov}
            suggestions={suggestions.length}
            onOpen={(rel) => void open(rel)}
            onFolder={openFolder}
            onSuggestions={() => setFilter("sugestoes")}
            onOpenYou={onOpenYou}
            onMap={() => setMode("mapa")}
            onNew={() => { setNameField(""); setFolderField(""); setDialog("note"); }}
            onSearch={() => searchRef.current?.focus()}
          />
        ) : (
          <>
            <header className="flex flex-wrap items-center gap-3 border-b border-hairline px-6 py-3.5">
              <IconButton icon="arrow-left" label="Voltar para a visão geral" flat className="size-8" onClick={goOverview} />
              <div className="min-w-[200px] flex-1">
                {note && mode !== "mapa" ? (
                  <>
                    <p className="text-xs text-fg-muted">
                      {(parentOf(note.rel) || "Raiz").split("/").map(cleanFolder).join(" › ")} · {LAYER[note.layer] ?? note.layer}
                      {dirty && " · não salvo"}
                    </p>
                    <h1 className="truncate font-display text-[22px] font-medium tracking-[-0.02em] text-fg">{titleOf(note.rel)}</h1>
                  </>
                ) : (
                  <>
                    <p className="text-xs text-fg-muted">Mapa</p>
                    <h1 className="truncate font-display text-[22px] font-medium tracking-[-0.02em] text-fg">{note ? `Ligações de ${titleOf(note.rel)}` : "Notas mais ligadas"}</h1>
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
                  { value: "mapa", label: "Mapa", icon: "network" },
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
                      ...(note.layer === "editada" ? [{ label: "Restaurar original de fábrica", icon: "undo" as const, onSelect: async () => { const r = await call(core().call("brainRestore", note.rel)); if (r.ok) { say("Original restaurado"); reload(); void open(note.rel); } } }] : []),
                      { label: "Inserir ligação [[ ]]", icon: "link", onSelect: () => { setMode("editar"); setDraft((d) => `${d}[[]]`); } },
                      "separator",
                      { label: "Remover nota…", icon: "trash", danger: true, onSelect: () => setDialog("delete") },
                    ]}
                  />
                </>
              )}
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
              {mode === "mapa" ? (
                <BrainMap graph={graph} current={note?.rel} onOpen={(rel) => { void open(rel); setMode("ler"); }} onFocus={(rel) => void open(rel)} />
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

      {/* Ligacoes da nota aberta */}
      {note && !suggestion && mode !== "mapa" && (
        <aside className="brain-panel hidden w-[236px] shrink-0 overflow-y-auto p-4 xl:block">
          <LinkList title="Liga para" empty="Nenhuma ligação. Use [[ ]] no texto." items={note.links} onOpen={(l) => (l.rel ? void open(l.rel) : openByTitle(l.label))} />
          <LinkList title="Mencionada em" empty="Nenhuma nota cita esta ainda." items={note.backlinks} onOpen={(l) => (l.rel ? void open(l.rel) : openByTitle(l.label))} />
        </aside>
      )}

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
          <span className="flex-1 truncate">{cleanFolder(row.title)}</span>
          <span className="rounded-full bg-chip px-1.5 text-[11px] tabular-nums text-fg-muted">{row.count}</span>
        </button>
      </li>
    );
  }
  if (row.kind === "hidden") {
    return (
      <li className="flex h-8 items-center gap-2 px-2 text-fg-subtle">
        <Icon name="eye-off" size={14} />
        <span className="flex-1 truncate">{row.title}</span>
        <button type="button" onClick={() => props.onRestore(row.rel)} className="text-xs text-accent-ink hover:underline">
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
              <button type="button" onClick={() => onNote(decodeURIComponent(href.slice(5)))} className="text-accent-ink underline decoration-accent/40 underline-offset-2 hover:decoration-accent">
                {children}
              </button>
            ) : (
              <button type="button" title={href} onClick={() => href && void openExternal(href)} className="text-accent-ink underline decoration-accent/40 underline-offset-2">
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

function LinkList({ title, empty, items, onOpen }: { title: string; empty: string; items: LinkRef[]; onOpen: (x: LinkRef) => void }) {
  return (
    <div className="mb-6">
      <p className="mb-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">{title}</p>
      {items.length === 0 ? (
        <p className="text-sm text-fg-subtle">{empty}</p>
      ) : (
        <ul className="space-y-0.5">
          {items.map((x, i) => (
            <li key={`${x.rel ?? x.label}:${i}`}>
              <button type="button" onClick={() => onOpen(x)} className={cn("flex w-full items-center gap-2 rounded-r2 px-2 py-1 text-left text-[13px] hover:bg-hover hover:text-fg", x.rel ? "text-fg-muted" : "text-fg-subtle")} title={x.rel ? undefined : "Nota ainda não existe"}>
                <Icon name="link" size={12} />
                <span className="truncate">{x.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const FOLDER_ICON: Record<string, IconName> = {
  maestro: "route", inbox: "box", agentes: "nav-user", politicas: "shield", skills: "sparkle", tarefas: "check-circle",
  execucoes: "play", diario: "nav-journal", aprendizados: "sparkle", dicionario: "book", sistema: "settings", voce: "user",
};
const folderIcon = (name: string): IconName => {
  const key = fold(cleanFolder(name)).split(/\s+/)[0] ?? "";
  return FOLDER_ICON[key] ?? "folder";
};

/** Visao geral: o que tem no cerebro, por pasta, com as notas a um clique. Substitui a tela vazia + mapa. */
function Overview(props: {
  ov: Overview;
  suggestions: number;
  onOpen: (rel: string) => void;
  onFolder: (folder: string) => void;
  onSuggestions: () => void;
  onOpenYou?: () => void;
  onMap: () => void;
  onNew: () => void;
  onSearch: () => void;
}) {
  const { ov } = props;
  const groups = useMemo(() => {
    const by = new Map<string, Note[]>();
    for (const n of ov.notes) {
      const top = n.folder.split("/")[0] || "";
      by.set(top, [...(by.get(top) ?? []), n]);
    }
    return [...by.entries()]
      .filter(([top]) => top)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([top, notes]) => ({
        top,
        notes: [...notes].sort((a, b) => Number(b.layer !== "base") - Number(a.layer !== "base") || a.title.localeCompare(b.title)),
      }));
  }, [ov.notes]);
  const root = ov.notes.filter((n) => !n.folder);
  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      <IntroCard which="brain" />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[26px] font-medium tracking-[-0.02em] text-fg">Seu segundo cérebro</h1>
          <p className="mt-1 max-w-xl text-md text-fg-muted">
            O que os agentes consultam antes de agir. Abra uma pasta, leia, edite ou crie notas: o original de fábrica nunca é apagado.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button icon="nav-search" onClick={props.onSearch}>
            Buscar
          </Button>
          <Button icon="network" onClick={props.onMap}>
            Mapa
          </Button>
          <Button variant="primary" icon="plus" disabled={!ov.writable} onClick={props.onNew}>
            Nova nota
          </Button>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2 text-sm">
        <span className="rounded-full bg-chip px-3 py-1 text-fg">{ov.notes.length} notas</span>
        <span className="rounded-full bg-chip px-3 py-1 text-fg">{ov.edited} suas ou editadas</span>
        {props.suggestions > 0 && (
          <button type="button" onClick={props.onSuggestions} className="press rounded-full bg-accent/15 px-3 py-1 font-medium text-accent-ink hover:bg-accent/25">
            {props.suggestions} {props.suggestions === 1 ? "sugestão para revisar" : "sugestões para revisar"} →
          </button>
        )}
        {props.onOpenYou && (
          <button type="button" onClick={props.onOpenYou} className="press rounded-full bg-chip px-3 py-1 text-fg hover:bg-row-hover">
            Contar sobre você →
          </button>
        )}
      </div>

      <div className="mt-6 grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(240px,1fr))]">
        {groups.map(({ top, notes }, i) => (
          <article key={top} style={{ animationDelay: `calc(var(--stagger) * ${i})` }} className="animate-enter flex flex-col rounded-r3 border border-edge bg-glass-hi p-4">
            <button type="button" onClick={() => props.onFolder(top)} className="group flex items-center gap-2.5 text-left">
              <span className="grid size-8 place-items-center rounded-r2 bg-accent/12 text-accent-ink">
                <Icon name={folderIcon(top)} size={16} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] font-medium text-fg group-hover:underline">{cleanFolder(top)}</span>
                <span className="block text-xs text-fg-muted">
                  {notes.length} {notes.length === 1 ? "nota" : "notas"}
                </span>
              </span>
            </button>
            <ul className="mt-3 space-y-0.5">
              {notes.slice(0, 4).map((n) => (
                <li key={n.rel}>
                  <button type="button" onClick={() => props.onOpen(n.rel)} className="flex w-full items-center gap-2 rounded-r1 px-1.5 py-1 text-left text-[13px] text-fg-muted hover:bg-hover hover:text-fg">
                    <Icon name="file-text" size={13} className="shrink-0" />
                    <span className="truncate">{n.title}</span>
                    {n.layer !== "base" && <span className="ml-auto size-1.5 shrink-0 rounded-full bg-accent" title={LAYER[n.layer]} />}
                  </button>
                </li>
              ))}
            </ul>
            {notes.length > 4 && (
              <button type="button" onClick={() => props.onFolder(top)} className="mt-1 self-start px-1.5 text-xs font-medium text-accent-ink hover:underline">
                Ver as {notes.length}
              </button>
            )}
          </article>
        ))}
        {root.length > 0 && (
          <article className="flex flex-col rounded-r3 border border-edge bg-glass-hi p-4">
            <p className="flex items-center gap-2.5 text-[15px] font-medium text-fg">
              <span className="grid size-8 place-items-center rounded-r2 bg-chip text-fg-muted">
                <Icon name="file-text" size={16} />
              </span>
              Soltas na raiz
            </p>
            <ul className="mt-3 space-y-0.5">
              {root.slice(0, 6).map((n) => (
                <li key={n.rel}>
                  <button type="button" onClick={() => props.onOpen(n.rel)} className="w-full truncate rounded-r1 px-1.5 py-1 text-left text-[13px] text-fg-muted hover:bg-hover hover:text-fg">
                    {n.title}
                  </button>
                </li>
              ))}
            </ul>
          </article>
        )}
      </div>
      {ov.personal && <p className="mt-6 break-all text-xs text-fg-muted">Sua pasta: {ov.personal}</p>}
      {!ov.writable && <p className="mt-2 text-xs text-warn-ink">A pasta do seu cérebro não está disponível: só leitura.</p>}
    </div>
  );
}

function SuggestionPanel({ s, onDecide, onBack }: { s: Suggestion; onDecide: (approve: boolean, title: string, body: string) => void; onBack: () => void }) {
  const [title, setTitle] = useState(s.title);
  const [body, setBody] = useState(s.body);
  return (
    <div className="overflow-y-auto px-6 pb-10 pt-4">
      <button type="button" onClick={onBack} className="mb-3 inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg">
        <Icon name="arrow-left" size={14} /> Visão geral
      </button>
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

type Graph = { nodes: Array<{ id: string; title: string }>; edges: Array<{ from: string; to: string }> };

/** Mapa focado: a nota aberta no centro, o que ela cita a direita e quem a cita a esquerda, cada uma com o nome
 *  inteiro e clicavel. Sem nota aberta, as notas mais ligadas para comecar. Antes o mapa desenhava todas as notas
 *  de uma vez (um emaranhado ilegivel). */
function BrainMap({ graph, current, onOpen, onFocus }: { graph: Graph | null; current?: string; onOpen: (rel: string) => void; onFocus: (rel: string) => void }) {
  if (!graph) return <Skeleton className="h-[60vh] rounded-r3" />;
  if (graph.nodes.length === 0) return <EmptyState icon="network" title="Nada para mapear ainda" />;
  const title = new Map(graph.nodes.map((n) => [n.id, n.title]));
  const degree = new Map<string, number>();
  for (const e of graph.edges) {
    degree.set(e.from, (degree.get(e.from) ?? 0) + 1);
    degree.set(e.to, (degree.get(e.to) ?? 0) + 1);
  }
  if (!current || !title.has(current)) {
    const hubs = [...graph.nodes].sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0)).slice(0, 18);
    return (
      <div>
        <p className="mb-4 text-sm text-fg-muted">Escolha uma nota para ver com quem ela se liga. As mais ligadas primeiro.</p>
        <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(220px,1fr))]">
          {hubs.map((n) => (
            <button key={n.id} type="button" onClick={() => onFocus(n.id)} className="press flex items-center gap-3 rounded-r3 border border-edge bg-glass-hi px-3.5 py-3 text-left hover:border-accent/40">
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent/12 text-xs font-semibold tabular-nums text-accent-ink">{degree.get(n.id) ?? 0}</span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-fg">{n.title}</span>
                <span className="block truncate text-xs text-fg-muted">{cleanFolder(parentOf(n.id).split("/")[0] || "Raiz")}</span>
              </span>
            </button>
          ))}
        </div>
      </div>
    );
  }
  const out = [...new Set(graph.edges.filter((e) => e.from === current && e.to !== current).map((e) => e.to))];
  const inn = [...new Set(graph.edges.filter((e) => e.to === current && e.from !== current).map((e) => e.from))].filter((x) => !out.includes(x));
  const MAX = 14;
  const W = 920;
  const rows = Math.max(Math.min(out.length, MAX), Math.min(inn.length, MAX), 1);
  const H = Math.max(360, rows * 40 + 60);
  const cx = W / 2;
  const cy = H / 2;
  const label = (id: string) => {
    const t = title.get(id) ?? titleOf(id);
    return t.length > 30 ? `${t.slice(0, 29)}…` : t;
  };
  const column = (ids: string[], x: number) => ids.slice(0, MAX).map((id, i, all) => ({ id, x, y: all.length === 1 ? cy : 40 + (i * (H - 80)) / (all.length - 1) }));
  const right = column(out, W - 200);
  const left = column(inn, 200);
  const pill = (id: string, x: number, y: number, side: "l" | "r" | "c") => {
    const text = label(id);
    const w = Math.min(260, 24 + text.length * 7.2);
    const x0 = side === "c" ? x - w / 2 : side === "r" ? x - 20 : x - w + 20;
    return (
      <g key={`${side}:${id}`} className="cursor-pointer" onClick={() => (side === "c" ? onOpen(id) : onFocus(id))}>
        <title>{title.get(id) ?? id}</title>
        <rect x={x0} y={y - 15} width={w} height={30} rx={15} fill={side === "c" ? "var(--accent)" : "var(--bg-glass-hi)"} stroke={side === "c" ? "none" : "var(--hairline-hi)"} />
        <text x={x0 + w / 2} y={y + 4.5} textAnchor="middle" fontSize={side === "c" ? 13 : 12} fontWeight={side === "c" ? 600 : 500} fill={side === "c" ? "#fff" : "var(--text-primary)"}>
          {text}
        </text>
      </g>
    );
  };
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-4 text-xs text-fg-muted">
        <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded bg-accent" /> esta nota cita ({out.length})</span>
        <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded bg-fg-muted" /> citam esta nota ({inn.length})</span>
        <span>Clique numa nota para centralizar · clique no centro para ler</span>
      </div>
      {out.length + inn.length === 0 ? (
        <EmptyState icon="network" title="Esta nota ainda não se liga a nenhuma">Use [[Nome da nota]] no texto para criar ligações.</EmptyState>
      ) : (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: "68vh" }} role="img" aria-label={`Ligações de ${label(current)}`}>
          {right.map((p) => (
            <path key={`o:${p.id}`} d={`M${cx + 60},${cy} C${cx + 160},${cy} ${p.x - 140},${p.y} ${p.x - 20},${p.y}`} fill="none" stroke="var(--accent)" strokeOpacity={0.55} strokeWidth={1.5} />
          ))}
          {left.map((p) => (
            <path key={`i:${p.id}`} d={`M${p.x + 20},${p.y} C${p.x + 140},${p.y} ${cx - 160},${cy} ${cx - 60},${cy}`} fill="none" stroke="var(--text-secondary)" strokeOpacity={0.45} strokeWidth={1.5} />
          ))}
          {right.map((p) => pill(p.id, p.x, p.y, "r"))}
          {left.map((p) => pill(p.id, p.x, p.y, "l"))}
          {pill(current, cx, cy, "c")}
        </svg>
      )}
      {(out.length > MAX || inn.length > MAX) && <p className="mt-2 text-xs text-fg-muted">Mostrando as {MAX} primeiras de cada lado.</p>}
    </div>
  );
}
