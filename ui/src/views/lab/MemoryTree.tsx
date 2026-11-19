import { useEffect, useMemo, useState } from "react";
import { EmptyState, Skeleton } from "../../components/ui";
import { core } from "../../lib/host";
import { layoutAgentTree, TREE_H, TREE_W, usesFromGraph, type TreeAgentInput } from "../../lib/agentTree";
import { AGENTS, AGENT_LOOK, call, type Memory } from "./types";

// A memoria dos agentes como a arvore do Cerebro vista de longe (lib/agentTree.ts): a raiz e o pedido entrando,
// o tronco sobe ate o Maestro na copa, cada galho e um agente com as notas dele como folhas, e os frutos sao as
// notas que mais de um agente usa. O pulso que corre pelo tronco e pelos galhos e o fluxo de um pedido.
// So leitura: clicar num agente o seleciona para editar a memoria e o contexto logo abaixo.

export const AGENT_FOLDERS: Record<string, string> = {
  MAESTRO: "00 Maestro", WEB: "10 Agentes/Web", DESKTOP: "10 Agentes/Desktop", CODE: "10 Agentes/Code",
  DATA: "10 Agentes/Data", FILE: "10 Agentes/File", EXTCODE: "10 Agentes/ExtCode",
};
const title = (rel: string) => rel.split("/").pop()!.replace(/\.md$/i, "");
const pct = (v: number, of: number) => `${(v / of) * 100}%`;

export function MemoryTree({ selected, onSelect }: { selected: string; onSelect: (agent: string) => void }) {
  const [input, setInput] = useState<TreeAgentInput[] | null>(null);
  const [error, setError] = useState("");
  const [hover, setHover] = useState("");

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
      // As notas ligadas na secao "Ligacoes" da nota do agente tambem sao memoria que ele usa
      const linked = await Promise.all(AGENTS.map(async (id) => {
        const r = await call(core().call("studioAgent", id));
        return ((r.memory as Memory | undefined)?.links ?? []).map((l) => l.rel).filter(Boolean);
      }));
      if (active) setInput(AGENTS.map((id, i) => ({ id, own: own[id] ?? [], uses: [...new Set([...(uses[id] ?? []), ...linked[i]!])] })));
    })();
    return () => { active = false; };
  }, []);

  const tree = useMemo(() => (input ? layoutAgentTree(input) : null), [input]);
  if (error) return <EmptyState icon="alert-circle" title="Árvore indisponível">{error}</EmptyState>;
  if (!tree || !input) return <Skeleton className="aspect-[1000/600] w-full rounded-r4" />;

  const focus = hover || selected;
  const dim = (id: string) => (hover ? (hover !== id ? "is-dim" : "") : selected && selected !== id ? "is-muted" : "");
  const count = (id: string) => input.find((a) => a.id === id)!;
  const label = (id: string, x: number, y: number, side: number) => {
    const a = count(id);
    return (
      <li key={id} className="mt-agent" data-side={side} style={{ left: pct(x, TREE_W), top: pct(y, TREE_H), "--agent": AGENT_LOOK[id]!.color } as React.CSSProperties}>
        <button type="button" aria-pressed={selected === id} onClick={() => onSelect(id)}
          onMouseEnter={() => setHover(id)} onMouseLeave={() => setHover("")} onFocus={() => setHover(id)} onBlur={() => setHover("")}>
          <i aria-hidden />
          <strong>{AGENT_LOOK[id]!.name}</strong>
          <small>{a.own.length} notas · usa {a.uses.length}</small>
        </button>
      </li>
    );
  };

  return (
    <section className="memory-tree" aria-label="Árvore da memória dos agentes">
      <div className="mt-scene">
        <svg className="mt-art" viewBox={`0 0 ${TREE_W} ${TREE_H}`} preserveAspectRatio="none" aria-hidden>
          <g className={`mt-trunk ${focus && focus !== tree.crown ? "is-soft" : ""}`}>
            {tree.trunk.pixels.map((d, tone) => d && <path key={tone} d={d} className={`px px-${tone}`} />)}
          </g>
          {tree.branches.map((b) => (
            <g key={b.id} className={`mt-branch ${dim(b.id)}`}>
              {b.pixels.map((d, tone) => d && <path key={tone} d={d} className={`px px-${tone}`} />)}
            </g>
          ))}
          {/* Fluxo: pedido sobe o tronco ate o Maestro e desce para o agente */}
          <path d={tree.trunk.flow} className="mt-flow mt-flow-trunk" />
          {tree.branches.map((b) => (
            <path key={b.id} d={b.flow} className={`mt-flow ${dim(b.id)}`} style={{ "--agent": AGENT_LOOK[b.id]!.color } as React.CSSProperties} />
          ))}
          {tree.fruits.map((f) => f.owners.map((o) => {
            const tip = o === tree.crown ? tree.trunk.crown : tree.branches.find((b) => b.id === o)?.tip;
            return tip && <line key={f.rel + o} x1={f.x} y1={f.y} x2={tip[0]} y2={tip[1]}
              className={`mt-tie ${focus && !f.owners.includes(focus) ? "is-dim" : focus ? "is-lit" : ""}`} />;
          }))}
        </svg>
        <ul className="mt-points" aria-label="Notas">
          {[...tree.crownLeaves, ...tree.branches.flatMap((b) => b.leaves)].map((l) => (
            <li key={l.agent + l.rel} className={`mt-leaf ${dim(l.agent)}`} style={{ left: pct(l.x, TREE_W), top: pct(l.y, TREE_H), "--agent": AGENT_LOOK[l.agent]!.color } as React.CSSProperties}
              title={`${title(l.rel)} · ${AGENT_LOOK[l.agent]!.name}`} />
          ))}
          {tree.fruits.map((f) => (
            <li key={f.rel} className={`mt-fruit ${focus && !f.owners.includes(focus) ? (hover ? "is-dim" : "is-muted") : ""}`} style={{ left: pct(f.x, TREE_W), top: pct(f.y, TREE_H) }}
              title={`${title(f.rel)} — usada por ${f.owners.map((o) => AGENT_LOOK[o]?.name ?? o).join(", ")}`} />
          ))}
        </ul>
        <ul className="mt-labels" aria-label="Agentes">
          {tree.crown && label(tree.crown, tree.trunk.crown[0], tree.trunk.crown[1] - 44, 0)}
          {tree.branches.map((b) => label(b.id, b.tip[0], b.tip[1], b.side))}
        </ul>
        <p className="mt-root" style={{ left: pct(tree.trunk.root[0], TREE_W) }}>Pedido (voz ou texto)</p>
      </div>
      <div className="mt-legend">
        <span><i className="mt-key-flow" /> fluxo de um pedido: sobe até o Maestro, que delega ao agente</span>
        <span><i className="mt-key-leaf" /> nota da pasta do agente</span>
        <span><i className="mt-key-fruit" /> memória comum ({tree.fruits.length} {tree.fruits.length === 1 ? "nota usada" : "notas usadas"} por mais de um agente)</span>
      </div>
    </section>
  );
}
