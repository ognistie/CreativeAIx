import { useCallback, useEffect, useMemo, useState } from "react";
import { EmptyState, Skeleton } from "../../components/ui";
import { core } from "../../lib/host";
import { layoutAgentSpine, SPINE_H, SPINE_W, usesFromGraph } from "../../lib/agentSpine";
import { AGENTS, AGENT_LOOK, call, type Memory } from "./types";

// A memoria dos agentes como um sistema nervoso (lib/agentSpine.ts): o Maestro e o cerebro, a medula leva o pedido
// para cima e cada agente sai de uma vertebra com o seu nervo. Os pontos no nervo sao as notas da pasta do agente; as
// contas rosadas na medula sao a memoria comum (notas que mais de um agente usa). Clicar num agente o escolhe;
// clicar num ponto abre a nota no painel ao lado.

export const AGENT_FOLDERS: Record<string, string> = {
  MAESTRO: "00 Maestro", WEB: "10 Agentes/Web", DESKTOP: "10 Agentes/Desktop", CODE: "10 Agentes/Code",
  DATA: "10 Agentes/Data", FILE: "10 Agentes/File", EXTCODE: "10 Agentes/ExtCode",
};
export const noteTitle = (rel: string) => rel.split("/").pop()!.replace(/\.md$/i, "");
const pct = (v: number, of: number) => `${(v / of) * 100}%`;

export interface Knowledge {
  agents: Record<string, { own: string[]; uses: string[] }>;
  shared: Set<string>;
  writable: boolean;
}

/** Notas de cada agente no Cerebro: as da pasta dele e as que ele cita (grafo + secao "Ligacoes" da nota do agente). */
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

