// Ponte com a casca Rust (src-tauri). Fora do Tauri (vite sozinho no navegador) nada disso existe.

import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { CoreClient, type CoreInfo } from "./core";

export const inTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

/** Porta e token do nucleo. O Rust espera o sidecar anunciar; erro se ele nao subiu. */
export function coreInfo(): Promise<CoreInfo> {
  if (!inTauri) return Promise.reject(new Error("abra pela casca Tauri (npm run tauri dev)"));
  return invoke<CoreInfo>("core_info");
}

export function restartCore(): Promise<void> {
  return invoke("restart_core");
}

export const appWindow = () => getCurrentWindow();

let shared: CoreClient | null = null;

/** Um cliente por janela, ligado ao nucleo que a casca subiu. */
export function core(): CoreClient {
  if (!shared) {
    shared = new CoreClient({ getInfo: coreInfo });
    shared.start();
  }
  return shared;
}
