import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { CommandPalette, type PaletteItem } from "./components/CommandPalette";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { dragArea, ResizeEdges, useWindowState, WindowControls } from "./components/WindowChrome";
import { NavRail } from "./components/NavRail";
import { SectionLetter } from "./components/SectionLetter";
import { Splash } from "./components/Splash";
import { AppDialog, AppMenu, Button, Field, HintProvider, Icon, IconButton, Skeleton, type IconName } from "./components/ui";
import { applyAppearance, readLook, rememberLook, type Appearance } from "./lib/appearance";
import { cn } from "./lib/cn";
import { core, demoMode, inQt, wallpaperUrl } from "./lib/host";
import { generativeOf } from "./lib/generative";
import { GenerativeCanvas } from "./components/GenerativeCanvas";
import { readPrefs } from "./lib/wallpaper/art";
import { dispatchTask, taskStore, useTask, wireTaskEvents, wireVoiceEvents } from "./lib/stores";
import { useCoreEvent, useCoreStatus } from "./lib/useCore";
import { wireMainWindow } from "./lib/windowing";
import type { Harness } from "./views/HarnessView";
import { startTask, TaskView } from "./views/task/TaskView";

// Telas carregadas sob demanda: a Conversa abre logo; o resto (Markdown, grafo, Lab...) so quando visitado.
const ActivityView = lazy(() => import("./views/ActivityView").then((m) => ({ default: m.ActivityView })));
const BrainView = lazy(() => import("./views/BrainView").then((m) => ({ default: m.BrainView })));
const HarnessView = lazy(() => import("./views/HarnessView").then((m) => ({ default: m.HarnessView })));
const HistoryView = lazy(() => import("./views/HistoryView").then((m) => ({ default: m.HistoryView })));
const JournalView = lazy(() => import("./views/JournalView").then((m) => ({ default: m.JournalView })));
const LabView = lazy(() => import("./views/lab/LabView").then((m) => ({ default: m.LabView })));
const LibraryView = lazy(() => import("./views/LibraryView").then((m) => ({ default: m.LibraryView })));

// Depois que a Conversa abre, as outras telas carregam em segundo plano (ocioso): a primeira visita a cada uma
// ja nao mostra esqueleto, e o tempo de abertura do app continua o mesmo.
const PRELOAD = [
  () => import("./views/HistoryView"),
  () => import("./views/ActivityView"),
  () => import("./views/BrainView"),
  () => import("./views/JournalView"),
  () => import("./views/LibraryView"),
  () => import("./views/lab/LabView"),
  () => import("./views/HarnessView"),
];
function preloadViews() {
  let index = 0;
  let timer = 0;
  let stopped = false;
  const idle = typeof window.requestIdleCallback === "function";
  function queue() {
    if (stopped || index >= PRELOAD.length) return;
    timer = idle ? window.requestIdleCallback(load) : window.setTimeout(load, 1500);
  }
  function load() {
    if (!stopped) void PRELOAD[index++]?.().then(queue, queue);
  }
  queue();
  return () => {
    stopped = true;
    if (idle) window.cancelIdleCallback(timer);
    else window.clearTimeout(timer);
  };
}

// Main: marca, busca, navegacao em grupos (Trabalho, Conhecimento, Sistema), conversas e status;
// cabecalho com o titulo da tela e "quem atende o pedido". Atalhos: Ctrl+N, Ctrl+H, Ctrl+B, Ctrl+, e Ctrl+\.

export type Page =
  | "task" | "history" | "activity" | "brain" | "journal" | "library" | "lab" | "settings";

const TITLES: Record<Page, string> = {
  task: "Conversa", history: "Histórico", activity: "Atividade", brain: "Cérebro", journal: "Diário",
  library: "Biblioteca", lab: "AI Research Lab", settings: "Configurações",
};

