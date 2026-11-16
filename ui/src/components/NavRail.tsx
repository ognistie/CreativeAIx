import { useRef, useState } from "react";
import { cn } from "../lib/cn";
import { Icon, type IconName } from "./ui";

// Barra lateral recolhida: trilho de icones (referencia: uma unica dica que desliza entre os itens, com o
// atalho ao lado). A dica e um elemento so, movido por transform; aparece no hover e no foco do teclado.

export interface RailItem {
  id: string;
  label: string;
  icon: IconName;
  hint?: string;
  active?: boolean;
  pulse?: boolean;
  onClick: () => void;
}

export function NavRail({ items, onExpand }: { items: RailItem[]; onExpand: () => void }) {
  const [tip, setTip] = useState<{ y: number; label: string; hint?: string } | null>(null);
  const box = useRef<HTMLElement>(null);

  const show = (el: HTMLElement, it: RailItem) => {
    const top = box.current?.getBoundingClientRect().top ?? 0;
    const r = el.getBoundingClientRect();
    setTip({ y: r.top - top + r.height / 2, label: it.label, hint: it.hint });
  };

  return (
    <nav ref={box} aria-label="Navegação" className="sidebar-panel relative z-20 m-2 mr-0 flex w-[56px] shrink-0 flex-col items-center gap-1 rounded-[18px] py-3" onMouseLeave={() => setTip(null)}>
      {items.map((it, i) => (
        <button
          key={it.id}
          type="button"
          aria-label={it.hint ? `${it.label} (${it.hint})` : it.label}
          aria-current={it.active ? "page" : undefined}
          onClick={it.onClick}
          onMouseEnter={(e) => show(e.currentTarget, it)}
          onFocus={(e) => show(e.currentTarget, it)}
          onBlur={() => setTip(null)}
          className={cn(
            "press grid size-10 place-items-center rounded-r2 transition-colors",
            it.active ? "bg-row-hover text-fg" : "text-fg-muted hover:bg-hover hover:text-fg",
            i === 0 && "mb-2",
          )}
        >
          <Icon name={it.icon} size={17} weight={1.75} className={cn(it.pulse && "animate-pulse text-accent-ink")} />
        </button>
      ))}
      <span className="flex-1" />
      <button
        type="button"
        aria-label="Mostrar barra lateral (Ctrl \)"
        onClick={onExpand}
        onMouseEnter={(e) => show(e.currentTarget, { id: "x", label: "Mostrar barra", hint: "Ctrl \\", icon: "sidebar", onClick: onExpand })}
        className="press grid size-10 place-items-center rounded-r2 text-fg-muted hover:bg-hover hover:text-fg"
      >
        <Icon name="sidebar" size={18} />
      </button>
      <span
        aria-hidden
        className="pointer-events-none absolute left-[58px] top-0 flex items-center gap-2 whitespace-nowrap rounded-full bg-[#141816] px-3 py-1.5 text-sm font-medium text-white shadow-[0_8px_24px_rgb(0_0_0/0.35)]"
        style={{
          transform: `translateY(${(tip?.y ?? 0) - 16}px) translateX(${tip ? 0 : -6}px)`,
          opacity: tip ? 1 : 0,
          transition: "transform 260ms cubic-bezier(0.34,1.3,0.64,1), opacity 160ms ease",
        }}
      >
        {tip?.label}
        {tip?.hint && <span className="text-white/60">{tip.hint}</span>}
      </span>
    </nav>
  );
}
