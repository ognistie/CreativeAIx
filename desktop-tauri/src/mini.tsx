import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/index.css";

// Mini chat: janela "mini" (src-tauri/tauri.conf.json). O redesign a partir do MiniChat.qml chega na Fase 4.
function Mini() {
  return (
    <div className="m-2 rounded-2xl border border-hairline bg-surface/90 p-3 text-sm shadow-lg backdrop-blur">
      Creative AIx
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Mini />
  </StrictMode>,
);
