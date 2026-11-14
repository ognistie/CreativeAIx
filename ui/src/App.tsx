import { useCallback, useEffect, useMemo, useState } from "react";
import { CommandPalette, type PaletteItem } from "./components/CommandPalette";
import { Titlebar } from "./components/Titlebar";
import { AppDialog, AppMenu, Button, Field, HintProvider, Icon, IconButton, Segmented, type IconName } from "./components/ui";
import { applyAppearance, type Appearance } from "./lib/appearance";
import { cn } from "./lib/cn";
import { core, inQt, inTauri, wallpaperUrl } from "./lib/host";
import { agentStore, dispatchTask, useAgentPref, useTask, wireTaskEvents, wireVoiceEvents, type AgentPref } from "./lib/stores";
import { useCoreEvent, useCoreStatus } from "./lib/useCore";
import { wireMainWindow } from "./lib/windowing";
import { AboutView } from "./views/AboutView";
import { ActivityView } from "./views/ActivityView";
import { BrainView } from "./views/BrainView";
import { HarnessView, type Harness } from "./views/HarnessView";
import { HistoryView } from "./views/HistoryView";
import { JournalView } from "./views/JournalView";
import { LabView } from "./views/LabView";
import { LibraryView } from "./views/LibraryView";
import { SettingsView } from "./views/SettingsView";
import { startTask, TaskView } from "./views/task/TaskView";
import { YouView } from "./views/YouView";

// Main.qml: marca, busca, navegacao em grupos (Trabalho, Conhecimento, Sistema), conversas e status;
// cabecalho com o titulo da tela e "quem atende o pedido". Atalhos iguais aos do QML.

export type Page =
  | "task" | "history" | "activity" | "brain" | "you" | "journal" | "library" | "lab" | "harness" | "settings" | "about";

const TITLES: Record<Page, string> = {
  task: "Conversa", history: "Histórico", activity: "Atividade", brain: "Cérebro", you: "Você", journal: "Diário",
  library: "Biblioteca", lab: "AI Research Lab", harness: "Harness", settings: "Configurações", about: "Sobre",
};

type Group = "Trabalho" | "Conhecimento" | "Sistema";
const NAV: Array<{ page: Page; label: string; icon: IconName; group: Group; key?: string; module?: string }> = [
  { page: "history", label: "Histórico", icon: "history", group: "Trabalho", key: "Ctrl H", module: "history" },
  { page: "activity", label: "Atividade", icon: "chart", group: "Trabalho" },
  { page: "brain", label: "Cérebro", icon: "brain", group: "Conhecimento", key: "Ctrl B", module: "brain" },
  { page: "you", label: "Você", icon: "user", group: "Conhecimento", module: "you" },
  { page: "journal", label: "Diário", icon: "notebook", group: "Conhecimento" },
  { page: "library", label: "Biblioteca", icon: "book", group: "Conhecimento" },
  { page: "lab", label: "AI Research Lab", icon: "flask", group: "Sistema" },
  { page: "harness", label: "Harness", icon: "sliders", group: "Sistema" },
  { page: "settings", label: "Configurações", icon: "settings", group: "Sistema", key: "Ctrl ," },
  { page: "about", label: "Sobre", icon: "info", group: "Sistema" },
];

const AGENTS: ReadonlyArray<{ value: AgentPref; label: string; icon: IconName }> = [
  { value: "auto", label: "Automático", icon: "route" },
  { value: "claude", label: "Claude Code", icon: "bolt" },
  { value: "codex", label: "Codex", icon: "terminal" },
];

interface Conversation {
  id: string;
  title: string;
  updated_at: number;
  turns: number;
}

wireTaskEvents();
wireVoiceEvents();
wireMainWindow((text) => startTask(text, { dryRun: false, report: false }));

