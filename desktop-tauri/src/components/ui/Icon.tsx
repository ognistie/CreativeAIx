import { ICONS, type IconName } from "../../lib/icons.gen";

/** Icones de linha do app (os mesmos desenhos do Icon.qml): viewBox 24, traco fino, pontas arredondadas. */
export function Icon({
  name,
  size = 16,
  weight = 1.7,
  className,
  label,
}: {
  name: IconName;
  size?: number;
  weight?: number;
  className?: string;
  /** Texto para leitor de tela. Sem label, o icone e decorativo. */
  label?: string;
}) {
  // Mesma compensacao do QML: o traco fica visualmente igual em tamanhos diferentes
  const stroke = ((weight * 24) / Math.max(12, size)) * (size >= 20 ? 0.9 : 1);
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

export type { IconName };
