import { useCallback, useEffect, useState } from "react";
import { core } from "../../lib/host";
import { AGENTS, call, type Memory } from "./types";

// Memoria dos agentes no Cerebro: as notas da pasta de cada agente e as que ele usa (citadas pelas notas dele no
// grafo, ou pela secao "Ligacoes" da nota do agente). Quem desenha: HarnessPanorama; quem edita: AgentKnowledge.

export const AGENT_FOLDERS: Record<string, string> = {
  MAESTRO: "00 Maestro", WEB: "10 Agentes/Web", DESKTOP: "10 Agentes/Desktop", CODE: "10 Agentes/Code",
  DATA: "10 Agentes/Data", FILE: "10 Agentes/File", EXTCODE: "10 Agentes/ExtCode",
};
export const noteTitle = (rel: string) => rel.split("/").pop()!.replace(/\.md$/i, "");

export interface Knowledge {
  agents: Record<string, { own: string[]; uses: string[] }>;
  shared: Set<string>;
  writable: boolean;
}

/** Notas fora da pasta de cada agente que as notas dele citam (pelas arestas do grafo do Cerebro). */
export function usesFromGraph(folders: Record<string, string>, edges: Array<{ from: string; to: string }>, own: Record<string, string[]>) {
  const inside = (rel: string, folder: string) => rel === folder || rel.startsWith(folder + "/");
  const out: Record<string, string[]> = {};
  for (const [id, folder] of Object.entries(folders)) {
    const mine = new Set(own[id] ?? []);
    out[id] = [...new Set(edges.filter((e) => mine.has(e.from) && !inside(e.to, folder)).map((e) => e.to))].sort();
  }
  return out;
}

export function useAgentKnowledge(): { knowledge: Knowledge | null; error: string; reload: () => void } {
  const [knowledge, setKnowledge] = useState<Knowledge | null>(null);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true;
    void (async () => {
      const [ov, graph] = await Promise.all([call(core().call("brainOverview")), call(core().call("brainGraph"))]);
      if (!ov.ok) return active && setError(ov.error || "Não deu para ler o Cérebro.");
      const notes = (ov.notes as Array<{ rel: string; folder: string }>) ?? [];
      const own = Object.fromEntries(AGENTS.map((id) => {
        const folder = AGENT_FOLDERS[id]!;
        return [id, notes.filter((n) => n.folder === folder || n.folder.startsWith(folder + "/")).map((n) => n.rel)];
      }));
      const uses = usesFromGraph(AGENT_FOLDERS, (graph.edges as Array<{ from: string; to: string }>) ?? [], own);
      const linked = await Promise.all(AGENTS.map(async (id) => {
        const r = await call(core().call("studioAgent", id));
        return ((r.memory as Memory | undefined)?.links ?? []).map((l) => l.rel).filter(Boolean);
      }));
      const agents = Object.fromEntries(AGENTS.map((id, i) => [id, {
        own: own[id] ?? [], uses: [...new Set([...(uses[id] ?? []), ...linked[i]!])].filter((r) => !(own[id] ?? []).includes(r)).sort(),
      }]));
      const count = new Map<string, number>();
      for (const a of Object.values(agents)) for (const r of [...a.own, ...a.uses]) count.set(r, (count.get(r) ?? 0) + 1);
      if (active) {
        setError("");
        setKnowledge({ agents, shared: new Set([...count].filter(([, n]) => n > 1).map(([r]) => r)), writable: ov.writable !== false });
      }
    })();
    return () => { active = false; };
  }, [version]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { knowledge, error, reload };
}
