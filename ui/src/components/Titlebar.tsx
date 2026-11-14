import { useEffect, useState } from "react";
import { appWindow, inTauri } from "../lib/host";

/** Barra de titulo propria (a janela nao tem moldura do Windows). Arrastar, minimizar, maximizar, fechar. */
export function Titlebar({ children }: { children?: React.ReactNode } = {}) {
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    if (!inTauri) return;
    const win = appWindow();
    let off: (() => void) | undefined;
    void win.isMaximized().then(setMaximized);
    void win
      .onResized(() => void win.isMaximized().then(setMaximized))
      .then((unlisten) => (off = unlisten));
    return () => off?.();
  }, []);

  const act = (fn: () => Promise<void>) => () => {
    if (inTauri) void fn();
  };

  return (
    <header
      data-tauri-drag-region
      className="flex h-10 shrink-0 items-center gap-3 border-b border-hairline pl-4 text-sm"
    >
      <span data-tauri-drag-region className="font-semibold tracking-tight">
        Creative AIx
      </span>
      <div data-tauri-drag-region className="flex flex-1 items-center gap-2">
        {children}
      </div>
      <div className="flex h-full">
        <WinButton label="Minimizar" onClick={act(() => appWindow().minimize())}>
          <path d="M3 8h10" />
        </WinButton>
        <WinButton
          label={maximized ? "Restaurar" : "Maximizar"}
          onClick={act(() => appWindow().toggleMaximize())}
        >
          {maximized ? <path d="M5 3h8v8M3 5h8v8H3z" /> : <rect x="3.5" y="3.5" width="9" height="9" />}
        </WinButton>
        <WinButton label="Fechar" danger onClick={act(() => appWindow().close())}>
          <path d="M4 4l8 8M12 4l-8 8" />
        </WinButton>
      </div>
    </header>
  );
}

function WinButton(props: {
  label: string;
  danger?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={props.label}
      title={props.label}
      onClick={props.onClick}
      className={`grid h-full w-12 place-items-center text-fg-muted transition-colors hover:text-fg ${
        props.danger ? "hover:bg-bad hover:text-white" : "hover:bg-hover"
      }`}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.2">
        {props.children}
      </svg>
    </button>
  );
}
