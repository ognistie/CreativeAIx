// Ponte com a casca Rust (src-tauri). Fora do Tauri (vite sozinho no navegador) nada disso existe,
// exceto o modo demonstracao (?demo), que usa um nucleo falso para revisar as telas.

import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { mockSocket } from "../demo/mockCore";
import { CoreClient, type CoreInfo } from "./core";

export const inTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
export const demoMode = !inTauri && typeof window !== "undefined" && new URLSearchParams(window.location.search).has("demo");

/** Porta e token do nucleo. O Rust espera o sidecar anunciar; erro se ele nao subiu. */
export function coreInfo(): Promise<CoreInfo> {
  if (demoMode) return Promise.resolve({ port: 0, token: "demo" });
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
    shared = new CoreClient({ getInfo: coreInfo, makeSocket: demoMode ? () => mockSocket() : undefined });
    shared.start();
  }
  return shared;
}

/** Abre um link https no navegador padrao (plugin opener, escopo so https). */
export async function openExternal(url: string): Promise<void> {
  if (!/^https:\/\//.test(url)) return;
  if (!inTauri) {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }
  const { openUrl } = await import("@tauri-apps/plugin-opener");
  await openUrl(url);
}

/** Escolher arquivos (plugin dialog). Devolve os caminhos ou [] se cancelar. */
export async function pickFiles(): Promise<string[]> {
  if (!inTauri) return [];
  const { open } = await import("@tauri-apps/plugin-dialog");
  const picked = await open({ multiple: true, directory: false, title: "Anexar arquivos" });
  if (!picked) return [];
  return Array.isArray(picked) ? picked : [picked];
}

export interface UpdateInfo {
  version: string;
  notes: string | null;
}

/** Versao nova assinada? null se nao ha ou se a atualizacao automatica esta desligada neste build. */
export function checkUpdate(): Promise<UpdateInfo | null> {
  if (!inTauri) return Promise.resolve(null);
  return invoke<UpdateInfo | null>("check_update");
}

export function installUpdate(): Promise<void> {
  return invoke("install_update");
}
