import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";
import { cn } from "../../lib/cn";
import { Icon, type IconName } from "./Icon";

// Button.qml: primary (fundo claro), secondary (contorno), ghost (so texto). Pilula, pressao discreta.
const button = cva(
  "press motion-fast inline-flex select-none items-center justify-center gap-1.5 rounded-full font-medium " +
    "transition-[background-color,color,transform,box-shadow] disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        primary: "bg-primary text-fg-inverse hover:brightness-110 active:brightness-90",
        secondary: "border border-hairline-hi text-fg hover:bg-hover active:bg-pressed",
        ghost: "text-fg-muted hover:bg-hover hover:text-fg active:bg-pressed",
        danger: "bg-bad/15 text-bad hover:bg-bad/25 active:bg-bad/30",
      },
      size: {
        md: "h-9 px-3.5 text-[13px]",
        compact: "h-[30px] px-2.5 text-sm",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {
  icon?: IconName;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, icon, children, type = "button", ...props },
  ref,
) {
  return (
    <button ref={ref} type={type} className={cn(button({ variant, size }), className)} {...props}>
      {icon && <Icon name={icon} size={size === "compact" ? 12 : 14} />}
      {children}
    </button>
  );
});

// IconButton.qml: 34x34, redondo, so icone; `label` vira dica e nome acessivel.
export const IconButton = forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { icon: IconName; label: string; flat?: boolean }
>(function IconButton({ icon, label, flat, className, type = "button", ...props }, ref) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      className={cn(
        "press motion-fast grid size-[34px] shrink-0 place-items-center rounded-full text-fg-muted transition-colors",
        "hover:bg-hover hover:text-fg active:bg-pressed disabled:pointer-events-none disabled:opacity-40",
        !flat && "bg-chip",
        className,
      )}
      {...props}
    >
      <Icon name={icon} size={16} />
    </button>
  );
});
