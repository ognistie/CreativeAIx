// Ligacao entre as duas janelas (principal e mini chat).
//
// A principal e a fonte da verdade da conversa: manda o estado da tarefa para o mini chat e recebe dele
// os pedidos digitados la.
//   app Qt  BroadcastChannel (as duas paginas tem a mesma origem app://ui). A troca de janela e o
//           acesso rapido sao do WindowMode no Python, como no app QML.
//   Tauri   eventos Tauri + comandos do mini_window.rs; o nucleo pede a troca por windowRequest.

import type { TaskState } from "./taskStore";
import { taskStore } from "./stores";
import { core, inQt, inTauri } from "./host";

type Msg = { kind: "state"; state: TaskState } | { kind: "submit"; text: string } | { kind: "ready" };

const CHANNEL = "creative-aix-windows";
let channel: BroadcastChannel | null = null;
const bus = () => (channel ??= new BroadcastChannel(CHANNEL));

async function tauriCall(cmd: string, args?: Record<string, unknown>) {
  const { invoke } = await import("@tauri-apps/api/core");
  invoke(cmd, args).catch((e: unknown) => console.warn(`[janela] ${cmd}:`, e));
}

export function restoreMain(): void {
  if (inQt) void core().call("restoreMain");
  else if (inTauri) void tauriCall("restore_main");
}

export function closeMini(): void {
  if (inQt) void core().call("closeMini");
  else if (inTauri) void tauriCall("close_mini");
}

/** Estado da tarefa -> mini chat (no maximo ~20 vezes por segundo). */
function relayState(send: () => void): void {
  let pending: ReturnType<typeof setTimeout> | null = null;
  taskStore.subscribe(() => {
    if (!pending)
      pending = setTimeout(() => {
        pending = null;
        send();
      }, 50);
  });
}

/** Janela principal: chamar uma vez. */
export function wireMainWindow(onMiniSubmit: (text: string) => void): void {
  if (inQt) {
    const send = () => bus().postMessage({ kind: "state", state: taskStore.get() } satisfies Msg);
    relayState(send);
    bus().onmessage = (e: MessageEvent<Msg>) => {
      if (e.data.kind === "submit") onMiniSubmit(e.data.text);
      else if (e.data.kind === "ready") send();
    };
    // Voltou para a janela principal: o mini chat sai de cena (WindowMode.main_activated)
    window.addEventListener("focus", () => void core().call("mainActivated"));
    return;
  }
  if (inTauri) void wireTauriMain(onMiniSubmit);
}

/** Mini chat: recebe o estado da principal. */
export function wireMiniWindow(onState: (s: TaskState) => void): void {
  if (inQt) {
    bus().onmessage = (e: MessageEvent<Msg>) => {
      if (e.data.kind === "state") onState(e.data.state);
    };
    bus().postMessage({ kind: "ready" } satisfies Msg);
    return;
  }
  if (inTauri) void wireTauriMini(onState);
}

export function submitFromMini(text: string): void {
  if (inQt) bus().postMessage({ kind: "submit", text } satisfies Msg);
  else if (inTauri) void import("@tauri-apps/api/event").then(({ emitTo }) => emitTo("main", "mini-submit", { text }));
}

// ── Casca Tauri ───────────────────────────────────────────────────
async function wireTauriMain(onMiniSubmit: (text: string) => void) {
  const { emitTo, listen } = await import("@tauri-apps/api/event");
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  let miniOpen = false;
  let lastBusy = taskStore.get().busy;
  core().on("windowRequest", (p: unknown) => {
    if ((p as { action?: string } | null)?.action === "enter_mini") {
      miniOpen = true;
      void tauriCall("enter_mini", { busy: taskStore.get().busy });
    }
  });
  core().on("quickEntry", () => {
    miniOpen = true;
    void tauriCall("quick_entry");
  });
  const send = () => void emitTo("mini", "task-state", taskStore.get());
  relayState(send);
  taskStore.subscribe(() => {
    const busy = taskStore.get().busy;
    if (busy !== lastBusy) {
      lastBusy = busy;
      if (miniOpen) void tauriCall("set_mini_busy", { busy });
    }
  });
  void listen<{ text: string }>("mini-submit", (e) => onMiniSubmit(e.payload.text));
  void listen("mini-ready", send);
  void getCurrentWindow().onFocusChanged(({ payload: focused }) => {
    if (focused && miniOpen) {
      miniOpen = false;
      void tauriCall("close_mini");
    }
  });
}

async function wireTauriMini(onState: (s: TaskState) => void) {
  const { emitTo, listen } = await import("@tauri-apps/api/event");
  void listen<TaskState>("task-state", (e) => onState(e.payload));
  void emitTo("main", "mini-ready", null);
}