export function App() {
  const status = useCoreStatus();
  const task = useTask();
  const agent = useAgentPref();
  const [page, setPage] = useState<Page>("task");
  const [collapsed, setCollapsed] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [current, setCurrent] = useState("");
  const [harness, setHarness] = useState<Harness | null>(null);
  const [suggestions, setSuggestions] = useState(0);
  const [palette, setPalette] = useState(false);
  const [deep, setDeep] = useState<{ topic?: string; entry?: string; at: number }>({ at: 0 });
  const modules = harness?.modules ?? {};

  const refreshConversations = useCallback(() => {
    core()
      .call("loadConversations")
      .then((r) => {
        const v = r as { items?: Conversation[]; current?: string };
        setConversations(v.items ?? []);
        setCurrent(v.current ?? "");
      })
      .catch(() => {});
  }, []);

  const refreshSuggestions = useCallback(() => {
    core()
      .call("suggestionsList")
      .then((r) => setSuggestions(((r as { items?: unknown[] }).items ?? []).length))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (status !== "open") return;
    core().call("appearance").then((a) => applyAppearance(a as Appearance)).catch(() => {});
    core()
      .call("harnessGet")
      .then((r) => setHarness((r as { harness?: Harness }).harness ?? null))
      .catch(() => {});
    refreshConversations();
    refreshSuggestions();
  }, [status, refreshConversations, refreshSuggestions]);

  useCoreEvent("conversationsChanged", refreshConversations);
  useCoreEvent("sessionReset", refreshConversations);
  useCoreEvent("historyChanged", refreshSuggestions);

  const newConversation = useCallback(() => {
    if (task.busy) return;
    setPage("task");
    dispatchTask({ type: "newConversation" });
    void core().call("newSession");
  }, [task.busy]);

  const openConversation = useCallback(
    (id: string) => {
      if (task.busy) return;
      core()
        .call("openConversation", id)
        .then((d) => {
          dispatchTask({ type: "showConversation", turns: ((d as { turns?: [] }).turns ?? []) as Array<Record<string, unknown>> });
          setCurrent(id);
          setPage("task");
        })
        .catch(() => {});
    },
    [task.busy],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      if (e.ctrlKey && k === "n") newConversation();
      else if (e.ctrlKey && k === "h") setPage("history");
      else if (e.ctrlKey && k === "b") setPage("brain");
      else if (e.ctrlKey && k === ",") setPage("settings");
      else if (e.ctrlKey && k === "\\") setCollapsed((c) => !c);
      else if (e.ctrlKey && k === "k" && page !== "brain") setPalette((o) => !o);
      else if (k === "escape" && task.busy) void core().call("forceStop");
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [newConversation, task.busy, page]);

  const visibleNav = NAV.filter((n) => !n.module || modules[n.module] !== false);

  const paletteBase = useMemo<PaletteItem[]>(
    () => [
      { id: "new", title: "Nova conversa", area: "Ação", icon: "plus", hint: "Ctrl N", run: newConversation },
      ...visibleNav.map((n) => ({ id: n.page, title: n.label, area: "Ir para", icon: n.icon, hint: n.key, run: () => setPage(n.page) })),
      ...conversations.map((c) => ({ id: `c:${c.id}`, title: c.title, area: "Conversa", icon: "message" as IconName, run: () => openConversation(c.id) })),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [newConversation, modules, conversations, openConversation],
  );

  const onTopic = useCallback((id: string) => (setDeep({ topic: id, at: Date.now() }), setPage("library")), []);
  const onDiary = useCallback((id: string) => (setDeep({ entry: id, at: Date.now() }), setPage("journal")), []);
  const photo = wallpaperUrl(String(harness?.appearance.wallpaper ?? ""));
  const dim = Number(harness?.appearance.dim ?? 0.35);
  useEffect(() => {
    document.documentElement.dataset.photo = photo ? "on" : "off";
  }, [photo]);

  // Barra de titulo nativa (app Qt) na cor do fundo atual, como no QML
  useEffect(() => {
    if (!inQt || !harness) return;
    const t = setTimeout(() => {
      const color = getComputedStyle(document.documentElement).getPropertyValue("--bg-base").trim();
      if (/^#[0-9a-f]{6}$/i.test(color)) void core().call("setTitleBarColor", color);
    }, 50);
    return () => clearTimeout(t);
  }, [harness]);

  return (
    <HintProvider>
      <div className="flex h-full flex-col">
        {inTauri && <Titlebar />}
        <div className="relative flex min-h-0 flex-1">
          {/* Fundo: foto do Harness (app Qt) ou as luzes da paleta */}
          {photo ? (
            <div aria-hidden className="pointer-events-none absolute inset-0">
              <img src={photo} alt="" className="size-full object-cover" />
              <div className="absolute inset-0" style={{ background: "var(--bg-base)", opacity: Math.max(0.15, Math.min(0.85, dim)) }} />
            </div>
          ) : (
            <div aria-hidden className="ambient pointer-events-none absolute inset-0" />
          )}
          {!collapsed && (
            <Sidebar
              page={page}
              setPage={setPage}
              task={task}
              nav={visibleNav}
              suggestions={suggestions}
              conversations={conversations}
              current={current}
              status={status}
              onNew={newConversation}
              onOpen={openConversation}
              onSearch={() => setPalette(true)}
            />
          )}
          <main className="relative flex min-w-0 flex-1 flex-col">
            <header className="flex h-14 shrink-0 items-center gap-3 px-4">
              <IconButton
                icon="sidebar"
                label={collapsed ? "Mostrar barra lateral (Ctrl \\)" : "Esconder barra lateral (Ctrl \\)"}
                flat
                onClick={() => setCollapsed((c) => !c)}
              />
              <span className="h-5 w-px bg-hairline" />
              <h1 className="text-md font-semibold text-fg">{TITLES[page]}</h1>
              <span className="flex-1" />
              {page === "task" && (
                <Segmented label="Quem atende o pedido" value={agent} onValueChange={(v) => agentStore.set(v)} options={AGENTS} />
              )}
              <IconButton icon="plus" label="Nova conversa (Ctrl N)" flat onClick={newConversation} disabled={task.busy} />
            </header>
            <div className="relative min-h-0 flex-1">
              <PageView page={page} go={setPage} deep={deep} harness={harness} onHarness={setHarness} />
            </div>
          </main>
          <CommandPalette open={palette} onOpenChange={setPalette} base={paletteBase} onTopic={onTopic} onDiary={onDiary} />
        </div>
      </div>
    </HintProvider>
  );
}

function PageView({
  page,
  go,
  deep,
  harness,
  onHarness,
}: {
  page: Page;
  go: (p: Page) => void;
  deep: { topic?: string; entry?: string; at: number };
  harness: Harness | null;
  onHarness: (h: Harness) => void;
}) {
  switch (page) {
    case "task":
      return <TaskView go={go} dev={harness?.dev} />;
    case "history":
      return <HistoryView />;
    case "activity":
      return <ActivityView onAnswer={() => go("task")} />;
    case "you":
      return <YouView onOpenBrain={() => go("brain")} />;
    case "library":
      return <LibraryView key={`lib-${deep.at}`} openTopic={deep.topic} />;
    case "harness":
      return <HarnessView onChanged={onHarness} />;
    case "lab":
      return <LabView />;
    case "journal":
      return <JournalView key={`diary-${deep.at}`} initialEntry={deep.entry} />;
    case "brain":
      return <BrainView onOpenYou={() => go("you")} />;
    case "about":
      return <AboutView />;
    case "settings":
      return <SettingsView />;
  }
}

function BrandMark({ size = 22 }: { size?: number }) {
  // BrandMark.qml: quatro quadrados, o ultimo na cor de destaque
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <rect key={i} x={2 + (i % 2) * 11} y={2 + Math.floor(i / 2) * 11} width={9} height={9} rx={2.6} fill={i === 3 ? "var(--accent)" : "currentColor"} />
      ))}
    </svg>
  );
}

