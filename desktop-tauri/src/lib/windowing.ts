// Ligacao entre as duas janelas (principal e mini chat) e a casca Rust (src-tauri/src/mini_window.rs).
//
// A principal e a fonte da verdade da conversa: manda o estado da tarefa para o mini chat por evento
// Tauri e recebe dele os pedidos digitados la. O nucleo pede a troca de janela (windowRequest) quando o
// agente vai para outro app; o atalho Alt+Espaco chega como quickEntry.

import { invoke } from "@tauri-apps/api/core";
import { emitTo, listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import type { TaskState } from "./taskStore";
import { taskStore } from "./stores";
import { core, inTauri } from "./tauri";

export const TASK_STATE_EVENT = "task-state";
export const MINI_SUBMIT_EVENT = "mini-submit";
export const MINI_READY_EVENT = "mini-ready";

const call = (cmd: string, args?: Record<string, unknown>) => {
  if (inTauri) invoke(cmd, args).catch((e: unknown) => console.warn(`[janela] ${cmd}:`, e));
};

export const restoreMain = () => call("restore_main");
export const closeMini = () => call("close_mini");

/** Janela principal: liga nucleo, mini chat e casca. Chamar uma vez. */
export function wireMainWindow(onMiniSubmit: (text: string) => void): void {
  if (!inTauri) return;
  let miniOpen = false;

  core().on("windowRequest", (p: unknown) => {
    const action = (p as { action?: string } | null)?.action;
    if (action === "enter_mini") {
      miniOpen = true;
      call("enter_mini", { busy: taskStore.get().busy });
    }
  });
  core().on("quickEntry", () => {
    miniOpen = true;
    call("quick_entry");
  });

  // Estado da tarefa -> mini chat (no maximo ~20 vezes por segundo)
  let pending: ReturnType<typeof setTimeout> | null = null;
  let lastBusy = taskStore.get().busy;
  const send = () => {
    pending = null;
    void emitTo("mini", TASK_STATE_EVENT, taskStore.get());
  };
  taskStore.subscribe(() => {
    const s = taskStore.get();
    if (s.busy !== lastBusy) {
      lastBusy = s.busy;
      if (miniOpen) call("set_mini_busy", { busy: s.busy });
    }
    if (!pending) pending = setTimeout(send, 50);
  });

  void listen<{ text: string }>(MINI_SUBMIT_EVENT, (e) => onMiniSubmit(e.payload.text));
  void listen(MINI_READY_EVENT, send);

  // Voltou para a janela principal (barra de tarefas, Alt+Tab): o mini chat sai de cena
  void getCurrentWindow().onFocusChanged(({ payload: focused }) => {
    if (focused && miniOpen) {
      miniOpen = false;
      call("close_mini");
    }
  });
}

/** Mini chat: recebe o estado da principal. Devolve a funcao que cancela. */
export function wireMiniWindow(onState: (s: TaskState) => void): void {
  if (!inTauri) return;
  void listen<TaskState>(TASK_STATE_EVENT, (e) => onState(e.payload));
  void emitTo("main", MINI_READY_EVENT, null);
}

export function submitFromMini(text: string): void {
  void emitTo("main", MINI_SUBMIT_EVENT, { text });
}
