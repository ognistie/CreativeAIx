import { useCallback, useEffect, useRef, useState } from "react";
import { FOLDER_COLORS, FolderCard } from "../components/journal/FolderCard";
import { localDay, MonthCalendar } from "../components/journal/MonthCalendar";
import { PaperCard } from "../components/journal/PaperCard";
import { ProgressRing } from "../components/ProgressRing";
import { AppDialog, Button, Chip, EmptyState, Field, GlassPanel, Icon, IconButton, Skeleton, Spinner } from "../components/ui";
import { cn } from "../lib/cn";
import { core } from "../lib/host";
import { useCoreEvent } from "../lib/useCore";
import { Page, Switch } from "./Page";

import { YouView } from "./YouView";

// JournalView: o Diario, um caderno na camada pessoal do Cerebro. Pastas, entradas com salvamento
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
// Cor de cada pasta: preferencia so deste computador (localStorage), com padrao por pasta.
const COLOR_KEY = "aix.journal.folderColors";
const DEFAULT_COLOR: Record<string, string> = { notas: FOLDER_COLORS[0], rotinas: FOLDER_COLORS[1], agentes: FOLDER_COLORS[2], assuntos: FOLDER_COLORS[3] };
const readColors = (): Record<string, string> => {
  try {
    return JSON.parse(localStorage.getItem(COLOR_KEY) || "{}") as Record<string, string>;
  } catch {
    return {};
  }
};
const fmtLong = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
};

const fmtDay = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "short" });
};

