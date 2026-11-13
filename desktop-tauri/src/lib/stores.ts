// Estado compartilhado da janela: tarefa (taskStore) e voz. Um store simples com useSyncExternalStore.
// A janela principal e a fonte da verdade da conversa; o mini chat recebe o mesmo estado por evento Tauri.

import { useSyncExternalStore } from "react";
import { initialTaskState, TASK_EVENTS, taskReducer, type TaskAction, type TaskState } from "./taskStore";
import { core } from "./tauri";

export function createStore<S>(initial: S) {
  let state = initial;
  const listeners = new Set<() => void>();
  return {
    get: () => state,
    set(next: S) {
      if (next === state) return;
      state = next;
      listeners.forEach((l) => l());
    },
    subscribe(l: () => void) {
      listeners.add(l);
      return () => {
        listeners.delete(l);
      };
    },
  };
}

// ── Tarefa ───────────────────────────────────────────────────────
export const taskStore = createStore<TaskState>(initialTaskState);

export function dispatchTask(action: TaskAction): void {
  taskStore.set(taskReducer(taskStore.get(), action));
}

let taskWired = false;
/** Liga os eventos do nucleo ao reducer (uma vez por janela). */
export function wireTaskEvents(): void {
  if (taskWired) return;
  taskWired = true;
  for (const name of TASK_EVENTS) {
    core().on(name, (payload: unknown) => dispatchTask({ type: "event", name, payload, now: Date.now() }));
  }
}

export function useTask(): TaskState {
  return useSyncExternalStore(taskStore.subscribe, taskStore.get);
}

// ── Voz ──────────────────────────────────────────────────────────
export interface VoiceState {
  state: string; // idle | recording | transcribing | speaking | ...
  level: number;
  live: boolean;
  queued: number;
  hotkey: string;
  error: string;
  recStartedAt: number;
}

export const voiceStore = createStore<VoiceState>({
  state: "idle",
  level: 0,
  live: false,
  queued: 0,
  hotkey: "",
  error: "",
  recStartedAt: 0,
});

const prettyHotkey = (combo: string) =>
  combo
    .split("+")
    .map((k) => (k === "space" ? "Espaço" : k.charAt(0).toUpperCase() + k.slice(1)))
    .join("+");

let voiceWired = false;
export function wireVoiceEvents(): void {
  if (voiceWired) return;
  voiceWired = true;
  core().on("voiceState", (p: unknown) => {
    const v = (p ?? {}) as Record<string, unknown>;
    const cur = voiceStore.get();
    const state = String(v.state || "idle");
    voiceStore.set({
      ...cur,
      state,
      recStartedAt: state === "recording" && cur.state !== "recording" ? Date.now() : cur.recStartedAt,
      error: v.error
        ? "Microfone indisponível. Confira o microfone padrão do Windows (Configurações > Privacidade > Microfone) e tente de novo."
        : "",
      live: !!v.live,
      queued: Number(v.queued) || 0,
      hotkey: v.hotkey ? prettyHotkey(String(v.hotkey)) : cur.hotkey,
    });
  });
  core().on("voiceLevel", (p: unknown) => {
    voiceStore.set({ ...voiceStore.get(), level: Number((p as { level?: number } | null)?.level) || 0 });
  });
}

export function useVoice(): VoiceState {
  return useSyncExternalStore(voiceStore.subscribe, voiceStore.get);
}
