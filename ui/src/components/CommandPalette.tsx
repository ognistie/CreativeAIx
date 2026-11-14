import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useMemo, useState } from "react";
import { cn } from "../lib/cn";
import { core } from "../lib/host";
import { Icon, type IconName } from "./ui";

// CommandPalette.qml: Ctrl+K abre; busca paginas, conversas, temas da Biblioteca e entradas do Diario.

export interface PaletteItem {
  id: string;
  title: string;
  area: string;
  icon: IconName;
  hint?: string;
  run: () => void;
}

const fold = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function CommandPalette({
  open,
  onOpenChange,
  base,
  onTopic,
  onDiary,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  base: PaletteItem[];
  onTopic: (id: string) => void;
  onDiary: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [extra, setExtra] = useState<PaletteItem[]>([]);
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    void Promise.all([
      core().call("librarySearch", "", "", "").catch(() => null),
      core().call("journalList", "", "", "").catch(() => null),
    ]).then(([lib, diary]) => {
      const topics = ((lib as { items?: Array<{ id: string; title: string }> } | null)?.items ?? []).map((t) => ({
        id: `topic:${t.id}`, title: t.title, area: "Biblioteca", icon: "book" as IconName, run: () => onTopic(t.id),
      }));
      const entries = ((diary as { items?: Array<{ id: string; title: string }> } | null)?.items ?? []).slice(0, 30).map((e) => ({
        id: `diary:${e.id}`, title: e.title || "Sem título", area: "Diário", icon: "notebook" as IconName, run: () => onDiary(e.id),
      }));
      setExtra([...topics, ...entries]);
    });
  }, [open, onTopic, onDiary]);

  const items = useMemo(() => {
    const q = fold(query.trim());
    const all = [...base, ...extra];
    return (q ? all.filter((i) => fold(`${i.title} ${i.area}`).includes(q)) : all).slice(0, 40);
  }, [query, base, extra]);

  useEffect(() => setActive(0), [query]);

  const choose = (i: PaletteItem | undefined) => {
    if (!i) return;
    onOpenChange(false);
    i.run();
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <Dialog.Content
          aria-describedby={undefined}
          className="animate-enter fixed left-1/2 top-[14vh] z-50 w-[min(560px,calc(100vw-32px))] -translate-x-1/2 overflow-hidden rounded-r4 border border-edge bg-glass-hi shadow-[0_24px_60px_var(--shadow)] backdrop-blur-2xl"
        >
          <Dialog.Title className="sr-only">Buscar e ir para</Dialog.Title>
          <div className="flex items-center gap-2 border-b border-hairline px-4">
            <Icon name="search" size={16} className="text-fg-muted" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") (e.preventDefault(), setActive((a) => Math.min(a + 1, items.length - 1)));
                else if (e.key === "ArrowUp") (e.preventDefault(), setActive((a) => Math.max(a - 1, 0)));
                else if (e.key === "Enter") (e.preventDefault(), choose(items[active]));
              }}
              placeholder="Buscar páginas, conversas, temas e notas do Diário"
              aria-label="Buscar"
              role="combobox"
              aria-expanded
              aria-controls="palette-list"
              aria-activedescendant={items[active] ? `pal-${items[active].id}` : undefined}
              className="h-12 flex-1 bg-transparent text-md text-fg outline-none placeholder:text-fg-subtle"
            />
            <kbd className="text-xs text-fg-subtle">Esc</kbd>
          </div>
          <ul id="palette-list" role="listbox" className="max-h-[50vh] overflow-y-auto p-1.5">
            {items.length === 0 && <li className="px-3 py-6 text-center text-sm text-fg-subtle">Nada encontrado</li>}
            {items.map((i, n) => (
              <li
                key={i.id}
                id={`pal-${i.id}`}
                role="option"
                aria-selected={n === active}
                onMouseMove={() => setActive(n)}
                onClick={() => choose(i)}
                className={cn("flex h-9 cursor-default items-center gap-2.5 rounded-r2 px-3 text-[13px]", n === active ? "bg-row-hover text-fg" : "text-fg-muted")}
              >
                <Icon name={i.icon} size={15} />
                <span className="flex-1 truncate">{i.title}</span>
                <span className="text-xs text-fg-subtle">{i.hint ?? i.area}</span>
              </li>
            ))}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
