// Onde a interface esta rodando e como falar com o nucleo e com as janelas.
//
//   qt     app oficial: janelas Qt (desktop/web_host.py), porta e token injetados em window.__CREATIVE_AIX__
//   tauri  casca Tauri opcional (ui/src-tauri), porta e token pelo comando core_info
//   demo   navegador com ?demo: nucleo falso para revisar telas

import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { mockSocket } from "../demo/mockCore";
import { CoreClient, type CoreInfo } from "./core";

interface QtHostInfo extends CoreInfo {
  host: "qt";
  window: "index" | "mini";
}

declare global {
  interface Window {
    __CREATIVE_AIX__?: QtHostInfo;
  }
}

const qtInfo = typeof window !== "undefined" ? window.__CREATIVE_AIX__ : undefined;

export const inQt = !!qtInfo;
export const inTauri = !inQt && typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
export const demoMode = !inQt && !inTauri && typeof window !== "undefined" && new URLSearchParams(window.location.search).has("demo");
/** Ha uma casca de verdade (Qt ou Tauri) com janelas, dialogo de arquivos e nucleo. */
export const inApp = inQt || inTauri;

/** Porta e token do nucleo. */
export function coreInfo(): Promise<CoreInfo> {
  if (qtInfo) return Promise.resolve({ port: qtInfo.port, token: qtInfo.token });
  if (demoMode) return Promise.resolve({ port: 0, token: "demo" });
  if (!inTauri) return Promise.reject(new Error("abra pelo app Creative AIx"));
  return invoke<CoreInfo>("core_info");
}

/** Reiniciar o nucleo so existe na casca Tauri (no app Qt o nucleo e o proprio processo). */
export function restartCore(): Promise<void> {
  return invoke("restart_core");
}

export const appWindow = () => getCurrentWindow();

let shared: CoreClient | null = null;

/** Um cliente por janela, ligado ao nucleo. */
export function core(): CoreClient {
  if (!shared) {
    shared = new CoreClient({ getInfo: coreInfo, makeSocket: demoMode ? () => mockSocket() : undefined });
    shared.start();
  }
  return shared;
}

/** Abre um link https no navegador padrao. */
export async function openExternal(url: string): Promise<void> {
  if (!/^https:\/\//.test(url)) return;
  if (inQt) {
    await core().call("openExternal", url);
    return;
  }
  if (inTauri) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}

/** Escolher arquivos (dialogo do Windows). Devolve os caminhos ou [] se cancelar. */
export async function pickFiles(): Promise<string[]> {
  if (inQt) {
    const r = await core().call("pickFiles");
    return Array.isArray(r) ? (r as string[]) : [];
  }
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

/** Versao nova assinada? (so na casca Tauri com a feature de atualizacao) */
export function checkUpdate(): Promise<UpdateInfo | null> {
  if (!inTauri) return Promise.resolve(null);
  return invoke<UpdateInfo | null>("check_update");
}

export function installUpdate(): Promise<void> {
  return invoke("install_update");
}

/** Endereco de um papel de parede (so no app Qt, servido pelo app://wallpaper). */
export function wallpaperUrl(id: string): string | null {
  return inQt && id ? `app://wallpaper/${encodeURIComponent(id)}` : null;
}
