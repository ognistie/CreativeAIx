import { ProgressRing } from "../ProgressRing";
import { Icon } from "../ui";

// Entrada do Diario como folha de papel (referencia: papel amassado que se desamassa ao passar o mouse).
// Amassado = vincos em gradiente + leve rotacao; no hover/foco os vincos somem e a folha fica reta.
// Tinta escura sobre papel claro nos dois temas (contraste >= 7:1).

const fmt = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }).replace(".", "");
};

export function PaperCard({
  title,
  date,
  summary,
  tags,
  isPrivate,
  priorities,
  openTasks,
  seed,
  onOpen,
}: {
  title: string;
  date: string;
  summary: string;
  tags: string[];
  isPrivate: boolean;
  priorities: number;
  openTasks: number;
  seed: number;
  onOpen: () => void;
}) {
  const tilt = ((seed * 37) % 7) - 3;
  return (
    <button type="button" onClick={onOpen} className="paper" style={{ ["--tilt" as string]: `${tilt * 0.6}deg`, ["--crease" as string]: `${(seed * 53) % 360}deg` }}>
      <span aria-hidden className="paper-creases" />
      <span className="relative flex items-start justify-between gap-3">
        <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-[#5b605c]">{fmt(date)}</span>
        {isPrivate && <span className="paper-stamp">privada</span>}
      </span>
      <span className="relative mt-3 line-clamp-2 font-display text-[18px] font-semibold leading-snug tracking-[-0.01em] text-[#1d211f]">{title || "Sem título"}</span>
      {summary && <span className="relative mt-2 line-clamp-4 text-[13.5px] leading-relaxed text-[#3d4340]">{summary}</span>}
      <span className="relative mt-auto flex items-center gap-3 pt-4 text-[12px] text-[#4a504c]">
        {openTasks > 0 && (
          <span className="flex shrink-0 items-center gap-1.5" title="Tarefas abertas">
            <ProgressRing done={0} total={openTasks} size={22} /> {openTasks === 1 ? "aberta" : "abertas"}
          </span>
        )}
        {priorities > 0 && (
          <span className="flex shrink-0 items-center gap-1" title="Prioridades">
            <Icon name="flag" size={12} /> {priorities}
          </span>
        )}
        {tags.length > 0 && <span className="ml-auto min-w-0 truncate font-mono text-[11px]">#{tags.slice(0, 2).join(" #")}</span>}
      </span>
    </button>
  );
}
