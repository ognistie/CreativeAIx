// Ligacao entre as duas janelas (principal e mini chat).
//
// A principal e a fonte da verdade da conversa: manda o estado da tarefa para o mini chat e recebe dele
// os pedidos digitados la.
// BroadcastChannel: as duas paginas tem a mesma origem app://ui. A troca de janela e o acesso rapido sao do
// WindowMode no Python (desktop/window_mode.py).

import type { TaskState } from "./taskStore";
import { taskStore } from "./stores";
import { core, inQt } from "./host";

type Msg = { kind: "state"; state: TaskState } | { kind: "submit"; text: string } | { kind: "ready" };

const CHANNEL = "creative-aix-windows";
let channel: BroadcastChannel | null = null;
const bus = () => (channel ??= new BroadcastChannel(CHANNEL));

export function restoreMain(): void {
  if (inQt) void core().call("restoreMain");
}

export function closeMini(): void {
  if (inQt) void core().call("closeMini");
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
  }
}

/** Mini chat: recebe o estado da principal. */
export function wireMiniWindow(onState: (s: TaskState) => void): void {
  if (inQt) {
    bus().onmessage = (e: MessageEvent<Msg>) => {
      if (e.data.kind === "state") onState(e.data.state);
    };
    bus().postMessage({ kind: "ready" } satisfies Msg);
  }
}

export function submitFromMini(text: string): void {
  if (inQt) bus().postMessage({ kind: "submit", text } satisfies Msg);
}
