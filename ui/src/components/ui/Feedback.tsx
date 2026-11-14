import { cn } from "../../lib/cn";
import { Icon, type IconName } from "./Icon";

/** Spinner.qml */
export function Spinner({ size = 14, className, label = "Carregando" }: { size?: number; className?: string; label?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      role="status"
      aria-label={label}
      className={cn("text-fg-muted", className)}
      style={{ animation: "spin 0.9s linear infinite" }}
    >
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2.5" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

/** Skeleton.qml: bloco pulsando enquanto o dado chega. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("rounded-r1 bg-chip", className)} style={{ animation: "skeleton-pulse 1.4s ease-in-out infinite" }} />;
}

export type Status = "ok" | "done" | "warn" | "clarify" | "limited" | "cancelled" | "fail" | "failed";

const STATUS: Record<Status, { tone: string; icon: IconName; label: string }> = {
  ok: { tone: "bg-ok", icon: "check", label: "Concluído" },
  done: { tone: "bg-ok", icon: "check", label: "Concluído" },
  warn: { tone: "bg-warn", icon: "alert-triangle", label: "Atenção" },
  clarify: { tone: "bg-warn", icon: "help", label: "Precisa de resposta" },
  limited: { tone: "bg-warn", icon: "alert-triangle", label: "Parcial" },
  cancelled: { tone: "bg-fg-subtle", icon: "x", label: "Cancelado" },
  fail: { tone: "bg-bad", icon: "x", label: "Falhou" },
  failed: { tone: "bg-bad", icon: "x", label: "Falhou" },
};

/** StatusDot.qml: bolinha com o icone do resultado (cor nunca e o unico sinal). */
export function StatusDot({ status, size = 15 }: { status: Status; size?: number }) {
  const s = STATUS[status] ?? STATUS.ok;
  return (
    <span
      role="img"
      aria-label={s.label}
      title={s.label}
      className={cn("inline-grid shrink-0 place-items-center rounded-full text-fg-inverse", s.tone)}
      style={{ width: size, height: size }}
    >
      <Icon name={s.icon} size={Math.round(size * 0.62)} weight={2.4} />
    </span>
  );
}

/** EmptyState.qml: icone num quadrado, titulo, texto e acao opcional. */
export function EmptyState({
  icon = "sparkle",
  title,
  children,
  action,
}: {
  icon?: IconName;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="animate-enter flex flex-col items-center gap-2 px-6 py-10 text-center">
      <span className="mb-1 grid size-10 place-items-center rounded-r2 bg-chip text-fg-muted">
        <Icon name={icon} size={18} />
      </span>
      <p className="text-md font-semibold text-fg">{title}</p>
      {children && <p className="max-w-sm text-[13px] text-fg-muted">{children}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