export function MemorySpine({ knowledge, selected, note, onSelect, onNote }: {
  knowledge: Knowledge;
  selected: string;
  note: string;
  onSelect: (agent: string) => void;
  onNote: (agent: string, rel: string) => void;
}) {
  const [hover, setHover] = useState("");
  const spine = useMemo(() => layoutAgentSpine(AGENTS.map((id) => ({ id, ...knowledge.agents[id]! }))), [knowledge]);
  const focus = hover || selected;
  const dim = (id: string) => (hover ? (hover !== id ? "is-dim" : "") : selected && selected !== id ? "is-muted" : "");
  const agentButton = (id: string, x: number, y: number, side: number) => {
    const a = knowledge.agents[id]!;
    return (
      <li key={id} className="ms-agent" data-side={side} style={{ left: pct(x, SPINE_W), top: pct(y, SPINE_H), "--agent": AGENT_LOOK[id]!.color } as React.CSSProperties}>
        <button type="button" aria-pressed={selected === id} onClick={() => onSelect(id)}
          onMouseEnter={() => setHover(id)} onMouseLeave={() => setHover("")} onFocus={() => setHover(id)} onBlur={() => setHover("")}>
          <i aria-hidden />
          <strong>{AGENT_LOOK[id]!.name}</strong>
          <small>{a.own.length} {a.own.length === 1 ? "nota" : "notas"} · usa {a.uses.length}</small>
        </button>
      </li>
    );
  };
  const point = (agent: string, rel: string, x: number, y: number, kind: "ganglion" | "bead", owners?: string[]) => (
    <li key={`${kind}-${agent}-${rel}`} className={`ms-${kind} ${kind === "bead" ? (focus && owners && !owners.includes(focus) ? "is-dim" : "") : dim(agent)}`}
      style={{ left: pct(x, SPINE_W), top: pct(y, SPINE_H), "--agent": AGENT_LOOK[agent]?.color } as React.CSSProperties}>
      <button type="button" aria-current={note === rel ? "true" : undefined}
        aria-label={`${noteTitle(rel)}${owners ? ` — usada por ${owners.map((o) => AGENT_LOOK[o]?.name ?? o).join(", ")}` : ` · ${AGENT_LOOK[agent]?.name}`}`}
        title={`${noteTitle(rel)}${owners ? ` — usada por ${owners.map((o) => AGENT_LOOK[o]?.name ?? o).join(", ")}` : ""}`}
        onClick={() => onNote(owners ? (owners.includes(selected) ? selected : owners[0]!) : agent, rel)} />
    </li>
  );

  return (
    <section className="memory-spine" aria-label="Medula da memória dos agentes">
      <div className="ms-scene">
        <svg className="ms-art" viewBox={`0 0 ${SPINE_W} ${SPINE_H}`} preserveAspectRatio="none" aria-hidden>
          {/* Medula e cauda equina: o tronco e as raizes da arvore, no mesmo traco */}
          <g className={`ms-cord ${focus && focus !== spine.brain.agent ? "is-soft" : ""}`}>
            {spine.cord.pixels.map((p, tone) => p && <path key={tone} d={p} className={`px px-${tone}`} />)}
          </g>
          {/* Nervos: os galhos, um agente por nervo, com as folhas (notas) nos raminhos */}
          {spine.nerves.map((n) => (
            <g key={n.id} className={`ms-nerve ${dim(n.id)}`}>
              {n.pixels.map((p, tone) => p && <path key={tone} d={p} className={`px px-${tone}`} />)}
            </g>
          ))}
          {/* Vertebras em osso, por cima da medula (luz em cima, sombra embaixo) */}
          <g className="ms-bones">
            {spine.bones.map((p, tone) => p && <path key={tone} d={p} className={`px bone-${tone}`} />)}
          </g>
          {/* Cerebro do Maestro (a copa) */}
          <g className={`ms-brain ${focus && focus !== spine.brain.agent ? "is-soft" : ""}`}>
            {spine.brain.pixels.map((p, tone) => p && <path key={tone} d={p} className={`px brain-${tone}`} />)}
          </g>
          {/* Fluxo: o pedido sobe a medula ate o cerebro e desce pelo nervo do agente */}
          <path d={spine.cord.flow} className="ms-flow ms-flow-cord" />
          {spine.nerves.map((n) => (
            <path key={n.id} d={n.flow} className={`ms-flow ${dim(n.id)}`} style={{ "--agent": AGENT_LOOK[n.id]!.color } as React.CSSProperties} />
          ))}
          {spine.shared.map((s) => s.owners.map((o) => {
            const tip = o === spine.brain.agent ? spine.cord.stem : spine.nerves.find((n) => n.id === o)?.tip;
            return tip && <line key={s.rel + o} x1={s.x} y1={s.y} x2={tip[0]} y2={tip[1]}
              className={`ms-tie ${focus && !s.owners.includes(focus) ? "is-dim" : focus ? "is-lit" : ""}`} />;
          }))}
        </svg>
        <ul className="ms-points" aria-label="Notas">
          {spine.brain.notes.map((n) => point(n.agent, n.rel, n.x, n.y, "ganglion"))}
          {spine.nerves.flatMap((nv) => nv.notes.map((n) => point(n.agent, n.rel, n.x, n.y, "ganglion")))}
          {spine.shared.map((s) => point(s.owners[0]!, s.rel, s.x, s.y, "bead", s.owners))}
        </ul>
        <ul className="ms-labels" aria-label="Agentes">
          {spine.brain.agent && agentButton(spine.brain.agent, spine.brain.center[0] - 250, spine.brain.center[1], -1)}
          {spine.nerves.map((n) => agentButton(n.id, n.tip[0], n.tip[1], n.side))}
        </ul>
        <p className="ms-root" style={{ left: pct(spine.cord.root[0], SPINE_W) }}>Pedido (voz ou texto)</p>
      </div>
      <div className="mt-legend">
        <span><i className="mt-key-flow" /> fluxo de um pedido: sobe a medula até o Maestro (cérebro), que delega pelo nervo do agente</span>
        <span><i className="mt-key-leaf" /> nota da pasta do agente</span>
        <span><i className="mt-key-fruit" /> memória comum ({spine.shared.length} {spine.shared.length === 1 ? "nota usada" : "notas usadas"} por mais de um agente)</span>
      </div>
    </section>
  );
}

export function MemorySpineLoading({ error }: { error: string }) {
  return error ? <EmptyState icon="alert-circle" title="Memória indisponível">{error}</EmptyState>
    : <Skeleton className="aspect-[1000/640] w-full rounded-r4" />;
}