export function JournalView({ initialEntry, initialProfile = false, onOpenBrain }: { initialEntry?: string; initialProfile?: boolean; onOpenBrain?: () => void } = {}) {
  const [profile, setProfile] = useState(initialProfile);
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
  const [dates, setDates] = useState<string[]>([]);
  const [day, setDay] = useState("");
  const [dayRows, setDayRows] = useState<Row[] | null>(null);
  const [colors, setColors] = useState<Record<string, string>>(readColors);

  const setColor = (key: string, c: string) =>
    setColors((prev) => {
      const next = { ...prev, [key]: c };
      try {
        localStorage.setItem(COLOR_KEY, JSON.stringify(next));
      } catch {
        /* sem armazenamento: a cor vale so nesta sessao */
      }
      return next;
    });

  const loadFolders = useCallback(() => {
    void call(core().call("journalFolders")).then((r) => {
      if (!r.ok) return setError(r.error || "");
      setAvailable(r.available !== false);
      setUseInBrain(!!r.use_in_brain);
      setFolders((r.folders as Folder[]) ?? []);
    });
  }, []);
  useEffect(loadFolders, [loadFolders]);
  const loadDates = useCallback(() => void call(core().call("journalDates")).then((r) => r.ok && setDates((r.dates as string[]) ?? [])), []);
  useEffect(loadDates, [loadDates]);
  useEffect(() => {
    if (!day) return setDayRows(null);
    setDayRows(null);
    void call(core().call("journalList", "", "", day)).then((r) => setDayRows(r.ok ? ((r.items as Row[]) ?? []) : []));
  }, [day]);
  useEffect(() => {
    if (initialEntry) void call(core().call("journalGet", initialEntry)).then((r) => r.ok && setEntry(r.entry as Entry));
  }, [initialEntry]);

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

  // Entrada nova nasce no dia escolhido no calendario; sem dia escolhido, hoje (dia local, nao UTC)
  const newEntry = () => setEntry({ id: "", title: "", body: "", date: day || localDay(new Date()), folder, private: false });

  if (profile) return <YouView onBack={() => setProfile(false)} onOpenBrain={onOpenBrain} />;

  if (available === false) {
    return (
      <Page title="Diário" actions={<Button size="compact" icon="user" onClick={() => setProfile(true)}>Como trabalhar comigo</Button>}>
        <EmptyState icon="notebook" title="Diário indisponível">
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
          loadDates();
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
        <div className="flex flex-wrap items-center gap-3">
          {folder && (
            <Button variant="ghost" size="compact" icon="arrow-left" onClick={() => (setFolder(""), setRows(null))}>
              Diário
            </Button>
          )}
          {!folder && <Button size="compact" icon="user" onClick={() => setProfile(true)}>Como trabalhar comigo</Button>}
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
      {error && <p className="mb-4 rounded-r2 bg-bad/10 p-3 text-sm text-bad-ink">{error}</p>}
      {!folder ? (
        available === null ? (
          <Skeleton className="h-64 rounded-r4" />
        ) : (
          <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
            <ul className="grid grid-cols-2 gap-x-6 gap-y-4" aria-label="Pastas do Diário">
              {folders.map((f, i) => (
                <li key={f.key} className="animate-enter" style={{ animationDelay: `${i * 50}ms` }}>
                  <FolderCard
                    name={f.name}
                    count={f.count}
                    privateCount={f.private}
                    recent={f.recent}
                    color={colors[f.key] ?? DEFAULT_COLOR[f.key] ?? FOLDER_COLORS[5]}
                    onOpen={() => setFolder(f.key)}
                    onColor={(c) => setColor(f.key, c)}
                  />
                </li>
              ))}
            </ul>
            <aside className="space-y-4">
              <GlassPanel className="p-4">
                <MonthCalendar dates={dates} selected={day} onSelect={setDay} />
              </GlassPanel>
              {day && (
                <section aria-live="polite">
                  <p className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">
                    <Icon name="calendar" size={13} /> {fmtLong(day)}
                  </p>
                  {!dayRows ? (
                    <Skeleton className="h-40 rounded-r3" />
                  ) : dayRows.length === 0 ? (
                    <p className="text-sm text-fg-muted">Nenhuma entrada neste dia.</p>
                  ) : (
                    <ul className="space-y-4">
                      {dayRows.map((r, i) => (
                        <li key={r.id}>
                          <PaperCard title={r.title} date={r.date} summary={r.summary} tags={r.tags} isPrivate={r.private} priorities={r.priorities} openTasks={r.open_tasks} seed={i + 3} onOpen={() => openEntry(r.id)} />
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              )}
            </aside>
          </div>
        )
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-2">
            <Field value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar no Diário" aria-label="Buscar no Diário" className="h-8 w-64 text-sm" />
            {tags.map((t) => (
              <Chip key={t} icon="tag" selected={tag === t} onClick={() => setTag(tag === t ? "" : t)}>
                {t}
              </Chip>
            ))}
          </div>
          {!rows ? (
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-56 rounded-r2" />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <EmptyState
              icon="pen"
              title={query || tag ? "Nada com essa busca" : "Nenhuma entrada nesta pasta"}
              action={
                <Button size="compact" variant="primary" icon="plus" onClick={newEntry}>
                  Escrever a primeira
                </Button>
              }
            />
          ) : (
            <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {rows.map((r, i) => (
                <li key={r.id} className="animate-enter" style={{ animationDelay: `${Math.min(i, 9) * 35}ms` }}>
                  <PaperCard title={r.title} date={r.date} summary={r.summary} tags={r.tags} isPrivate={r.private} priorities={r.priorities} openTasks={r.open_tasks} seed={i + 1} onOpen={() => openEntry(r.id)} />
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
  // A data e da entrada, nao da criacao: da para mudar (escrever hoje sobre ontem, ou reaproveitar uma entrada)
  const [date, setDate] = useState(entry.date);
  const [state, setState] = useState<"" | "saving" | "saved" | "error">("");
  const [ask, setAsk] = useState<"" | "summary" | "delete">("");
  const [summarizing, setSummarizing] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const idRef = useRef(entry.id);
  const savedRef = useRef({ title: entry.title, body: entry.body, date: entry.date });

  const save = useCallback(async () => {
    if (!title.trim() && !body.trim()) return;
    setState("saving");
    const r = await call(core().call("journalSave", JSON.stringify({ id: idRef.current, title, body, folder: entry.folder, date })));
    if (!r.ok) return setState("error");
    const e = r.entry as Entry;
    idRef.current = e.id;
    savedRef.current = { title, body, date };
    setState("saved");
    onSaved(e);
  }, [title, body, date, entry.folder, onSaved]);

  // Salva sozinho 1,2 s depois de parar de digitar (ou de trocar a data)
  useEffect(() => {
    const s = savedRef.current;
    if (title === s.title && body === s.body && date === s.date) return;
    const t = setTimeout(() => void save(), 1200);
    return () => clearTimeout(t);
  }, [title, body, date, save]);

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
            <Button variant="ghost" size="compact" icon="arrow-left" onClick={onBack}>
              Voltar
            </Button>
            <label className="flex items-center gap-1.5 rounded-r2 px-2 py-1 text-xs text-fg-muted hover:bg-bg-hover" title="Dia desta entrada no calendário">
              <Icon name="calendar" size={13} />
              <span className="sr-only">Dia da entrada</span>
              <input type="date" value={date} max={localDay(new Date())} onChange={(e) => e.target.value && setDate(e.target.value)}
                className="bg-transparent text-xs text-fg-muted outline-none [color-scheme:inherit]" />
            </label>
            <span className="flex-1 text-xs text-fg-subtle" aria-live="polite">
              {date !== entry.date && entry.id ? `Muda para ${fmtDay(date)} · ` : ""}{{ "": "", saving: "Salvando…", saved: "Salvo", error: "Não salvou" }[state]}
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
                  className={cn(entry.private && "text-accent-ink")}
                />
                <IconButton icon="trash" label="Excluir entrada" flat onClick={() => setAsk("delete")} />
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
          <TaskCard
            title={entry.private ? "Extraído · privada, fora da Conversa" : "Extraído do texto"}
            body={body}
            derived={d}
            onToggle={(text, done) => setBody((b) => toggleTask(b, text, done))}
          />
          {entry.id && (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">Resumo por IA</p>
              {d?.ai_summary?.text && <p className="mb-2 text-fg">{d.ai_summary.text}</p>}
              {summaryError && <p className="mb-2 text-bad-ink">{summaryError}</p>}
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

/** Marca/desmarca "- [ ] texto" no corpo (a primeira tarefa com esse texto e estado). O salvamento automatico grava. */
function toggleTask(body: string, text: string, done: boolean): string {
  const lines = body.split("\n");
  const re = /^(\s*[-*]\s*\[)([ xX])(\]\s*)(.*)$/;
  const i = lines.findIndex((l) => {
    const m = l.match(re);
    return !!m && (m[4] ?? "").trim() === text.trim() && (m[2] !== " ") === done;
  });
  if (i < 0) return body;
  lines[i] = (lines[i] ?? "").replace(re, (_a, open: string, _x, close: string, t: string) => `${open}${done ? " " : "x"}${close}${t}`);
  return lines.join("\n");
}

/** Cartao de tarefas (referencia: checklist com anel de progresso e "faltam N"). Clicar marca no texto. */
function TaskCard({
  title,
  body,
  derived,
  onToggle,
}: {
  title: string;
  body: string;
  derived?: Entry["derived"];
  onToggle: (text: string, done: boolean) => void;
}) {
  const tasks = derived?.tasks ?? [];
  const done = tasks.filter((t) => t.done).length;
  const left = tasks.length - done;
  const empty = !derived || (!derived.priorities.length && !tasks.length && !derived.tags.length);
  return (
    <GlassPanel className="overflow-hidden">
      <div className="flex items-center gap-3 border-b border-hairline p-4">
        {tasks.length > 0 ? <ProgressRing done={done} total={tasks.length} className="text-accent-ink" /> : <Icon name="checklist" size={20} className="text-fg-muted" />}
        <div className="min-w-0">
          <p className="text-sm font-medium text-fg">Tarefas e prioridades</p>
          <p className="text-xs text-fg-muted">{title}</p>
        </div>
      </div>
      {empty ? (
        <p className="p-4 text-sm leading-relaxed text-fg-muted">
          Use <code className="rounded bg-chip px-1 text-fg">!</code> para prioridade, <code className="rounded bg-chip px-1 text-fg">- [ ]</code> para tarefa e{" "}
          <code className="rounded bg-chip px-1 text-fg">#</code> para tag.
        </p>
      ) : (
        <ul className="p-2 text-sm">
          {derived!.priorities.map((p, i) => (
            <li key={`p${i}`} className="flex items-start gap-2.5 rounded-r2 px-2 py-1.5 text-fg">
              <Icon name="flag" size={15} className="mt-0.5 shrink-0 text-warn-ink" /> {p}
            </li>
          ))}
          {tasks.map((t, i) => (
            <li key={`t${i}`}>
              <button
                type="button"
                onClick={() => onToggle(t.text, t.done)}
                disabled={!body}
                aria-pressed={t.done}
                className="flex w-full items-start gap-2.5 rounded-r2 px-2 py-1.5 text-left transition-colors hover:bg-row-hover"
              >
                <Icon name={t.done ? "check-circle" : "circle"} size={16} className={cn("mt-0.5 shrink-0", t.done ? "text-ok-ink" : "text-fg-muted")} />
                <span className={cn(t.done ? "text-fg-muted line-through" : "text-fg")}>{t.text}</span>
              </button>
            </li>
          ))}
          {derived!.tags.length > 0 && (
            <li className="flex flex-wrap gap-1.5 px-2 pb-1 pt-2">
              {derived!.tags.map((t) => (
                <span key={t} className="flex items-center gap-1 rounded-full bg-chip px-2 py-0.5 text-xs text-fg-muted">
                  <Icon name="tag" size={11} /> {t}
                </span>
              ))}
            </li>
          )}
        </ul>
      )}
      {tasks.length > 0 && (
        <p className="flex items-center justify-between border-t border-hairline px-4 py-2.5 text-xs text-fg-muted">
          <span>{left === 0 ? "Tudo feito" : `${left} ${left === 1 ? "falta" : "faltam"}`}</span>
          <span>
            {done}/{tasks.length}
          </span>
        </p>
      )}
    </GlassPanel>
  );
}
