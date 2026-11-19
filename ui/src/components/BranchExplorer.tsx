import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Icon, IconButton } from "./ui";
import { PER_PAGE, VIEW_H, VIEW_W, layoutWorld, type LevelSpec } from "../lib/branchLayout";

// Arvore do Cerebro: uma arvore so, que cresce com o caminho aberto. Abrir uma pasta faz brotar um galho novo
// a partir do icone dela; os galhos de antes ficam no lugar (com os nomes mais apagados) e a vista desliza ate
// o galho novo. Subir recolhe o galho e a vista volta, com o foco na pasta de onde a pessoa saiu.
// So as pastas do caminho aberto sao desenhadas (cada nivel mostra uma pagina de filhos).

type BranchNote = { rel: string; title: string; folder: string };
type Child = { id: string; label: string; folder: boolean };

const parentOf = (path: string) => path.split("/").slice(0, -1).join("/");

export function BranchExplorer({ branch, onBranch, folders, notes, folderLabel, onOpen, returnTo }: {
  branch: string;
  onBranch: (folder: string) => void;
  folders: string[];
  notes: BranchNote[];
  folderLabel: (name: string) => string;
  onOpen: (rel: string) => void;
  returnTo?: string;
}) {
  const [page, setPage] = useState(0);
  const uid = useId().replace(/:/g, "");
  const scene = useRef<HTMLDivElement>(null);
  // Ao subir (ou voltar de uma nota), quem ganha o foco: a pasta ou nota de onde a pessoa saiu
  const cameFrom = useRef(returnTo ?? "");
  const lastBranch = useRef(branch);

  const childrenOf = useMemo(() => {
    const cache = new Map<string, Child[]>();
    return (folder: string): Child[] => {
      const hit = cache.get(folder);
      if (hit) return hit;
      const prefix = folder ? folder + "/" : "";
      const names = new Set<string>();
      for (const f of [...folders, ...notes.map((note) => note.folder)]) {
        if (f.startsWith(prefix) && f.length > prefix.length) names.add(f.slice(prefix.length).split("/")[0]!);
      }
      const list = [
        ...[...names].sort((a, b) => a.localeCompare(b)).map((name) => ({ id: prefix + name, label: folderLabel(name), folder: true })),
        ...notes.filter((note) => note.folder === folder).sort((a, b) => a.title.localeCompare(b.title))
          .map((note) => ({ id: note.rel, label: note.title, folder: false })),
      ];
      cache.set(folder, list);
      return list;
    };
  }, [folders, notes, folderLabel]);

  const own = childrenOf(branch);

  // Subiu um nivel: abre na pagina da pasta de onde veio. Desceu: primeira pagina.
  useLayoutEffect(() => {
    if (lastBranch.current === branch) {
      const index = own.findIndex((node) => node.id === cameFrom.current);
      if (index >= 0) setPage(Math.floor(index / PER_PAGE));
      return;
    }
    const previous = lastBranch.current;
    lastBranch.current = branch;
    const prefix = branch ? branch + "/" : "";
    if (previous.startsWith(prefix) && previous !== branch) {
      const child = prefix + previous.slice(prefix.length).split("/")[0];
      cameFrom.current = child;
      const index = own.findIndex((node) => node.id === child);
      setPage(index >= 0 ? Math.floor(index / PER_PAGE) : 0);
    } else {
      cameFrom.current = "";
      setPage(0);
    }
  }, [branch, own]);

  const pages = Math.max(1, Math.ceil(own.length / PER_PAGE));
  const current = Math.min(page, pages - 1);

  // Niveis do caminho: Cerebro, depois cada pasta aberta. Os de cima mostram a pagina que contem a pasta aberta.
  const levels = useMemo(() => {
    const trail = branch ? branch.split("/") : [];
    const out: Array<{ folder: string; page: number; items: Child[]; open?: number }> = [];
    for (let depth = 0; depth <= trail.length; depth++) {
      const folder = trail.slice(0, depth).join("/");
      const all = childrenOf(folder);
      const next = depth < trail.length ? trail.slice(0, depth + 1).join("/") : "";
      const index = next ? all.findIndex((item) => item.id === next) : -1;
      if (next && index < 0) break;                          // pasta sumiu (filtro ou exclusao): para aqui
      const p = next ? Math.floor(index / PER_PAGE) : current;
      const items = all.slice(p * PER_PAGE, (p + 1) * PER_PAGE);
      out.push({ folder, page: p, items, open: next ? index - p * PER_PAGE : undefined });
    }
    return out;
  }, [branch, childrenOf, current]);

  const world = useMemo(() => layoutWorld(levels.map<LevelSpec>((level) => ({
    key: `${level.folder}#${level.page}`, count: level.items.length, open: level.open,
  }))), [levels]);

  useEffect(() => {
    const target = cameFrom.current;
    if (!target) return;
    const button = scene.current?.querySelector<HTMLButtonElement>(`.branch-node[data-current][data-node="${CSS.escape(target)}"]`);
    if (!button) return;
    button.focus({ preventScroll: true });
    cameFrom.current = "";
  }, [branch, current, levels]);

  const up = () => branch && onBranch(parentOf(branch));
  const trail = branch ? branch.split("/") : [];
  const name = (folder: string) => folderLabel(folder.split("/").at(-1)!);
  const pct = (v: number, of: number) => `${(v / of) * 100}%`;

  const moveFocus = (event: React.KeyboardEvent) => {
    const keys: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if ((event.key === "Backspace" || (event.altKey && event.key === "ArrowUp")) && branch) {
      event.preventDefault();
      return up();
    }
    if (!(event.key in keys) || event.altKey) return;
    const buttons = [...(scene.current?.querySelectorAll<HTMLButtonElement>(".branch-node[data-current]") ?? [])];
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (index < 0) return;
    event.preventDefault();
    buttons[(index + keys[event.key]! + buttons.length) % buttons.length]?.focus();
  };

  const last = world.levels.length - 1;
  // So cresce o galho que acabou de aparecer (descer uma pasta); ao subir, o galho de cima ja estava la
  const shown = useRef<Set<string>>(new Set());
  const lastKey = world.levels[last]!.key;
  const grows = !shown.current.has(lastKey);
  useEffect(() => { shown.current = new Set(world.levels.map((level) => level.key)); }, [world]);

  return (
    <section aria-label="Explorar pastas e notas" className="branch-explorer">
      <header className="branch-header">
        <nav aria-label="Caminho da pasta" className="branch-trail">
          <button type="button" onClick={() => onBranch("")} aria-current={!branch ? "location" : undefined}>
            <Icon name="brain" size={14} /> Cérebro
          </button>
          {trail.map((part, i) => {
            const path = trail.slice(0, i + 1).join("/");
            return <span key={path} className="contents">
              <Icon name="chevron-right" size={13} className="text-fg-subtle" />
              <button type="button" onClick={() => onBranch(path)} aria-current={path === branch ? "location" : undefined}>{folderLabel(part)}</button>
            </span>;
          })}
        </nav>
        {branch && <button type="button" className="branch-up" onClick={up} title="Subir um nível (Backspace)">
          <Icon name="arrow-left" size={14} /> Subir para {branch.includes("/") ? name(parentOf(branch)) : "Cérebro"}
        </button>}
        {pages > 1 && <div className="branch-pagination">
          <IconButton icon="arrow-left" label="Ramos anteriores" disabled={current === 0} onClick={() => setPage(current - 1)} />
          <span aria-live="polite">{current + 1} / {pages}</span>
          <IconButton icon="arrow-right" label="Próximos ramos" disabled={current === pages - 1} onClick={() => setPage(current + 1)} />
        </div>}
      </header>

      <div ref={scene} className="branch-scene" onKeyDown={moveFocus}>
        {/* A vista: uma camada so, que desliza (transform) para enquadrar o galho da pasta aberta */}
        <div className="branch-world" style={{ transform: `translate(${pct(world.camera[0], VIEW_W)}, ${pct(world.camera[1], VIEW_H)})` }}>
          <svg className="branch-art" aria-hidden viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} preserveAspectRatio="none">
            {/* O galho da pasta aberta cresce a partir dela: recorte circular que abre no ponto da pasta */}
            <defs>
              <clipPath id={`${uid}-grow`}>
                <circle key={lastKey} className={grows ? "branch-grow" : undefined} cx={world.levels[last]!.anchor[0]} cy={world.levels[last]!.anchor[1]} r={1600} />
              </clipPath>
            </defs>
            {world.levels.map((level, depth) => (
              <g key={level.key} className="branch-level" data-current={depth === last || undefined}
                clipPath={depth === last ? `url(#${uid}-grow)` : undefined}>
                {level.pixels.map((d, tone) => d && <path key={tone} d={d} className={`px px-${tone}`} />)}
              </g>
            ))}
          </svg>

          {world.levels.map((level, depth) => {
            const spec = levels[depth]!;
            const isCurrent = depth === last;
            return (
              <ul key={level.key} className="branch-nodes" data-current={isCurrent || undefined} data-grows={(isCurrent && grows) || undefined} aria-label={spec.folder ? name(spec.folder) : "Cérebro"}>
                {spec.items.map((item, index) => {
                  const node = level.nodes[index]!;
                  const opened = spec.open === index;
                  return (
                    <li key={item.id} style={{ left: pct(node.tip[0], VIEW_W), top: pct(node.tip[1], VIEW_H), "--grow": index } as React.CSSProperties}>
                      <button type="button" className="branch-node" data-node={item.id} data-kind={item.folder ? "folder" : "note"}
                        data-current={isCurrent || undefined} data-open={opened || undefined}
                        tabIndex={isCurrent || opened ? 0 : -1}
                        aria-label={item.folder ? (opened ? `Fechar a pasta ${item.label}` : `Abrir a pasta ${item.label}`) : `Ler a nota ${item.label}`}
                        onClick={(event) => {
                          if (!item.folder) return onOpen(item.id);
                          // Pasta ja aberta no caminho: volta para ela (fecha o que estava aberto dentro)
                          if (opened) return onBranch(item.id === branch ? parentOf(item.id) : item.id);
                          onBranch(item.id);
                          if (event.detail === 0) requestAnimationFrame(() =>
                            scene.current?.querySelector<HTMLButtonElement>(".branch-node[data-current]")?.focus({ preventScroll: true }));
                        }}>
                        <Icon name={item.folder ? (opened ? "folder-open" : "folder") : "file-text"} size={17} weight={1.4} />
                        <span>{item.label}{item.folder ? "/" : ""}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            );
          })}
        </div>
        {!own.length && <p className="branch-empty">{branch ? "Esta pasta está vazia." : "Nenhuma nota nesta seleção."}</p>}
      </div>
      <p className="branch-status">{own.length} {own.length === 1 ? "item" : "itens"}</p>
    </section>
  );
}
