import { useCallback, useEffect, useState } from "react";
import { Titlebar } from "./components/Titlebar";
import { AppDialog, AppMenu, Button, Field, HintProvider, Icon, IconButton, type IconName } from "./components/ui";
import { applyAppearance, type Appearance } from "./lib/appearance";
import { cn } from "./lib/cn";
import { dispatchTask, useTask, wireTaskEvents, wireVoiceEvents } from "./lib/stores";
import { core } from "./lib/tauri";
import { useCoreEvent, useCoreStatus } from "./lib/useCore";
import { AboutView } from "./views/AboutView";
import { BrainView } from "./views/BrainView";
import { ActivityView } from "./views/ActivityView";
import { HistoryView } from "./views/HistoryView";
import { HarnessView } from "./views/HarnessView";
import { JournalView } from "./views/JournalView";
import { LabView } from "./views/LabView";
import { LibraryView } from "./views/LibraryView";
import { YouView } from "./views/YouView";
import { SettingsView } from "./views/SettingsView";
import { startTask, TaskView } from "./views/task/TaskView";
import { wireMainWindow } from "./lib/windowing";

// Main.qml: barra lateral (navegacao + conversas) e a tela da aba escolhida. Atalhos iguais aos do QML.

export type Page =
  | "task" | "history" | "activity" | "brain" | "you" | "journal" | "library" | "lab" | "harness" | "settings" | "about";

const NAV: Array<{ page: Page; label: string; icon: IconName; group: 1 | 2 | 3; key?: string }> = [
  { page: "history", label: "Histórico", icon: "history", group: 1, key: "Ctrl H" },
  { page: "activity", label: "Atividade", icon: "chart", group: 1 },
  { page: "brain", label: "Cérebro", icon: "brain", group: 2, key: "Ctrl B" },
  { page: "you", label: "Você", icon: "user", group: 2 },
  { page: "journal", label: "Diário", icon: "file-text", group: 2 },
  { page: "library", label: "Biblioteca", icon: "box", group: 2 },
  { page: "lab", label: "AI Research Lab", icon: "sparkle", group: 3 },
  { page: "harness", label: "Harness", icon: "sliders", group: 3 },
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
  const [page, setPage] = useState<Page>("task");
  const [collapsed, setCollapsed] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [current, setCurrent] = useState("");
  const [modules, setModules] = useState<Record<string, boolean>>({});

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

  useEffect(() => {
    if (status !== "open") return;
    core().call("appearance").then((a) => applyAppearance(a as Appearance)).catch(() => {});
    core()
      .call("harnessGet")
      .then((r) => setModules(((r as { harness?: { modules?: Record<string, boolean> } }).harness?.modules) ?? {}))
      .catch(() => {});
    refreshConversations();
  }, [status, refreshConversations]);

  useCoreEvent("conversationsChanged", refreshConversations);
  useCoreEvent("sessionReset", refreshConversations);

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
      else if (k === "escape" && task.busy) void core().call("forceStop");
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [newConversation, task.busy]);

  return (
    <HintProvider>
      <div className="flex h-full flex-col">
        <Titlebar>
          <StatusPill status={status} />
        </Titlebar>
        <div className="flex min-h-0 flex-1">
          {!collapsed && (
            <Sidebar
              page={page}
              setPage={setPage}
              task={task}
              conversations={conversations}
              modules={modules}
              current={current}
              onNew={newConversation}
              onOpen={openConversation}
            />
          )}
          <main className="relative min-w-0 flex-1 bg-canvas">
            <IconButton
              icon={collapsed ? "chevron-right" : "list"}
              label={collapsed ? "Mostrar barra lateral (Ctrl \\)" : "Esconder barra lateral (Ctrl \\)"}
              flat
              onClick={() => setCollapsed((c) => !c)}
              className="absolute left-3 top-3 z-10"
            />
            <PageView page={page} go={setPage} onHarness={(m) => setModules(m)} />
          </main>
        </div>
      </div>
    </HintProvider>
  );
}

function PageView({ page, go, onHarness }: { page: Page; go: (p: Page) => void; onHarness: (modules: Record<string, boolean>) => void }) {
  switch (page) {
    case "task":
      return <TaskView />;
    case "history":
      return <HistoryView />;
    case "activity":
      return <ActivityView onAnswer={() => go("task")} />;
    case "you":
      return <YouView onOpenBrain={() => go("brain")} />;
    case "library":
      return <LibraryView />;
    case "harness":
      return <HarnessView onChanged={(h) => onHarness(h.modules)} />;
    case "lab":
      return <LabView />;
    case "journal":
      return <JournalView />;
    case "brain":
      return <BrainView onOpenYou={() => go("you")} />;
    case "about":
      return <AboutView />;
    case "settings":
      return <SettingsView />;
  }
}