function Sidebar(props: {
  page: Page;
  setPage: (p: Page) => void;
  task: ReturnType<typeof useTask>;
  nav: typeof NAV;
  suggestions: number;
  conversations: Conversation[];
  current: string;
  status: string;
  onNew: () => void;
  onOpen: (id: string) => void;
  onSearch: () => void;
}) {
  const { page, setPage, task } = props;
  const [query, setQuery] = useState("");
  const [renaming, setRenaming] = useState<Conversation | null>(null);
  const [deleting, setDeleting] = useState<Conversation | null>(null);
  const [title, setTitle] = useState("");
  const list = props.conversations.filter((c) => c.title.toLowerCase().includes(query.trim().toLowerCase()));
  const idle = task.status === "idle";
  const groups: Group[] = ["Trabalho", "Conhecimento", "Sistema"];

  return (
    <nav aria-label="Navegação" className="relative z-10 flex w-[260px] shrink-0 flex-col border-r border-hairline bg-sidebar px-3 pb-3 pt-4 backdrop-blur-xl">
      <div className="mb-3 flex items-center gap-2.5 px-2 text-fg">
        <BrandMark />
        <span className="font-display text-[17px] font-semibold tracking-[-0.01em]">Creative AIx</span>
      </div>
      <NavButton icon="search" label="Buscar" hint="Ctrl K" alwaysHint onClick={props.onSearch} />

      {groups.map((g) => (
        <div key={g} className="mt-3 flex flex-col gap-0.5">
          <p className="mb-1 px-3 font-mono text-[11px] uppercase tracking-[0.12em] text-fg-subtle">{g}</p>
          {g === "Trabalho" && (
            <>
              <NavButton icon="plus" label="Nova conversa" active={page === "task" && idle && task.turns.length === 0} onClick={props.onNew} />
              {!idle && (
                <NavButton icon={task.busy ? "play" : "message"} label={task.busy ? "Em execução" : "Tarefa atual"} active={page === "task"} onClick={() => setPage("task")} pulse={task.busy} />
              )}
            </>
          )}
          {props.nav
            .filter((n) => n.group === g)
            .map((n) => (
              <NavButton
                key={n.page}
                icon={n.icon}
                label={n.label}
                hint={n.page === "brain" && props.suggestions > 0 ? `${props.suggestions} ${props.suggestions === 1 ? "sugestão" : "sugestões"}` : n.key}
                alwaysHint={n.page === "brain" && props.suggestions > 0}
                active={page === n.page}
                onClick={() => setPage(n.page)}
              />
            ))}
        </div>
      ))}

      <div className="mt-4 flex min-h-0 flex-1 flex-col">
        <label className="relative mb-2 block">
          <Icon name="search" size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle" />
          <Field value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar conversas" aria-label="Buscar conversas" className="h-9 pl-9 text-[13px]" />
        </label>
        <p className="mb-1 px-3 text-xs text-fg-subtle">Conversas</p>
        <ul className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
          {list.map((c) => (
            <li key={c.id} className="group relative">
              <button
                type="button"
                onClick={() => props.onOpen(c.id)}
                disabled={task.busy}
                className={cn(
                  "motion-fast flex h-9 w-full items-center rounded-r2 pl-3 pr-9 text-left text-[13px] transition-colors disabled:opacity-50",
                  c.id === props.current && page === "task" ? "bg-row-hover text-fg" : "text-fg-muted hover:bg-hover hover:text-fg",
                )}
              >
                <span className="truncate">{c.title}</span>
              </button>
              <span className="absolute right-0.5 top-0.5 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
                <AppMenu
                  trigger={<IconButton icon="more" label={`Ações de ${c.title}`} flat className="size-8" />}
                  items={[
                    { label: "Renomear", icon: "edit", onSelect: () => (setTitle(c.title), setRenaming(c)) },
                    { label: "Apagar", icon: "x", danger: true, onSelect: () => setDeleting(c) },
                  ]}
                />
              </span>
            </li>
          ))}
          {props.conversations.length === 0 && <li className="px-3 text-[13px] text-fg-subtle">As conversas salvas aparecem aqui.</li>}
        </ul>
      </div>

      <p role="status" className="mt-2 flex items-center gap-2 border-t border-hairline px-3 pt-3 text-xs text-fg-muted">
        <span className={cn("size-2 rounded-full", props.status !== "open" ? "bg-warn" : task.busy ? "animate-pulse bg-accent" : "bg-ok")} />
        {props.status !== "open" ? "Conectando ao núcleo…" : task.busy ? "Executando…" : "Pronto  ·  Claude Sonnet 5"}
      </p>

      <AppDialog
        open={!!renaming}
        onOpenChange={(o) => !o && setRenaming(null)}
        title="Renomear conversa"
        actions={
          <>
            <Button variant="ghost" onClick={() => setRenaming(null)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={!title.trim()}
              onClick={() => {
                if (renaming) void core().call("renameConversation", renaming.id, title.trim());
                setRenaming(null);
              }}
            >
              Salvar
            </Button>
          </>
        }
      >
        <Field value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Nome da conversa" maxLength={80} autoFocus />
      </AppDialog>
      <AppDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Apagar esta conversa?"
        description="Os pedidos e as respostas somem da lista. O histórico de execuções continua."
        actions={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (deleting) void core().call("deleteConversation", deleting.id);
                setDeleting(null);
              }}
            >
              Apagar
            </Button>
          </>
        }
      />
    </nav>
  );
}

function NavButton(props: { icon: IconName; label: string; hint?: string; alwaysHint?: boolean; active?: boolean; pulse?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      aria-current={props.active ? "page" : undefined}
      className={cn(
        "motion-fast group relative flex h-10 items-center gap-3 rounded-r2 px-3 text-[14px] transition-colors",
        props.active ? "bg-row-hover font-semibold text-fg" : "text-fg hover:bg-hover",
      )}
    >
      {props.active && <span aria-hidden className="absolute -left-1 top-1/2 size-1.5 -translate-y-1/2 rounded-full bg-accent" />}
      <Icon name={props.icon} size={17} className={cn(props.pulse && "animate-pulse text-accent")} />
      <span className="flex-1 text-left">{props.label}</span>
      {props.hint && (
        <span className={cn("text-xs text-fg-subtle transition-opacity", props.alwaysHint ? "opacity-100" : "opacity-0 group-hover:opacity-100")}>{props.hint}</span>
      )}
    </button>
  );
}
