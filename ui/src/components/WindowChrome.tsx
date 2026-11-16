import { useCallback, useEffect, useState } from "react";
import { core, inQt } from "../lib/host";
import { WindowGlyph } from "./ui/Icon";

// Janela sem a moldura do Windows (desktop/web_host.py): a barra de titulo e parte do app, no mesmo material.
// Arrastar, duplo clique, minimizar/maximizar/fechar e redimensionar pelas bordas vao para o Qt
// (startSystemMove/startSystemResize), entao o encaixe nas bordas da tela continua sendo o do Windows.

const INTERACTIVE = "button, a, input, textarea, select, [role=button], [role=switch], [role=menuitem], [data-no-drag]";

export function useWindowState(): { maximized: boolean; toggle: () => void } {
  const [maximized, setMaximized] = useState(true);
  const refresh = useCallback(() => {
    if (!inQt) return;
    core()
      .call("windowState")
      .then((r) => setMaximized(!!(r as { maximized?: boolean }).maximized))
      .catch(() => {});
  }, []);
  useEffect(() => {
    refresh();
    window.addEventListener("resize", refresh);
    return () => window.removeEventListener("resize", refresh);
  }, [refresh]);
  const toggle = useCallback(() => {
    if (!inQt) return;
    core()
      .call("windowToggleMaximize")
      .then((r) => setMaximized(!!(r as { maximized?: boolean }).maximized))
      .catch(() => {});
  }, []);
  return { maximized, toggle };
}

/** Props para uma area arrastavel: arrasta a janela, duplo clique maximiza. Cliques em controles passam. */
export function dragArea(toggle: () => void) {
  if (!inQt) return {};
  return {
    onMouseDown: (e: React.MouseEvent) => {
      if (e.button !== 0 || e.detail > 1 || (e.target as HTMLElement).closest(INTERACTIVE)) return;
      void core().call("windowStartMove");
    },
    onDoubleClick: (e: React.MouseEvent) => {
      if ((e.target as HTMLElement).closest(INTERACTIVE)) return;
      toggle();
    },
  };
}

export function WindowControls({ maximized, toggle }: { maximized: boolean; toggle: () => void }) {
  if (!inQt) return null;
  const Min = WindowGlyph.minimize;
  const Max = WindowGlyph.maximize;
  const Close = WindowGlyph.close;
  return (
    <div className="ml-1 flex items-center gap-0.5" data-no-drag>
      <button type="button" className="window-btn" aria-label="Minimizar" onClick={() => void core().call("windowMinimize")}>
        <Min size={15} strokeWidth={1.5} />
      </button>
      <button type="button" className="window-btn" aria-label={maximized ? "Restaurar" : "Maximizar"} onClick={toggle}>
        {maximized ? (
          <svg width={13} height={13} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth={1.25} aria-hidden>
            <rect x="1.5" y="3.5" width="9" height="9" rx="1.6" />
            <path d="M4 3.5V2.6c0-.6.5-1.1 1.1-1.1h6.3c.6 0 1.1.5 1.1 1.1v6.3c0 .6-.5 1.1-1.1 1.1h-.9" />
          </svg>
        ) : (
          <Max size={12} strokeWidth={1.6} />
        )}
      </button>
      <button type="button" className="window-btn close" aria-label="Fechar" onClick={() => void core().call("windowClose")}>
        <Close size={16} strokeWidth={1.5} />
      </button>
    </div>
  );
}

/** Bordas invisiveis para redimensionar (so com a janela restaurada). */
export function ResizeEdges({ maximized }: { maximized: boolean }) {
  if (!inQt || maximized) return null;
  const edge = (name: string, cls: string, cursor: string) => (
    <div
      key={name}
      aria-hidden
      className={`fixed z-[200] ${cls}`}
      style={{ cursor }}
      onMouseDown={(e) => {
        if (e.button === 0) void core().call("windowStartResize", name);
      }}
    />
  );
  return (
    <>
      {edge("left", "inset-y-2 left-0 w-1.5", "ew-resize")}
      {edge("right", "inset-y-2 right-0 w-1.5", "ew-resize")}
      {edge("top", "inset-x-2 top-0 h-1.5", "ns-resize")}
      {edge("bottom", "inset-x-2 bottom-0 h-1.5", "ns-resize")}
      {edge("top-left", "left-0 top-0 size-2.5", "nwse-resize")}
      {edge("top-right", "right-0 top-0 size-2.5", "nesw-resize")}
      {edge("bottom-left", "bottom-0 left-0 size-2.5", "nesw-resize")}
      {edge("bottom-right", "bottom-0 right-0 size-2.5", "nwse-resize")}
    </>
  );
}
