import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { forwardRef } from "react";
import { cn } from "../../lib/cn";
import { Icon, type IconName } from "./Icon";

/** Chip.qml: filtro/selecao. 30px, selecionado = cor primaria. Bolinha de cor opcional. */
export function Chip({
  selected,
  icon,
  swatch,
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean; icon?: IconName; swatch?: string }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={cn(
        "press motion-fast inline-flex h-[30px] items-center gap-1.5 rounded-full px-[11px] text-sm transition-colors",
        selected ? "bg-primary text-fg-inverse" : "bg-chip text-fg-muted hover:bg-row-hover",
        className,
      )}
      {...props}
    >
      {swatch && <span className="size-3 rounded-full border border-hairline-hi" style={{ background: swatch }} />}
      {icon && <Icon name={icon} size={12} />}
      {children}
    </button>
  );
}

/** TogglePill.qml: liga/desliga com rotulo (28px). */
export function TogglePill({
  checked,
  onCheckedChange,
  icon,
  className,
  children,
  ...props
}: Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> & {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  icon?: IconName;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "press motion-fast inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-sm transition-colors",
        checked
          ? "border-primary/35 bg-primary/12 text-fg"
          : "border-hairline text-fg-muted hover:bg-hover hover:text-fg",
        className,
      )}
      {...props}
    >
      {icon && <Icon name={icon} size={12} />}
      {children}
    </button>
  );
}

/** Segmented.qml: escolha unica entre poucas opcoes, trilho com pilula deslizante. */
export function Segmented<T extends string>({
  options,
  value,
  onValueChange,
  label,
  className,
}: {
  options: ReadonlyArray<{ value: T; label: string; icon?: IconName }>;
  value: T;
  onValueChange: (v: T) => void;
  label: string;
  className?: string;
}) {
  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      onValueChange={(v) => v && onValueChange(v as T)}
      aria-label={label}
      className={cn("inline-flex h-8 items-center gap-0.5 rounded-full border border-hairline bg-chip p-[3px]", className)}
    >
      {options.map((o) => (
        <ToggleGroup.Item
          key={o.value}
          value={o.value}
          className={cn(
            "motion-normal inline-flex h-full items-center gap-1.5 rounded-full px-3 text-sm transition-colors",
            "text-fg-muted hover:text-fg data-[state=on]:bg-primary data-[state=on]:text-fg-inverse",
          )}
        >
          {o.icon && <Icon name={o.icon} size={12} />}
          {o.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}

/** AppField.qml: campo de texto 38px, borda de destaque no foco. */
export const Field = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Field(
  { className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        "motion-fast h-[38px] w-full rounded-r3 border border-hairline-hi bg-surface px-3 text-md text-fg",
        "outline-none transition-[border-color] placeholder:text-fg-subtle focus:border-accent/60",
        "focus-visible:outline-none disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
});
