import { Icon, type IconName } from "../components/ui";

// Moldura comum das telas (PageHeader + ScrollPage): titulo, subtitulo e coluna de leitura.
export function Page({
  title,
  subtitle,
  actions,
  children,
  wide,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="h-full overflow-y-auto px-8">
      <div className={wide ? "mx-auto max-w-5xl py-12" : "mx-auto max-w-[var(--content-max)] py-12"}>
        <header className="on-photo animate-enter mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-[28px] font-medium tracking-[-0.03em] text-fg">{title}</h1>
            {subtitle && <p className="mt-1.5 max-w-xl text-md text-fg-muted">{subtitle}</p>}
          </div>
          {actions}
        </header>
        {children}
      </div>
    </div>
  );
}

export function Section({ title, hint, icon, children }: { title: string; hint?: string; icon?: IconName; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <div className="photo-label">
        <h2 className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">
          {icon && <Icon name={icon} size={13} />}
          {title}
        </h2>
        {hint && <p className="mt-1 text-sm text-fg-muted">{hint}</p>}
      </div>
      <div className="mt-3 overflow-hidden rounded-r3 border border-edge bg-glass backdrop-blur-xl">{children}</div>
    </section>
  );
}

/** Linha de configuracao com rotulo, descricao e controle a direita. */
export function Row({ label, hint, children }: { label: string; hint?: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-4 border-b border-hairline px-4 py-3 last:border-0">
      <div className="min-w-0 flex-1">
        <p className="text-md text-fg">{label}</p>
        {hint && <p className="mt-0.5 text-sm text-fg-muted">{hint}</p>}
      </div>
      {children}
    </div>
  );
}

/** Interruptor acessivel (role switch). Trilho 40x24 com o botao preso a esquerda (left-0.5): antes o botao
 *  ficava sem ancora, o navegador o centralizava e ele saia do trilho; desligado, o trilho tinha a cor do vidro e
 *  sumia sobre fundo claro. */
export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`motion-normal relative inline-flex h-6 w-10 shrink-0 items-center rounded-full border transition-colors ${
        checked ? "border-transparent bg-accent" : "border-hairline-hi bg-[color-mix(in_oklab,var(--text-primary)_14%,transparent)]"
      }`}
    >
      <span
        aria-hidden
        className={`motion-normal absolute left-0.5 top-1/2 size-[18px] -translate-y-1/2 rounded-full bg-white shadow-[0_1px_3px_rgb(0_0_0/0.3)] transition-transform ${
          checked ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}
