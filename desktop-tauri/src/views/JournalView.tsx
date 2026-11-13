import { useCallback, useEffect, useRef, useState } from "react";
import { AppDialog, Button, Chip, EmptyState, Field, GlassPanel, Icon, IconButton, Skeleton, Spinner } from "../components/ui";
import { cn } from "../lib/cn";
import { core } from "../lib/tauri";
import { useCoreEvent } from "../lib/useCore";
import { Page, Switch } from "./Page";

// JournalView.qml: o Diario, um caderno na camada pessoal do Cerebro. Pastas, entradas com salvamento
// automatico, privadas (fora da Conversa), extracao de prioridades/tarefas/tags e resumo por IA opcional.

interface Folder {
  key: string;
  name: string;
  count: number;
  recent: string[];
  private: number;
}

interface Row {
  id: string;
  date: string;
  title: string;
  folder: string;
  summary: string;
  tags: string[];
  private: boolean;
  priorities: number;
  open_tasks: number;
}

interface Entry {
  id: string;
  title: string;
  body: string;
  date: string;
  folder: string;
  private: boolean;
  derived?: {
    tags: string[];
    priorities: string[];
    tasks: Array<{ text: string; done: boolean }>;
    ai_summary?: { text: string };
  };
}

type Reply = { ok: boolean; error?: string } & Record<string, unknown>;
const call = (p: Promise<unknown>) => p.then((r) => r as Reply).catch((e: Error) => ({ ok: false, error: e.message }) as Reply);
const fmtDay = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "short" });
};

