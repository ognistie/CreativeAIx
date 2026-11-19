import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AppDialog, AppMenu, Button, Chip, EmptyState, Field, Icon, IconButton, Segmented, Skeleton } from "../components/ui";
import { core, openExternal } from "../lib/host";
import { BranchExplorer } from "../components/BranchExplorer";

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
// Pasta aberta na arvore: sair do Cerebro e voltar retoma o mesmo lugar
let cachedBranch = "";

export function BrainView() {
  const [ov, setOv] = useState<Overview | null>(cachedOverview);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [filter, setFilter] = useState<Filter>("tudo");
  const [branch, setBranchState] = useState(cachedBranch);
  const setBranch = useCallback((next: string) => { cachedBranch = next; setBranchState(next); }, []);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Array<{ rel: string; title: string; snippet: string }> | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>(cachedSuggestions);
  const [note, setNote] = useState<Opened | null>(null);
  const [returnTo, setReturnTo] = useState<string>();
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [mode, setMode] = useState<Mode>("ler");
  const [draft, setDraft] = useState("");
  const [mapFocus, setMapFocus] = useState("");
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
    let current = true;
    const timer = window.setTimeout(() => {
      void call(core().call("brainSearch", query)).then((r) => {
        if (current) setResults(r.ok ? ((r.items ?? r.data) as typeof results) ?? [] : []);
      });
    }, 220);
    return () => { current = false; window.clearTimeout(timer); };
  }, [query]);

  const open = useCallback(
    async (rel: string) => {
      if (dirty && note) await save(true);
      const r = await call(core().call("brainRead", rel));
      if (!r.ok) return setError(r.error || "");
      const o = { ...(r as unknown as Opened), text: String(r.text ?? ""), links: toLinks(r.links), backlinks: toLinks(r.backlinks) };
      setReturnTo(rel);
      setNote(o);
      // Voltar da nota mostra a pasta dela na arvore (mesmo aberta pela busca ou pelo mapa)
      if (filter === "tudo") setBranch(parentOf(rel));
      setQuery("");
      setResults(null);
      setMapFocus("");
      setDraft(o.text);
      setSuggestion(null);
      setMode((m) => (m === "mapa" ? "ler" : m));
      setError("");
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [dirty, note, filter],
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
        <Skeleton className="h-full flex-1 rounded-r4" />
      </div>
    );
  }

  const goOverview = () => {
    setNote(null);
    setSuggestion(null);
    setMode("ler");
  };

  return (
    <div className="flex h-full gap-3 px-4 pb-4 pt-1">
      {/* Visao geral / leitura / edicao / mapa */}
      <section className="brain-panel brain-content flex min-h-0 min-w-0 flex-1 flex-col">
        {error && <p className="m-4 mb-0 rounded-r2 bg-bad/10 p-3 text-sm text-bad-ink">{error}</p>}
        <div className="brain-toolbar">
          <div className="relative min-w-44 flex-1">
            <Field ref={searchRef} value={query} onChange={(event) => { setResults(null); setQuery(event.target.value); }}
              placeholder="Buscar notas" aria-label="Buscar no cérebro" className="h-8 text-sm"
              onKeyDown={(event) => { if (event.key === "Escape") setQuery(""); }} />
            {query.trim() && <ul aria-label="Resultados da busca" className="brain-search-results">
              {!results || !results.length ? <li>{results ? "Nenhuma nota encontrada" : "Buscando…"}</li> : results.map((item) => (
                <li key={item.rel}><button type="button" onClick={() => void open(item.rel)}>
                  <strong>{item.title}</strong>
                  {item.snippet && <span className="line-clamp-2 text-xs text-fg-muted">{item.snippet}</span>}
                </button></li>
              ))}
            </ul>}
          </div>
          <Button size="compact" icon="network" onClick={() => setMode("mapa")}>Mapa</Button>
          <Button size="compact" icon="plus" disabled={!ov.writable} onClick={() => { setNameField(""); setFolderField(branch); setDialog("note"); }}>Nova nota</Button>
          <AppMenu trigger={<IconButton icon="more" label="Opções do Cérebro" />} items={[
            ...(ov.writable ? [{ label: "Nova pasta", icon: "folder-plus" as const, onSelect: () => { setNameField(branch ? branch + "/" : ""); setDialog("folder"); } }] : []),
            { label: "Abrir no Explorer", icon: "folder-open", onSelect: () => void core().call("openBrainFolder") },
          ]} />
        </div>
        {suggestion ? (
          <SuggestionPanel key={suggestion.id} s={suggestion} onDecide={decide} onBack={goOverview} />
        ) : !note && mode !== "mapa" ? (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="brain-filters">
              <Chip selected={filter === "tudo"} onClick={() => { setFilter("tudo"); setBranch(""); }}>Todas</Chip>
              <Chip selected={filter === "meus"} onClick={() => { setFilter("meus"); setBranch(""); }}>Minhas notas</Chip>
              {ov.removed.length > 0 && <Chip selected={filter === "ocultas"} onClick={() => setFilter("ocultas")}>Ocultas</Chip>}
              {suggestions.length > 0 && <Chip selected={filter === "sugestoes"} onClick={() => setFilter("sugestoes")}>Sugestões · {suggestions.length}</Chip>}
            </div>
            {filter === "sugestoes" ? <ul className="brain-utility-list">
              {suggestions.map((item) => <li key={item.id}><Button icon="sparkle" onClick={() => setSuggestion(item)}>{item.title}</Button></li>)}
            </ul> : filter === "ocultas" ? <ul className="brain-utility-list">
              {ov.removed.map((rel) => <li key={rel}><Button icon="undo" disabled={!ov.writable} onClick={async () => {
                const result = await call(core().call("brainRestore", rel));
                if (!result.ok) return setError(result.error || "Não foi possível restaurar.");
                say("Nota restaurada");
                reload();
              }}>Restaurar {titleOf(rel)}</Button></li>)}
            </ul> : (
              <BranchExplorer branch={branch} onBranch={setBranch} folders={filter === "tudo" ? ov.folders : []}
                notes={filter === "tudo" ? ov.notes : ov.notes.filter((item) => item.layer !== "base")}
                folderLabel={cleanFolder} returnTo={returnTo} onOpen={(rel) => void open(rel)} />
            )}
          </div>
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
                    <h1 className="truncate font-display text-[22px] font-medium tracking-[-0.02em] text-fg">{mapFocus || note ? `Ligações de ${titleOf(mapFocus || note!.rel)}` : "Notas mais ligadas"}</h1>
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
                <BrainMap graph={graph} current={mapFocus || note?.rel} onOpen={(rel) => void open(rel)} onFocus={setMapFocus} />
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
        <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(min(220px,100%),1fr))]">
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
      <g key={`${side}:${id}`} className="brain-map-node" role="button" tabIndex={0} aria-label={`${side === "c" ? "Ler" : "Centralizar"} ${title.get(id) ?? id}`}
        onClick={() => (side === "c" ? onOpen(id) : onFocus(id))}
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          if (side === "c") onOpen(id);
          else onFocus(id);
        }}>
        <title>{title.get(id) ?? id}</title>
        <rect x={x0} y={y - 15} width={w} height={30} rx={15} fill={side === "c" ? "var(--primary)" : "var(--bg-surface-hi)"} stroke={side === "c" ? "none" : "var(--hairline-hi)"} />
        <text x={x0 + w / 2} y={y + 4.5} textAnchor="middle" fontSize={side === "c" ? 13 : 12} fontWeight={side === "c" ? 600 : 500} fill={side === "c" ? "var(--text-inverse)" : "var(--text-primary)"}>
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
        <>
        <div className="brain-map-compact">
          <Button icon="file-text" onClick={() => onOpen(current)}>Ler nota central</Button>
          {[{ name: "Citam esta nota", ids: inn }, { name: "Esta nota cita", ids: out }].filter((branch) => branch.ids.length).map((branch) => (
            <section key={branch.name}>
              <h2>{branch.name}</h2>
              {branch.ids.slice(0, MAX).map((id) => <button key={id} type="button" onClick={() => onFocus(id)}>{title.get(id) ?? titleOf(id)}</button>)}
            </section>
          ))}
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} className="brain-map-art w-full" role="group" aria-label={`Ligações de ${label(current)}`}>
          {right.map((p) => (
            <path key={`o:${p.id}`} d={`M${cx + 60},${cy} C${cx + 160},${cy} ${p.x - 140},${p.y} ${p.x - 20},${p.y}`} fill="none" stroke="var(--accent)" strokeOpacity={0.8} strokeWidth={3} strokeDasharray="1 5" strokeLinecap="round" />
          ))}
          {left.map((p) => (
            <path key={`i:${p.id}`} d={`M${p.x + 20},${p.y} C${p.x + 140},${p.y} ${cx - 160},${cy} ${cx - 60},${cy}`} fill="none" stroke="var(--text-secondary)" strokeOpacity={0.6} strokeWidth={2.5} strokeDasharray="1 5" strokeLinecap="round" />
          ))}
          {right.map((p) => pill(p.id, p.x, p.y, "r"))}
          {left.map((p) => pill(p.id, p.x, p.y, "l"))}
          {pill(current, cx, cy, "c")}
        </svg>
        </>
      )}
      {(out.length > MAX || inn.length > MAX) && <p className="mt-2 text-xs text-fg-muted">Mostrando as {MAX} primeiras de cada lado.</p>}
    </div>
  );
}
