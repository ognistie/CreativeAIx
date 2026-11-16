import { useCallback, useEffect, useState } from "react";

// Abertura do app: marca sobre as luzes da paleta, em intensidade cheia. Depois da entrada (e com o nucleo
// conectado), convida a pressionar qualquer tecla ou clicar; ao sair some com um leve zoom e revela o app,
// que ja esta montado por baixo (nada muda de tamanho nem de posicao).

type Phase = "intro" | "ready" | "leaving";

export function Splash({ coreReady, photo, onDone }: { coreReady: boolean; photo?: string | null; onDone: () => void }) {
  const [phase, setPhase] = useState<Phase>("intro");
  const [introDone, setIntroDone] = useState(false);
  // Tecla ou clique antes do nucleo ficar pronto: lembra e entra assim que ele estiver (antes era ignorado)
  const [wants, setWants] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setIntroDone(true), 1500);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (introDone && coreReady && phase === "intro") setPhase("ready");
  }, [introDone, coreReady, phase]);

  const leave = useCallback(() => {
    if (phase === "leaving") return;
    if (phase !== "ready") {
      setWants(true);
      return;
    }
    setPhase("leaving");
    setTimeout(onDone, 560);
  }, [phase, onDone]);

  useEffect(() => {
    if (wants && phase === "ready") leave();
  }, [wants, phase, leave]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      e.preventDefault();
      leave();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [leave]);

  return (
    <div
      role="dialog"
      aria-label="Creative AIx. Pressione qualquer tecla para entrar."
      onClick={leave}
      data-phase={phase}
      className="splash fixed inset-0 z-[100] grid place-items-center overflow-hidden bg-canvas"
      style={{ cursor: phase === "ready" ? "pointer" : "default" }}
    >
      {photo ? (
        <div aria-hidden className="absolute inset-0">
          <img src={photo} alt="" className="size-full object-cover" />
          <div className="absolute inset-0 bg-[radial-gradient(60%_50%_at_50%_50%,rgb(0_0_0/0.22),transparent_75%)]" />
        </div>
      ) : (
        <div aria-hidden className="splash-lights absolute inset-0" />
      )}
      <div className="splash-brand relative -mt-6 flex flex-col items-center">
        <svg width={40} height={40} viewBox="0 0 24 24" aria-hidden className="photo-ink mb-[18px] text-fg">
          {[0, 1, 2, 3].map((i) => (
            <rect key={i} x={2 + (i % 2) * 11} y={2 + Math.floor(i / 2) * 11} width={9} height={9} rx={2.6} fill={i === 3 ? "var(--accent)" : "currentColor"} />
          ))}
        </svg>
        <h1 className="photo-ink font-display text-[56px] font-semibold leading-none tracking-[-0.022em] text-fg">Creative AIx</h1>
        <p className="splash-tagline photo-ink-muted mt-3 text-lg font-medium text-fg-muted">Linguagem natural entra. Ações reais saem.</p>
      </div>
      <div className="splash-hint absolute bottom-[max(48px,12vh)] left-1/2 flex h-[38px] -translate-x-1/2 items-center gap-2.5 rounded-full border border-hairline bg-chip px-4 text-sm text-fg-muted backdrop-blur-xl">
        <span className="size-1.5 animate-pulse rounded-full bg-accent" />
        {phase === "intro" && (introDone || wants) ? "Conectando ao núcleo…" : "Pressione qualquer tecla ou clique para entrar"}
      </div>
    </div>
  );
}