export function JournalView() {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [useInBrain, setUseInBrain] = useState(false);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [folder, setFolder] = useState("");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState("");
  const [entry, setEntry] = useState<Entry | null>(null);
  const [error, setError] = useState("");

  const loadFolders = useCallback(() => {
    void call(core().call("journalFolders")).then((r) => {
      if (!r.ok) return setError(r.error || "");
      setAvailable(r.available !== false);
      setUseInBrain(!!r.use_in_brain);
      setFolders((r.folders as Folder[]) ?? []);
    });
  }, []);
  useEffect(loadFolders, [loadFolders]);

  const loadList = useCallback(() => {
    if (!folder) return;
    void call(core().call("journalListIn", folder, query, tag, "")).then((r) => {
      setRows(r.ok ? ((r.items as Row[]) ?? []) : []);
      setTags((r.tags as string[]) ?? []);
    });
  }, [folder, query, tag]);
  useEffect(() => {
    const t = setTimeout(loadList, 180);
    return () => clearTimeout(t);
  }, [loadList]);

  const openEntry = (id: string) => void call(core().call("journalGet", id)).then((r) => (r.ok ? setEntry(r.entry as Entry) : setError(r.error || "")));

  const newEntry = () => setEntry({ id: "", title: "", body: "", date: new Date().toISOString().slice(0, 10), folder, private: false });

  if (available === false) {
    return (
      <Page title="Diário">
        <EmptyState icon="file-text" title="Diário indisponível">
          O Diário fica na pasta pessoal do Segundo Cérebro, que não está configurada.
        </EmptyState>
      </Page>
    );
  }

  if (entry) {
    return (
      <EntryEditor
        key={entry.id || "novo"}
        entry={entry}
        onBack={() => {
          setEntry(null);
          loadList();
          loadFolders();
        }}
        onSaved={(e) => setEntry(e)}
      />
    );
  }

  const current = folders.find((f) => f.key === folder);

  return (
    <Page
      wide
      title={current ? current.name : "Diário"}
      subtitle={current ? undefined : "Um caderno que o agente pode consultar, se você quiser. Fica na sua pasta pessoal."}
      actions={
        <div className="flex items-center gap-3">
          {folder && (
            <Button variant="ghost" size="compact" onClick={() => (setFolder(""), setRows(null))}>
              ← Diário
            </Button>
          )}
          <label className="flex items-center gap-2 text-sm text-fg-muted">
            Usar na Conversa
            <Switch
              label="Usar o Diário na Conversa"
              checked={useInBrain}
              onChange={(on) => void call(core().call("journalUseInBrain", on)).then((r) => r.ok && setUseInBrain(!!r.use_in_brain))}
            />
          </label>
          {folder && (
            <Button variant="primary" size="compact" icon="plus" onClick={newEntry}>
              Nova entrada
            </Button>
          )}
        </div>
      }
    >
      {error && <p className="mb-4 rounded-r2 bg-bad/10 p-3 text-sm text-bad">{error}</p>}
      {!folder ? (
        available === null ? (
          <Skeleton className="h-40 rounded-r4" />
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {folders.map((f) => (
              <li key={f.key}>
                <button type="button" onClick={() => setFolder(f.key)} className="press block h-full w-full text-left">
                  <GlassPanel className="flex h-full flex-col p-5 hover:border-hairline-hi">
                    <Icon name="folder" size={20} className="text-accent" />
                    <p className="mt-3 font-display text-lg font-medium text-fg">{f.name}</p>
                    <p className="text-sm text-fg-muted">
                      {f.count} {f.count === 1 ? "entrada" : "entradas"}
                      {f.private ? ` · ${f.private} privada${f.private > 1 ? "s" : ""}` : ""}
                    </p>
                    <ul className="mt-3 space-y-0.5 text-xs text-fg-subtle">
                      {f.recent.map((t, i) => (
                        <li key={i} className="truncate">
                          {t}
                        </li>
                      ))}
                    </ul>
                  </GlassPanel>
                </button>
              </li>
            ))}
          </ul>
        )
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Field value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar no Diário" aria-label="Buscar no Diário" className="h-8 w-64 text-sm" />
            {tags.map((t) => (
              <Chip key={t} selected={tag === t} onClick={() => setTag(tag === t ? "" : t)}>
                #{t}
              </Chip>
            ))}
          </div>
          {!rows ? (
            <Skeleton className="h-32 rounded-r3" />
          ) : rows.length === 0 ? (
            <EmptyState icon="file-text" title={query || tag ? "Nada com essa busca" : "Nenhuma entrada nesta pasta"} action={<Button size="compact" variant="primary" icon="plus" onClick={newEntry}>Escrever a primeira</Button>} />
          ) : (
            <ul className="overflow-hidden rounded-r3 border border-edge bg-glass">
              {rows.map((r) => (
                <li key={r.id} className="border-b border-hairline last:border-0">
                  <button type="button" onClick={() => openEntry(r.id)} className="flex w-full items-start gap-4 px-4 py-3 text-left hover:bg-row-hover">
                    <span className="w-20 shrink-0 pt-0.5 text-xs text-fg-subtle">{fmtDay(r.date)}</span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2 text-md text-fg">
                        {r.private && <Icon name="lock" size={13} className="text-fg-muted" label="Privada" />}
                        <span className="truncate">{r.title || "Sem título"}</span>
                      </span>
                      {r.summary && <span className="mt-0.5 line-clamp-1 block text-sm text-fg-muted">{r.summary}</span>}
                    </span>
                    <span className="shrink-0 text-right text-xs text-fg-subtle">
                      {r.priorities > 0 && <span className="block">! {r.priorities}</span>}
                      {r.open_tasks > 0 && <span className="block">☐ {r.open_tasks}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Page>
  );
}

function EntryEditor({ entry, onBack, onSaved }: { entry: Entry; onBack: () => void; onSaved: (e: Entry) => void }) {
  const [title, setTitle] = useState(entry.title);
  const [body, setBody] = useState(entry.body);
  const [state, setState] = useState<"" | "saving" | "saved" | "error">("");
  const [ask, setAsk] = useState<"" | "summary" | "delete">("");
  const [summarizing, setSummarizing] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const idRef = useRef(entry.id);
  const savedRef = useRef({ title: entry.title, body: entry.body });

  const save = useCallback(async () => {
    if (!title.trim() && !body.trim()) return;
    setState("saving");
    const r = await call(core().call("journalSave", JSON.stringify({ id: idRef.current, title, body, folder: entry.folder, date: entry.date })));
    if (!r.ok) return setState("error");
    const e = r.entry as Entry;
    idRef.current = e.id;
    savedRef.current = { title, body };
    setState("saved");
    onSaved(e);
  }, [title, body, entry.folder, entry.date, onSaved]);

  // Salva sozinho 1,2 s depois de parar de digitar
  useEffect(() => {
    if (title === savedRef.current.title && body === savedRef.current.body) return;
    const t = setTimeout(() => void save(), 1200);
    return () => clearTimeout(t);
  }, [title, body, save]);

  useCoreEvent(
    "journalSummary",
    useCallback(
      (p: unknown) => {
        setSummarizing(false);
        const r = p as { ok: boolean; entry?: Entry; error?: string };
        if (r.ok && r.entry) onSaved(r.entry);
        else setSummaryError(r.error || "O resumo não saiu.");
      },
      [onSaved],
    ),
  );

  const d = entry.derived;

  return (
    <div className="h-full overflow-y-auto px-8">
      <div className="mx-auto grid max-w-5xl gap-8 py-10 lg:grid-cols-[1fr_260px]">
        <div className="min-w-0">
          <div className="mb-4 flex items-center gap-2">
            <Button variant="ghost" size="compact" onClick={onBack}>
              ← Voltar
            </Button>
            <span className="flex-1 text-xs text-fg-subtle" aria-live="polite">
              {fmtDay(entry.date)} · {{ "": "", saving: "Salvando…", saved: "Salvo", error: "Não salvou" }[state]}
            </span>
            {state === "error" && (
              <Button size="compact" onClick={() => void save()}>
                Tentar de novo
              </Button>
            )}
            {entry.id && (
              <>
                <IconButton
                  icon={entry.private ? "lock" : "eye"}
                  label={entry.private ? "Privada: fora da Conversa (clique para liberar)" : "Visível para a Conversa (clique para tornar privada)"}
                  flat
                  onClick={() => void call(core().call("journalSetPrivate", entry.id, !entry.private)).then((r) => r.ok && onSaved(r.entry as Entry))}
                  className={cn(entry.private && "text-accent")}
                />
                <IconButton icon="x" label="Excluir entrada" flat onClick={() => setAsk("delete")} />
              </>
            )}
          </div>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Título"
            aria-label="Título"
            className="w-full select-text bg-transparent font-display text-[26px] font-medium tracking-[-0.03em] text-fg outline-none placeholder:text-fg-subtle"
          />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Escreva aqui… ! prioridade   - [ ] tarefa   #tag"
            aria-label="Texto"
            autoFocus={!entry.id}
            className="mt-3 min-h-[55vh] w-full select-text resize-none bg-transparent text-md leading-relaxed text-fg outline-none placeholder:text-fg-subtle"
          />
        </div>
        <aside className="space-y-5 text-sm">
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">
              {entry.private ? "Extraído (privada: fica fora da Conversa)" : "Extraído"}
            </p>
            {!d || (!d.priorities.length && !d.tasks.length && !d.tags.length) ? (
              <p className="text-fg-subtle">Use ! para prioridades, - [ ] para tarefas e # para tags.</p>
            ) : (
              <ul className="space-y-1">
                {d.priorities.map((p, i) => (
                  <li key={`p${i}`} className="text-fg">
                    ! {p}
                  </li>
                ))}
                {d.tasks.map((t, i) => (
                  <li key={`t${i}`} className={cn("text-fg-muted", t.done && "line-through")}>
                    {t.done ? "☑" : "☐"} {t.text}
                  </li>
                ))}
                {d.tags.length > 0 && <li className="text-accent">{d.tags.map((t) => `#${t}`).join("  ")}</li>}
              </ul>
            )}
          </div>
          {entry.id && (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">Resumo por IA</p>
              {d?.ai_summary?.text && <p className="mb-2 text-fg">{d.ai_summary.text}</p>}
              {summaryError && <p className="mb-2 text-bad">{summaryError}</p>}
              <Button size="compact" icon="sparkle" disabled={summarizing} onClick={() => setAsk("summary")}>
                {summarizing ? <Spinner size={12} /> : null}
                {d?.ai_summary ? "Resumir de novo" : "Resumir"}
              </Button>
            </div>
          )}
        </aside>
      </div>

      <AppDialog
        open={ask === "summary"}
        onOpenChange={(o) => !o && setAsk("")}
        title="Resumir esta entrada com IA?"
        description={`O título e o texto desta entrada (${title.length + body.length} caracteres) vão para o provedor de IA. Nada mais do Diário sai do computador.`}
        actions={
          <>
            <Button variant="ghost" onClick={() => setAsk("")}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                setAsk("");
                setSummarizing(true);
                setSummaryError("");
                void core().call("journalSummarize", entry.id);
              }}
            >
              Resumir
            </Button>
          </>
        }
      />
      <AppDialog
        open={ask === "delete"}
        onOpenChange={(o) => !o && setAsk("")}
        title="Excluir esta entrada?"
        description="A entrada e o que foi extraído dela saem do disco e da Conversa. Não dá para desfazer."
        actions={
          <>
            <Button variant="ghost" onClick={() => setAsk("")}>
              Cancelar
            </Button>
            <Button variant="danger" onClick={() => void call(core().call("journalDelete", entry.id)).then((r) => (r.ok ? onBack() : setAsk("")))}>
              Excluir
            </Button>
          </>
        }
      />
    </div>
  );
}
