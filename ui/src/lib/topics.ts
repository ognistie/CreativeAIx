import type { IconName } from "../components/ui";

// Identidade visual de cada tema da Biblioteca: icone, cores e motivo da capa (components/art/TopicArt).
// `deep` leva texto branco com contraste >= 4.5:1 (rodape dos cards e selo da capa).

export type Motif = "dial" | "layers" | "arrow" | "network" | "rings" | "hourglass" | "nested" | "sphere" | "globe" | "streams";

export interface TopicLook {
  icon: IconName;
  motif: Motif;
  c: string;
  deep: string;
  glow: string;
}

const LOOKS: Record<string, TopicLook> = {
  harness: { icon: "wrench", motif: "dial", c: "#3b82f6", deep: "#1d4ed8", glow: "#a5f3fc" },
  context: { icon: "memory", motif: "layers", c: "#f97316", deep: "#a8400d", glow: "#fde68a" },
  aci: { icon: "cursor", motif: "arrow", c: "#22a35a", deep: "#2f5d3a", glow: "#bbf7d0" },
  orchestration: { icon: "network", motif: "network", c: "#8b5cf6", deep: "#5b35c9", glow: "#f0abfc" },
  evals: { icon: "target", motif: "rings", c: "#f43f5e", deep: "#a3133a", glow: "#fecdd3" },
  "test-time": { icon: "hourglass", motif: "hourglass", c: "#14b8a6", deep: "#0f6b6a", glow: "#99f6e4" },
  rlm: { icon: "recursion", motif: "nested", c: "#f59e0b", deep: "#8a4b06", glow: "#fef08a" },
  interpretability: { icon: "microscope", motif: "sphere", c: "#6366f1", deep: "#3730a3", glow: "#c7d2fe" },
  "world-models": { icon: "orbit", motif: "globe", c: "#10b981", deep: "#116149", glow: "#a7f3d0" },
  serving: { icon: "server", motif: "streams", c: "#ec4899", deep: "#9d1d63", glow: "#fbcfe8" },
};

const FALLBACK: TopicLook = { icon: "book", motif: "dial", c: "#64748b", deep: "#334155", glow: "#e2e8f0" };

export const lookFor = (id: string): TopicLook => LOOKS[id] ?? FALLBACK;

export const LEVEL_LABEL: Record<string, string> = {
  iniciante: "Iniciante",
  intermediario: "Intermediário",
  avancado: "Avançado",
};
