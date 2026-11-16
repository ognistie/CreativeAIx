import { useMemo, useState } from "react";
import { cn } from "../../lib/cn";
import { IconButton } from "../ui";

// Calendario do Diario: dias com entrada ganham um ponto; clicar filtra as entradas do dia.
// Grade de botoes (Tab/Enter); setas trocam o mes.

const WEEK = ["D", "S", "T", "Q", "Q", "S", "S"];
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export function MonthCalendar({ dates, selected, onSelect }: { dates: string[]; selected: string; onSelect: (day: string) => void }) {
  const has = useMemo(() => new Set(dates), [dates]);
  const today = iso(new Date());
  const [cursor, setCursor] = useState(() => {
    const base = selected || today;
    return new Date(Number(base.slice(0, 4)), Number(base.slice(5, 7)) - 1, 1);
  });

  const cells = useMemo(() => {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const start = new Date(first);
    start.setDate(1 - first.getDay());
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      return d;
    });
  }, [cursor]);

  const month = cursor.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  const inMonth = dates.filter((d) => d.startsWith(iso(cursor).slice(0, 7))).length;

  return (
    <div>
      <div className="mb-3 flex items-center gap-1">
        <div className="min-w-0 flex-1">
          <p className="font-display text-lg font-semibold text-fg first-letter:uppercase">{month}</p>
          <p className="text-xs text-fg-muted">
            {inMonth} {inMonth === 1 ? "dia com entrada" : "dias com entrada"}
          </p>
        </div>
        <IconButton icon="arrow-left" label="Mês anterior" flat onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} />
        <IconButton icon="arrow-right" label="Próximo mês" flat onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} />
      </div>
      <div className="grid grid-cols-7 gap-1 text-center" role="grid" aria-label={month}>
        {WEEK.map((w, i) => (
          <span key={i} className="pb-1 text-[11px] font-medium text-fg-subtle" aria-hidden>
            {w}
          </span>
        ))}
        {cells.map((d) => {
          const key = iso(d);
          const out = d.getMonth() !== cursor.getMonth();
          const on = key === selected;
          const mark = has.has(key);
          return (
            <button
              key={key}
              type="button"
              onClick={() => onSelect(on ? "" : key)}
              aria-pressed={on}
              aria-label={`${d.toLocaleDateString("pt-BR", { day: "numeric", month: "long" })}${mark ? ", tem entrada" : ""}`}
              className={cn(
                "relative grid aspect-square place-items-center rounded-full text-sm transition-colors",
                out ? "text-fg-subtle/60" : "text-fg",
                mark && !on && "font-semibold",
                on ? "bg-primary text-fg-inverse" : "hover:bg-row-hover",
                key === today && !on && "ring-1 ring-hairline-hi",
              )}
            >
              {d.getDate()}
              {mark && <span aria-hidden className={cn("absolute bottom-1 size-1 rounded-full", on ? "bg-fg-inverse" : "bg-accent")} />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
