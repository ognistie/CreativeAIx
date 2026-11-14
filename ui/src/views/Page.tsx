// Moldura comum das telas (PageHeader.qml + ScrollPage.qml): titulo, subtitulo e coluna de leitura.
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

export function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-1 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">{title}</h2>
      {hint && <p className="mb-3 text-sm text-fg-subtle">{hint}</p>}
      <div className="mt-3 overflow-hidden rounded-r3 border border-edge bg-glass">{children}</div>
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

/** Interruptor acessivel (role switch). */
export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`motion-normal relative h-6 w-10 shrink-0 rounded-full transition-colors ${checked ? "bg-accent" : "bg-chip"}`}
    >
      <span
        className={`motion-normal absolute top-0.5 size-5 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-[18px]" : "translate-x-0.5"}`}
      />
    </button>
  );
}