type Group = "Trabalho" | "Conhecimento" | "Sistema";
const NAV: Array<{ page: Page; label: string; icon: IconName; group: Group; key?: string; module?: string }> = [
  { page: "history", label: "Histórico", icon: "nav-history", group: "Trabalho", key: "Ctrl H", module: "history" },
  { page: "activity", label: "Atividade", icon: "nav-activity", group: "Trabalho" },
  { page: "brain", label: "Cérebro", icon: "nav-brain", group: "Conhecimento", key: "Ctrl B", module: "brain" },
  { page: "journal", label: "Diário", icon: "nav-journal", group: "Conhecimento" },
  { page: "library", label: "Biblioteca", icon: "nav-library", group: "Conhecimento" },
  { page: "lab", label: "AI Research Lab", icon: "nav-lab", group: "Sistema" },
  { page: "settings", label: "Configurações", icon: "nav-settings", group: "Sistema", key: "Ctrl ," },
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
  // Abertura uma vez por inicio do app (?nosplash pula: revisao de telas no navegador)
  const [splash, setSplash] = useState(() => !new URLSearchParams(window.location.search).has("nosplash") && !(demoMode && window.location.hash));
  const [collapsed, setCollapsed] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [current, setCurrent] = useState("");
  const conversationRevision = useRef(0);
  const restoredConversation = useRef(false);
  const [harness, setHarness] = useState<Harness | null>(null);
  const [appearanceReady, setAppearanceReady] = useState(false);
  const [lookPreview, setLookPreview] = useState<Appearance | null>(null);
  const [suggestions, setSuggestions] = useState(0);
  const [palette, setPalette] = useState(false);
  const [deep, setDeep] = useState<{ topic?: string; entry?: string; profile?: boolean; at: number }>({ at: 0 });
  const modules = harness?.modules ?? {};

  const refreshConversations = useCallback(() => {
    core()
      .call("loadConversations", false)
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

  useEffect(preloadViews, []);

  useEffect(() => {
    if (status !== "open") return;
    let active = true;
    const revision = conversationRevision.current;
    // Configuracoes > Interface > "Abertura ao iniciar" desligada: entra direto
    core()
      .call("uiSettings")
      .then((u) => (u as { splash?: boolean }).splash === false && setSplash(false))
      .catch(() => {});
    core()
      .call("harnessGet")
      .then((r) => {
        const h = (r as { harness?: Harness }).harness ?? null;
        if (active) setHarness(h);
      })
      .catch(() => {})
      .finally(() => { if (active) setAppearanceReady(true); });
    if (restoredConversation.current) refreshConversations();
    else {
      void core().call("loadConversations", true).then((result) => {
        if (!active || revision !== conversationRevision.current) return;
        const v = result as { items?: Conversation[]; current?: string; turns?: Array<Record<string, unknown>> };
        restoredConversation.current = true;
        setConversations(v.items ?? []);
        setCurrent(v.current ?? "");
        if (v.turns?.length && !taskStore.get().busy) dispatchTask({ type: "showConversation", turns: v.turns });
      }).catch(() => {});
    }
    refreshSuggestions();
    return () => { active = false; };
  }, [status, refreshConversations, refreshSuggestions]);

  useCoreEvent("conversationsChanged", refreshConversations);
  useCoreEvent("sessionReset", refreshConversations);
  useCoreEvent("historyChanged", refreshSuggestions);

  // A voz é executada pelo núcleo. A interface só acompanha a tarefa já aceita.
  const onVoiceCommand = useCallback((p: unknown) => {
    const v = (p ?? {}) as { text?: string; heard?: string; executing?: boolean };
    const text = (v.text ?? "").trim();
    if (!text || (taskStore.get().busy && !v.executing)) return;
    setPage("task");
    if (v.executing) dispatchTask({ type: "start", text, heard: v.heard, dryRun: false, now: Date.now() });
    else startTask(text, { dryRun: false, report: false }, v.heard || "");
  }, []);
  useCoreEvent("voiceCommand", onVoiceCommand);
  // Confirmacao de efeito (enviar, pagar, excluir): a conversa vem para a frente, mesmo minimizada
  const onPlanReview = useCallback((p: unknown) => {
    if (!(p as { effect?: unknown } | null)?.effect) return;
    setPage("task");
    if (inQt) void core().call("restoreMain");
  }, []);
  useCoreEvent("planReview", onPlanReview);

  const newConversation = useCallback(() => {
    if (task.busy) return;
    conversationRevision.current++;
    setPage("task");
    dispatchTask({ type: "newConversation" });
    void core().call("newSession");
  }, [task.busy]);

  const openConversation = useCallback(
    (id: string) => {
      if (task.busy) return;
      const revision = ++conversationRevision.current;
      core()
        .call("openConversation", id)
        .then((d) => {
          const v = d as { turns?: Array<Record<string, unknown>> };
          if (revision !== conversationRevision.current || !v.turns) return;
          dispatchTask({ type: "showConversation", turns: v.turns });
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
      else if (splash) return;
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [newConversation, task.busy, page, splash]);

  const visibleNav = NAV.filter((n) => !n.module || modules[n.module] !== false);

  const paletteBase = useMemo<PaletteItem[]>(
    () => [
      { id: "new", title: "Nova conversa", area: "Ação", icon: "pen", hint: "Ctrl N", run: newConversation },
      ...visibleNav.map((n) => ({ id: n.page, title: n.label, area: "Ir para", icon: n.icon, hint: n.key, run: () => setPage(n.page) })),
      { id: "diary-profile", title: "Como trabalhar comigo", area: "Diário", icon: "user", run: () => {
        setDeep({ profile: true, at: Date.now() });
        setPage("journal");
      } },
      ...conversations.map((c) => ({ id: `c:${c.id}`, title: c.title, area: "Conversa", icon: "message" as IconName, run: () => openConversation(c.id) })),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [newConversation, modules, conversations, openConversation],
  );

  const onTopic = useCallback((id: string) => (setDeep({ topic: id, at: Date.now() }), setPage("library")), []);
  const onDiary = useCallback((id: string) => (setDeep({ entry: id, at: Date.now() }), setPage("journal")), []);
  // Ate o Harness responder, o papel de parede da ultima vez (a abertura ja mostra o fundo certo)
  const [cachedLook] = useState(readLook);
  const appearance: Appearance | undefined = lookPreview ?? (harness?.appearance as Appearance | undefined) ?? cachedLook.appearance;
  useLayoutEffect(() => applyAppearance(appearance), [appearance]);
  const wallpaper = String(appearance?.wallpaper ?? (harness || lookPreview ? "" : cachedLook.wallpaper ?? ""));
  const [unavailablePhoto, setUnavailablePhoto] = useState("");
  useEffect(() => { setUnavailablePhoto(""); }, [wallpaper]);
  const photo = unavailablePhoto === wallpaper ? null : wallpaperUrl(wallpaper);
  // Papel gerativo: desenhado com as cores da paleta; conta como foto no tema escuro.
  const generative = useMemo(() => generativeOf(wallpaper), [wallpaper]);
  // opcoes avancadas do papel de parede gerativo (Aparencia > Avancado)
  const artPrefs = useMemo(() => readPrefs(appearance?.art), [appearance?.art]);
  const look = `${appearance?.mode ?? ""}|${appearance?.palette ?? ""}|${appearance?.accent ?? ""}`;
  const dark = appearance?.mode !== "claro";
  // Medicao da foto (core/wallpapers.py): escurecimento/veu minimo para o texto solto ler com
  // AA sobre o quarto mais claro (ou mais escuro) da imagem, e o reforco do vidro dos paineis.
  type PhotoMeasure = { min_dim?: number; min_veil?: number; glass_boost?: number };
  const [measuredPhoto, setMeasuredPhoto] = useState<{ id: string; value?: PhotoMeasure } | null>(null);
  const measure = measuredPhoto?.id === wallpaper ? measuredPhoto.value : undefined;
  useEffect(() => {
    if (!photo || status !== "open") return;
    let active = true;
    core()
      .call("wallpaperInfo", wallpaper)
      .then((r) => {
        if (active) setMeasuredPhoto({ id: wallpaper, value: (r as { item?: { palette?: PhotoMeasure } }).item?.palette });
      })
      .catch(() => {});
    return () => { active = false; };
  }, [photo, wallpaper, status]);
  // Margem sobre a medicao: ela usa um cinza de referencia; o texto secundario do app e um pouco mais fraco.
  // Veu leve: a foto continua sendo a foto. Quem garante a leitura e o material de cada painel (vidro com desfoque)
  // e o halo do texto solto; antes este veu chegava a 60-70% e apagava o papel de parede.
  const floor = measure ? (dark ? measure.min_dim ?? 0 : measure.min_veil ?? 0) * 0.35 : 0.08;
  const dim = Math.min(0.45, Math.max(Number(appearance?.dim ?? 0.35) * 0.5, floor));
  useLayoutEffect(() => {
    const root = document.documentElement;
    // O gerativo no tema escuro se comporta como foto (vidro, tinta clara sobre o fundo). No claro ele e um fundo
    // claro: a interface segue o tema normal (texto escuro); com "foto" o texto ficava branco sobre fundo claro.
    const photoLike = !!photo || (!!generative && dark);
    root.dataset.photo = photoLike ? "on" : "off";
    root.style.setProperty("--glass-boost", String(photo ? Math.min(0.24, measure?.glass_boost ?? 0.08) : photoLike ? 0.1 : 0));
  }, [photo, generative, dark, measure]);

  // Aparencia e papel de parede atuais guardados a cada mudanca (abrir o app ou trocar no Harness): a abertura da
  // proxima vez nasce com eles. Antes so gravava ao abrir, entao trocar o fundo no Harness deixava o antigo guardado
  // e a abertura mostrava o fundo anterior antes de voltar ao certo.
  useEffect(() => {
    if (!harness) return;
    rememberLook({ appearance: harness.appearance as Appearance, wallpaper: String(harness.appearance.wallpaper ?? "") });
  }, [harness]);

  const win = useWindowState();
  const drag = dragArea(win.toggle);

  return (
    <HintProvider>
      <div className="relative flex h-full">
        {/* Fundo: foto do Harness ou as luzes da paleta */}
        {photo || generative ? (
          <div aria-hidden className="pointer-events-none absolute inset-0">
            {generative ? <GenerativeCanvas art={generative} look={look} className="size-full" live prefs={artPrefs} />
              : <img src={photo!} alt="" className="size-full object-cover" onError={() => setUnavailablePhoto(wallpaper)} />}
            <div className="absolute inset-0" style={{ background: "var(--bg-base)", opacity: dim, transition: "opacity var(--dur-slow) var(--ease-out)" }} />
          </div>
        ) : (
          <div aria-hidden className="ambient pointer-events-none absolute inset-0" />
        )}
        <div className={`relative flex h-full w-full ${splash ? "invisible" : ""}`}>
        <ResizeEdges maximized={win.maximized} />
        {collapsed ? (
          <NavRail
            onExpand={() => setCollapsed(false)}
            items={[
              { id: "new", label: "Nova conversa", icon: "nav-new", hint: "Ctrl N", onClick: newConversation },
              ...(task.busy ? [{ id: "task", label: "Em execução", icon: "play" as IconName, pulse: true, active: page === "task", onClick: () => setPage("task") }] : []),
              { id: "search", label: "Buscar", icon: "nav-search", hint: "Ctrl K", onClick: () => setPalette(true) },
              ...visibleNav.map((n) => ({ id: n.page, label: n.label, icon: n.icon, hint: n.key, active: page === n.page, onClick: () => setPage(n.page) })),
            ]}
          />
        ) : (
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
            drag={drag}
          />
        )}
        <main className="relative flex min-w-0 flex-1 flex-col">
          {/* Topo: parte do app (mesmo fundo), arrastavel; os controles da janela ficam aqui, sem faixa separada */}
          <header {...drag} className="flex h-12 shrink-0 select-none items-center gap-1 pl-2 pr-1.5">
            <IconButton
              icon="sidebar"
              label={collapsed ? "Mostrar barra lateral (Ctrl \\)" : "Esconder barra lateral (Ctrl \\)"}
              flat
              className="size-8"
              onClick={() => setCollapsed((c) => !c)}
            />
            {page !== "task" && <h1 className="photo-ink-muted ml-1 text-[13px] font-medium text-fg-muted">{TITLES[page]}</h1>}
            <span className="flex-1" />
            <IconButton icon="pen" label="Nova conversa (Ctrl N)" flat className="size-8" onClick={newConversation} disabled={task.busy} />
            <SectionLetter key={page} page={page} title={TITLES[page]} />
            <WindowControls maximized={win.maximized} toggle={win.toggle} />
          </header>
          <div className="relative min-h-0 flex-1">
            <Suspense fallback={<div className="mx-auto max-w-5xl px-8 py-12"><Skeleton className="h-10 w-56 rounded-r2" /><Skeleton className="mt-6 h-64 rounded-r4" /></div>}>
              <ErrorBoundary resetKey={page} onHome={() => setPage("task")}>
                {/* key: cada troca de tela refaz a entrada suave */}
                <div key={page} className="h-full">
                  <PageView page={page} go={setPage} deep={deep} harness={harness} onHarness={setHarness} onAppearancePreview={setLookPreview} />
                </div>
              </ErrorBoundary>
            </Suspense>
          </div>
        </main>
        </div>
        {splash && <Splash coreReady={status === "open" && appearanceReady} onDone={() => setSplash(false)} />}
        <CommandPalette open={palette} onOpenChange={setPalette} base={paletteBase} onTopic={onTopic} onDiary={onDiary} />
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
  onAppearancePreview,
}: {
  page: Page;
  go: (p: Page) => void;
  deep: { topic?: string; entry?: string; profile?: boolean; at: number };
  harness: Harness | null;
  onHarness: (h: Harness) => void;
  onAppearancePreview: (look: Appearance | null) => void;
}) {
  switch (page) {
    case "task":
      return <TaskView dev={harness?.dev} />;
    case "history":
      return <HistoryView />;
    case "activity":
      return <ActivityView onAnswer={() => go("task")} />;
    case "library":
      return <LibraryView key={`lib-${deep.at}`} openTopic={deep.topic} />;
    case "settings":
      return <HarnessView onChanged={onHarness} onPreview={onAppearancePreview} onOpenLab={() => go("lab")} />;
    case "lab":
      return <LabView />;
    case "journal":
      return <JournalView key={`diary-${deep.at}`} initialEntry={deep.entry} initialProfile={deep.profile} onOpenBrain={() => go("brain")} />;
    case "brain":
      return <BrainView />;
  }
}

function BrandMark({ size = 22 }: { size?: number }) {
  // BrandMark: quatro quadrados, o ultimo na cor de destaque
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
  drag: ReturnType<typeof dragArea>;
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
    <nav aria-label="Navegação" className="sidebar-panel relative z-10 m-2 mr-0 flex w-[248px] shrink-0 flex-col rounded-[18px] px-2.5 pb-2.5">
      <div {...props.drag} className="flex h-12 shrink-0 select-none items-center gap-2.5 px-2 text-fg">
        <BrandMark size={20} />
        <span className="text-[15px] font-semibold tracking-[-0.02em]">Creative AIx</span>
      </div>
      <button
        type="button"
        onClick={props.onSearch}
        className="motion-fast mb-1 flex h-8 items-center gap-2 rounded-r2 border border-hairline bg-chip px-2.5 text-[13px] text-fg-muted transition-colors hover:text-fg"
      >
        <Icon name="nav-search" size={14} />
        <span className="flex-1 text-left">Buscar</span>
        <kbd className="rounded-[5px] border border-hairline px-1.5 font-sans text-[11px] text-fg-subtle">Ctrl K</kbd>
      </button>

      {groups.map((g) => (
        <div key={g} className="mt-3 flex flex-col gap-px">
          <p className="mb-1 px-2.5 text-[11px] font-medium text-fg-subtle">{g}</p>
          {g === "Trabalho" && (
            <>
              <NavButton icon="nav-new" label="Nova conversa" active={page === "task" && idle && task.turns.length === 0} onClick={props.onNew} />
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
        <div className="mb-1 flex items-center gap-2 px-2.5">
          <p className="flex-1 text-[11px] font-medium text-fg-subtle">Conversas</p>
        </div>
        {props.conversations.length > 6 && (
          <label className="relative mb-1.5 block">
            <Icon name="search" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-subtle" />
            <Field value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filtrar" aria-label="Buscar conversas" className="h-8 rounded-r2 pl-8 text-[13px]" />
          </label>
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
              <span className="absolute right-0.5 top-0.5 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
                <AppMenu
                  trigger={<IconButton icon="more" label={`Ações de ${c.title}`} flat className="size-8" />}
                  items={[
                    { label: "Renomear", icon: "edit", onSelect: () => (setTitle(c.title), setRenaming(c)) },
                    { label: "Apagar", icon: "trash", danger: true, onSelect: () => setDeleting(c) },
                  ]}
                />
              </span>
            </li>
          ))}
          {props.conversations.length === 0 && <li className="px-3 text-[13px] text-fg-subtle">As conversas salvas aparecem aqui.</li>}
        </ul>
      </div>

      <p role="status" className="mt-2 flex items-center gap-2 px-2.5 pt-2 text-[12px] text-fg-subtle">
        <span className={cn("size-1.5 rounded-full", props.status !== "open" ? "bg-warn" : task.busy ? "animate-pulse bg-accent" : "bg-ok")} />
        {props.status !== "open" ? "Conectando ao núcleo…" : task.busy ? "Executando…" : "Pronto"}
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
        "motion-fast group relative flex h-8 items-center gap-2.5 rounded-r2 px-2.5 text-[13.5px] transition-colors",
        props.active ? "bg-row-hover font-medium text-fg shadow-[inset_0_0_0_1px_var(--hairline)]" : "text-fg-muted hover:bg-hover hover:text-fg",
      )}
    >
      <Icon name={props.icon} size={16} weight={1.75} className={cn("shrink-0", props.active ? "text-fg" : "text-fg-muted group-hover:text-fg", props.pulse && "animate-pulse text-accent-ink")} />
      <span className="flex-1 truncate text-left">{props.label}</span>
      {props.hint && (
        <span className={cn("text-[11px] text-fg-subtle transition-opacity", props.alwaysHint ? "opacity-100" : "opacity-0 group-hover:opacity-100")}>{props.hint}</span>
      )}
    </button>
  );
}
