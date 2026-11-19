// Onde a interface esta rodando e como falar com o nucleo e com as janelas.
//
//   qt     o app: janelas Qt (desktop/web_host.py), porta e token injetados em window.__CREATIVE_AIX__
//   demo   navegador com ?demo: nucleo falso para revisar telas

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
export const demoMode = !inQt && typeof window !== "undefined" && new URLSearchParams(window.location.search).has("demo");
/** Ha o app de verdade (janelas, dialogo de arquivos e nucleo). */
export const inApp = inQt;

/** Porta e token do nucleo. */
export function coreInfo(): Promise<CoreInfo> {
  if (qtInfo) return Promise.resolve({ port: qtInfo.port, token: qtInfo.token });
  if (demoMode) return Promise.resolve({ port: 0, token: "demo" });
  return Promise.reject(new Error("abra pelo app Creative AIx"));
}

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
  window.open(url, "_blank", "noopener,noreferrer");
}

/** O dialogo fica aberto enquanto a pessoa navega nas pastas: com o prazo padrao (30 s) a escolha se perdia. */
const DIALOG_TIMEOUT_MS = 10 * 60_000;

/** Escolher arquivos (dialogo do Windows). Devolve os caminhos ou [] se cancelar. */
export async function pickFiles(): Promise<string[]> {
  if (!inQt) return [];
  const r = await core().callWithin(DIALOG_TIMEOUT_MS, "pickFiles");
  return Array.isArray(r) ? (r as string[]) : [];
}

/** Escolher a pasta de um projeto (dialogo do Windows). "" se cancelar. */
export async function pickFolder(): Promise<string> {
  if (inQt) {
    const r = await core().callWithin(DIALOG_TIMEOUT_MS, "pickFolder");
    return typeof r === "string" ? r : "";
  }
  if (demoMode) return "C:\\Users\\voce\\Desktop\\meu-projeto";
  return "";
}

export async function saveLabDocument(name: string, content: string): Promise<boolean> {
  if (inQt) {
    const reply = await core().callWithin(DIALOG_TIMEOUT_MS, "saveLabFile", name, content) as { ok?: boolean; error?: string; cancelled?: boolean };
    if (!reply?.ok) throw new Error(reply?.error || "Não foi possível salvar o arquivo.");
    return !reply.cancelled;
  }
  const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
  const anchor = Object.assign(document.createElement("a"), { href: url, download: name });
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}

/** Endereco de um papel de parede (servido pelo app://wallpaper do host). */
export function wallpaperUrl(id: string): string | null {
  // "gen:..." e desenhado pelo app (lib/generative.ts), nao e arquivo
  return inQt && id && !id.startsWith("gen:") ? `app://wallpaper/${encodeURIComponent(id)}` : null;
}
