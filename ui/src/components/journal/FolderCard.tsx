import { Icon } from "../ui";

// Pasta do Diario (referencias: pastas de vidro com folhas que se abrem em leque no hover, e a pasta azul
// com bolinhas de cor). Folhas = titulos das entradas mais recentes. So CSS (transform), sem JS de animacao.

export const FOLDER_COLORS = ["#2563eb", "#15803d", "#7c3aed", "#be185d", "#b45309", "#334155"] as const;

export function FolderCard({
  name,
  count,
  privateCount,
  recent,
  color,
  onOpen,
  onColor,
}: {
  name: string;
  count: number;
  privateCount: number;
  recent: string[];
  color: string;
  onOpen: () => void;
  onColor: (c: string) => void;
}) {
  const sheets = recent.slice(0, 3);
  return (
    <div className="folder-wrap group" style={{ ["--fc" as string]: color }}>
      <button type="button" onClick={onOpen} className="folder press" aria-label={`Abrir a pasta ${name}, ${count} ${count === 1 ? "entrada" : "entradas"}`}>
        <span aria-hidden className="folder-back" />
        {sheets.map((t, i) => (
          <span aria-hidden key={i} className="folder-sheet" style={{ ["--i" as string]: i, ["--n" as string]: sheets.length }}>
            <span className="line-clamp-3">{t}</span>
          </span>
        ))}
        {sheets.length === 0 && (
          <span aria-hidden className="folder-sheet folder-sheet-empty" style={{ ["--i" as string]: 0, ["--n" as string]: 1 }}>
            Vazia
          </span>
        )}
        <span className="folder-front">
          <span className="min-w-0">
            <span className="block truncate font-display text-[17px] font-semibold tracking-[-0.01em]">{name}</span>
            <span className="mt-0.5 block font-mono text-[11px] text-white/85">
              {count} {count === 1 ? "entrada" : "entradas"}
              {privateCount ? ` · ${privateCount} privada${privateCount > 1 ? "s" : ""}` : ""}
            </span>
          </span>
          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-black/25 transition-transform group-hover:rotate-90">
            <Icon name="plus" size={15} />
          </span>
        </span>
      </button>
      <div className="mt-3 flex justify-center gap-1.5 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100" role="radiogroup" aria-label={`Cor da pasta ${name}`}>
        {FOLDER_COLORS.map((c) => (
          <button
            key={c}
            type="button"
            role="radio"
            aria-checked={c === color}
            aria-label={`Cor ${c}`}
            onClick={() => onColor(c)}
            className="size-3.5 rounded-full ring-offset-2 ring-offset-[var(--bg-base)] transition-transform hover:scale-125 aria-checked:ring-2 aria-checked:ring-[var(--text-secondary)]"
            style={{ background: c }}
          />
        ))}
      </div>
    </div>
  );
}
