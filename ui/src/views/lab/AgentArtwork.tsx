import { memo, useEffect, useRef } from "react";
import type { Agent } from "./types";
import { CELL, COLS, ROWS, halftone, paint } from "./halftone";

// Arte de cada quadro do AI Research Lab: uma ilustracao em meio-tom pixelado (views/lab/halftone.ts), com
// 3 tons de tinta proprios de cada agente sobre o papel do quadro. Desenhada uma vez num canvas pequeno e
// ampliada sem suavizar. Tudo e ilustrativo: nenhum grafico aqui representa dado real.

export interface ArtLook {
  /** cor da borda e do foco do quadro */
  edge: string;
  paper: string;
  ink: string;
  /** luz difusa do fundo (camadas de gradiente) */
  light: string;
}

/** Tinta da ilustracao: tom claro, medio e cheio (nos quadros escuros, o cheio e o mais claro) */
export const RAMP: Record<Agent, readonly [string, string, string]> = {
  MAESTRO: ["#cdbdf0", "#9a7fe0", "#4f34a8"],
  WEB: ["#2c6f72", "#57c9bd", "#c9fff3"],
  DESKTOP: ["#bcd0f3", "#6f95e0", "#2551ad"],
  CODE: ["#2c3880", "#6c83f4", "#d5dcff"],
  DATA: ["#b9dccb", "#4caf96", "#1d5f58"],
  FILE: ["#f0c3a6", "#df8667", "#9c3f3a"],
  EXTCODE: ["#1f5a47", "#3fcf98", "#c6ffe2"],
};

export const ART: Record<Agent, ArtLook> = {
  MAESTRO: {
    paper: "#f2edf8", ink: "#2a2044", edge: "#c9bbdc",
    light: `radial-gradient(72% 68% at 54% 44%, #a18ad8, transparent 72%),
            linear-gradient(165deg, #f6effa, #e2d7f5 55%, #ddbada)`,
  },
  WEB: {
    paper: "#14282d", ink: "#defaf2", edge: "#5f8e88",
    light: `radial-gradient(65% 50% at 18% 96%, #ff9a5ccc, transparent 70%),
            radial-gradient(55% 45% at 86% 10%, #59e3d6aa, transparent 70%),
            linear-gradient(180deg, #0f5a63, #1a2547 55%, #4a1f3d)`,
  },
  DESKTOP: {
    paper: "#eaf0fa", ink: "#213665", edge: "#a8bbd9",
    light: `radial-gradient(70% 55% at 80% 18%, #ffffffb3, transparent 68%),
            radial-gradient(70% 60% at 30% 80%, #6d8dff99, transparent 70%),
            linear-gradient(160deg, #dae9fa, #abc5ea 58%, #9ba9db)`,
  },
  CODE: {
    paper: "#171b36", ink: "#e1e7ff", edge: "#596797",
    light: `radial-gradient(80% 45% at 50% 104%, #3f7dffcc, transparent 72%),
            radial-gradient(40% 35% at 18% 18%, #b48bff66, transparent 70%),
            linear-gradient(180deg, #0b0e24, #161a4a 60%, #1b2d86)`,
  },
  DATA: {
    paper: "#edf1df", ink: "#23372d", edge: "#b1c59b",
    light: `radial-gradient(52% 46% at 46% 52%, #1aa6b0e6, transparent 72%),
            radial-gradient(75% 65% at 50% 50%, #8fd77fb3, transparent 82%),
            linear-gradient(160deg, #f6e1d4, #f3c9b0 50%, #e7b9c4)`,
  },
  FILE: {
    paper: "#f7ebdb", ink: "#4d3027", edge: "#d6b69f",
    light: `radial-gradient(60% 50% at 22% 20%, #fff0c8cc, transparent 70%),
            radial-gradient(70% 60% at 85% 95%, #e35d7a99, transparent 72%),
            linear-gradient(155deg, #f8e0bf, #e6a68c 55%, #ca8d85)`,
  },
  EXTCODE: {
    paper: "#172a25", ink: "#dcf5e2", edge: "#59917c",
    light: `radial-gradient(70% 40% at 40% 70%, #2fd39a8c, transparent 70%),
            radial-gradient(45% 35% at 90% 8%, #ffb36b66, transparent 70%),
            linear-gradient(175deg, #10161a, #13262a 60%, #0d3b33)`,
  },
};

/** A arte inteira do quadro: papel do agente e a ilustracao em pontos (canvas). */
export const AgentArtwork = memo(function AgentArtwork({ agent }: { agent: Agent }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const ctx = canvas.current?.getContext("2d");
    if (ctx) paint(ctx, halftone(agent), RAMP[agent]);
  }, [agent]);
  return (
    <span className="research-art" style={{ background: `radial-gradient(80% 70% at 50% 45%, color-mix(in srgb, ${ART[agent].paper}, ${RAMP[agent][0]} 22%), ${ART[agent].paper})` }}>
      <canvas ref={canvas} className="research-figure" width={COLS * CELL} height={ROWS * CELL} aria-hidden="true" />
    </span>
  );
});
