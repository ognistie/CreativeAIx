/** Anel de progresso com o numero no meio (feitas / total). Decorativo: o texto ao lado diz o mesmo. */
export function ProgressRing({ done, total, size = 34, className }: { done: number; total: number; size?: number; className?: string }) {
  const r = (size - 5) / 2;
  const c = 2 * Math.PI * r;
  const p = total > 0 ? done / total : 0;
  return (
    <span className={className} style={{ position: "relative", display: "inline-grid", placeItems: "center", width: size, height: size }} aria-hidden>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ position: "absolute", inset: 0, transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeOpacity="0.18" strokeWidth="2.5" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray={`${c * p} ${c}`}
          style={{ transition: "stroke-dasharray var(--dur-slow) var(--ease-out)" }}
        />
      </svg>
      <span style={{ fontSize: size * 0.36, fontWeight: 600, lineHeight: 1 }}>{total - done}</span>
    </span>
  );
}
