import { useEffect, useMemo, useRef, useState } from "react";
import { Prose } from "../../components/Prose";
import { Button, EmptyState, Icon, Skeleton } from "../../components/ui";
import { core, openExternal } from "../../lib/host";
import { cn } from "../../lib/cn";
import { AGENT_LOOK, call } from "./types";
import { AGENT_FOLDERS, noteTitle, type Knowledge } from "./knowledge";

// Conhecimento de um agente no Cerebro: as notas da pasta dele e as que ele usa de outras pastas. Abrir uma nota mostra
// a leitura (com os [[links]] navegaveis), as ligacoes de ida e volta e a edicao. Salvar grava na camada pessoal do
// Cerebro (a de fabrica nunca muda); "Voltar ao original" desfaz a edicao de uma nota de fabrica.

type Note = {
  rel: string; text: string; layer: string;
  links: Array<{ target: string; rel: string | null }>;
  backlinks: Array<{ rel: string; title: string }>;
};

const LAYER: Record<string, string> = { base: "De fábrica", editada: "Editada por você", pessoal: "Sua" };
const stripFrontmatter = (t: string) => t.replace(/^---\n[\s\S]*?\n---\n?/, "");
const wikiToMarkdown = (t: string) =>
  t.replace(/\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]/g, (_, target: string, alias?: string) =>
    `[${alias ?? target}](note:${encodeURIComponent(target.trim())})`);