function Sidebar(props: {
  page: Page;
  setPage: (p: Page) => void;
  task: ReturnType<typeof useTask>;
  conversations: Conversation[];
  modules: Record<string, boolean>;
  current: string;
  onNew: () => void;
  onOpen: (id: string) => void;
}) {
  const { page, setPage, task } = props;
  const [query, setQuery] = useState("");
  const [renaming, setRenaming] = useState<Conversation | null>(null);
  const [deleting, setDeleting] = useState<Conversation | null>(null);
  const [title, setTitle] = useState("");
  const list = props.conversations.filter((c) => c.title.toLowerCase().includes(query.trim().toLowerCase()));
  const idle = task.status === "idle";

  return (
    <nav aria-label="Navegação" className="flex w-64 shrink-0 flex-col border-r border-hairline bg-sidebar px-2.5 pb-3 pt-14 backdrop-blur-xl">
      <NavButton icon="plus" label="Nova conversa" hint="Ctrl N" active={page === "task" && idle && task.turns.length === 0} onClick={props.onNew} />
      {!idle && (
        <NavButton icon={task.busy ? "play" : "message"} label={task.busy ? "Em execução" : "Tarefa atual"} active={page === "task"} onClick={() => setPage("task")} pulse={task.busy} />
      )}
      {[1, 2, 3].map((g) => (
        <div key={g} className="mt-3 flex flex-col gap-0.5 border-t border-hairline pt-3 first-of-type:border-0">
          {NAV.filter((n) => n.group === g && props.modules[n.page] !== false).map((n) => (
            <NavButton key={n.page} icon={n.icon} label={n.label} hint={n.key} active={page === n.page} onClick={() => setPage(n.page)} />
          ))}
        </div>
      ))}

      <div className="mt-4 flex min-h-0 flex-1 flex-col border-t border-hairline pt-3">
        <p className="mb-2 px-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-subtle">Conversas</p>
        {props.conversations.length > 4 && (
          <Field value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar conversa" aria-label="Buscar conversa" className="mb-2 h-8 text-sm" />
        )}
        <ul className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
          {list.map((c) => (
            <li key={c.id} className="group relative">
              <button
                type="button"
                onClick={() => props.onOpen(c.id)}
                disabled={task.busy}
                className={cn(
                  "motion-fast flex h-8 w-full items-center rounded-r2 pl-2.5 pr-9 text-left text-[13px] transition-colors disabled:opacity-50",
                  c.id === props.current && page === "task" ? "bg-row-hover text-fg" : "text-fg-muted hover:bg-hover hover:text-fg",
                )}
              >
                <span className="truncate">{c.title}</span>
              </button>
              <span className="absolute right-0.5 top-0 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
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
          {props.conversations.length === 0 && <li className="px-2.5 text-[13px] text-fg-subtle">As conversas salvas aparecem aqui.</li>}
        </ul>
      </div>

      <NavButton icon="settings" label="Configurações" hint="Ctrl ," active={page === "settings"} onClick={() => setPage("settings")} />
      <NavButton icon="info" label="Sobre" active={page === "about"} onClick={() => setPage("about")} />

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

function NavButton(props: { icon: IconName; label: string; hint?: string; active?: boolean; pulse?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      aria-current={props.active ? "page" : undefined}
      className={cn(
        "motion-fast group flex h-9 items-center gap-2.5 rounded-r2 px-2.5 text-[13px] transition-colors",
        props.active ? "bg-row-hover font-medium text-fg" : "text-fg-muted hover:bg-hover hover:text-fg",
      )}
    >
      <Icon name={props.icon} size={16} className={cn(props.pulse && "animate-pulse text-accent")} />
      <span className="flex-1 text-left">{props.label}</span>
      {props.hint && <span className="text-xs text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100">{props.hint}</span>}
    </button>
  );
}

function StatusPill({ status }: { status: string }) {
  if (status === "open") return null;
  const label = status === "connecting" ? "conectando ao núcleo…" : "núcleo desconectado";
  return (
    <span role="status" className="flex items-center gap-2 text-xs text-fg-muted">
      <span className={cn("size-2 rounded-full", status === "connecting" ? "bg-warn" : "bg-bad")} />
      {label}
    </span>
  );
}