export function AgentKnowledge({ agent, knowledge, rel, onRel, onDirty, onChanged }: {
  agent: string;
  knowledge: Knowledge;
  rel: string;
  onRel: (rel: string) => void;
  onDirty: (dirty: boolean) => void;
  onChanged: () => void;
}) {
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [createError, setCreateError] = useState("");
  const look = AGENT_LOOK[agent]!;
  const mine = knowledge.agents[agent] ?? { own: [], uses: [] };
  const q = query.trim().toLowerCase();
  const filter = (list: string[]) => list.filter((r) => !q || r.toLowerCase().includes(q));
  const groups = [
    { title: `Da pasta de ${look.name}`, items: filter(mine.own), empty: "Nenhuma nota na pasta deste agente ainda." },
    { title: "Que ele usa de outras pastas", items: filter(mine.uses), empty: "Nenhuma nota ligada de fora." },
  ];

  const create = async () => {
    const title = newTitle.trim().replace(/[\\/:*?"<>|]/g, "").slice(0, 80);
    if (!title) return;
    const target = `${AGENT_FOLDERS[agent]}/${title}.md`;
    const r = await call(core().call("brainCreate", target, `# ${title}\n\n`));
    if (!r.ok) return setCreateError(r.error || "Não deu para criar a nota.");
    setCreating(false);
    setNewTitle("");
    setCreateError("");
    onChanged();
    onRel(String(r.rel || target));
  };

  return (
    <div className="lab-knowledge">
      <aside className="lab-knowledge-list" aria-label={`Notas de ${look.name}`}>
        <label className="lab-knowledge-search">
          <Icon name="search" size={13} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filtrar notas" aria-label="Filtrar notas" />
        </label>
        {groups.map((g) => (
          <section key={g.title}>
            <h3>{g.title} <span>{g.items.length}</span></h3>
            {g.items.length ? (
              <ul>
                {g.items.map((item) => (
                  <li key={item}>
                    <button type="button" aria-current={item === rel ? "true" : undefined} onClick={() => onRel(item)} title={item}>
                      <i style={{ background: knowledge.shared.has(item) ? "#e28aa1" : look.color }} aria-hidden />
                      <span>{noteTitle(item)}</span>
                      {knowledge.shared.has(item) && <small>comum</small>}
                    </button>
                  </li>
                ))}
              </ul>
            ) : <p className="lab-knowledge-empty">{q ? "Nada com esse filtro." : g.empty}</p>}
          </section>
        ))}
        {knowledge.writable && (creating ? (
          <form className="lab-knowledge-new" onSubmit={(e) => { e.preventDefault(); void create(); }}>
            <input autoFocus value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Título da nota" aria-label="Título da nova nota" />
            <div>
              <Button size="compact" variant="ghost" onClick={() => { setCreating(false); setCreateError(""); }}>Cancelar</Button>
              <Button size="compact" variant="primary" type="submit" disabled={!newTitle.trim()}>Criar</Button>
            </div>
            {createError && <p role="alert">{createError}</p>}
          </form>
        ) : (
          <Button size="compact" icon="plus" onClick={() => setCreating(true)}>Nova nota em {look.name}</Button>
        ))}
      </aside>
      <div className="lab-knowledge-note">
        {rel ? <NoteView key={rel} rel={rel} writable={knowledge.writable} onRel={onRel} onDirty={onDirty} onChanged={onChanged} />
          : <EmptyState icon="file" title="Escolha uma nota">Clique numa nota da lista ou num ponto do desenho para ler, seguir as ligações e editar.</EmptyState>}
      </div>
    </div>
  );
}

function NoteView({ rel, writable, onRel, onDirty, onChanged }: {
  rel: string; writable: boolean; onRel: (rel: string) => void; onDirty: (d: boolean) => void; onChanged: () => void;
}) {
  const [note, setNote] = useState<Note | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState("");
  const [reload, setReload] = useState(0);
  const ref = useRef<HTMLElement>(null);
  // Aberta pelo desenho (la em cima): rola ate a nota
  useEffect(() => { if (note) ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [note?.rel]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let active = true;
    setError("");
    void call(core().call("brainRead", rel)).then((r) => {
      if (!active) return;
      if (!r.ok) return setError(r.error || "Não deu para abrir a nota.");
      const n = { rel, text: String(r.text ?? ""), layer: String(r.layer ?? "base"),
        links: (r.links as Note["links"]) ?? [], backlinks: (r.backlinks as Note["backlinks"]) ?? [] };
      setNote(n);
      setDraft(n.text);
    });
    return () => { active = false; };
  }, [rel, reload]);

  const dirty = editing && !!note && draft !== note.text;
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);

  const markdown = useMemo(() => wikiToMarkdown(stripFrontmatter(note?.text ?? "")), [note?.text]);
  const follow = (href: string) => {
    if (!href.startsWith("note:")) return void openExternal(href);
    const target = decodeURIComponent(href.slice(5)).toLowerCase();
    const hit = note?.links.find((l) => l.target.toLowerCase() === target && l.rel);
    if (hit?.rel) onRel(hit.rel);
  };

  const save = async () => {
    if (!note) return;
    setSaving(true);
    const r = await call(core().call("brainSave", rel, draft));
    setSaving(false);
    if (!r.ok) return setError(r.error || "Não deu para salvar.");
    setSaved("Salvo no seu Cérebro.");
    setEditing(false);
    setReload((v) => v + 1);
    onChanged();
  };
  const restore = async () => {
    const r = await call(core().call("brainRestore", rel));
    if (!r.ok) return setError(r.error || "Não deu para voltar ao original.");
    setSaved("Voltou à versão de fábrica.");
    setEditing(false);
    setReload((v) => v + 1);
    onChanged();
  };

  if (error && !note) return <EmptyState icon="alert-circle" title="Nota indisponível">{error}</EmptyState>;
  if (!note) return <div className="space-y-3"><Skeleton className="h-8 w-64 rounded-r2" /><Skeleton className="h-64 rounded-r4" /></div>;

  return (
    <article ref={ref} className="lab-note" aria-label={noteTitle(rel)}>
      <header>
        <div className="min-w-0">
          <h3 className="truncate">{noteTitle(rel)}</h3>
          <p className="truncate">{rel} · <span className={cn("lab-note-layer", `is-${note.layer}`)}>{LAYER[note.layer] ?? note.layer}</span></p>
        </div>
        <span className="flex-1" />
        {editing ? <>
          <Button size="compact" variant="ghost" onClick={() => { setEditing(false); setDraft(note.text); }}>Cancelar</Button>
          <Button size="compact" variant="primary" icon="check" disabled={!dirty || saving} onClick={() => void save()}>{saving ? "Salvando…" : "Salvar"}</Button>
        </> : <>
          {note.layer === "editada" && writable && <Button size="compact" variant="ghost" onClick={() => void restore()}>Voltar ao original</Button>}
          <Button size="compact" icon="edit" disabled={!writable} title={writable ? "" : "O Cérebro pessoal não está disponível para escrita"}
            onClick={() => { setEditing(true); setSaved(""); }}>Editar</Button>
        </>}
      </header>
      {saved && !editing && <p className="lab-note-saved" role="status">{saved}</p>}
      {error && <p className="lab-note-error" role="alert">{error}</p>}
      {editing ? (
        <textarea className="lab-note-editor" value={draft} onChange={(e) => setDraft(e.target.value)} spellCheck={false}
          aria-label={`Texto de ${noteTitle(rel)}`} />
      ) : (
        <div className="lab-note-body"><Prose markdown={markdown || "_Nota vazia._"} onLink={follow} /></div>
      )}
      {(note.links.length > 0 || note.backlinks.length > 0) && (
        <footer>
          {note.links.length > 0 && <div><h4>Cita</h4>{note.links.map((l) => (
            <button key={l.target} type="button" disabled={!l.rel} onClick={() => l.rel && onRel(l.rel)} title={l.rel ? l.rel : "Nota ainda não existe"}>
              {l.target}
            </button>
          ))}</div>}
          {note.backlinks.length > 0 && <div><h4>Citada por</h4>{note.backlinks.map((b) => (
            <button key={b.rel} type="button" onClick={() => onRel(b.rel)} title={b.rel}>{b.title || noteTitle(b.rel)}</button>
          ))}</div>}
        </footer>
      )}
    </article>
  );
}
