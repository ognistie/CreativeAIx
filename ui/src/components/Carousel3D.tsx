import { useCallback, useEffect, useLayoutEffect, useRef } from "react";
import { cn } from "../lib/cn";
import { IconButton } from "./ui";

// Carrossel em curva (referencia: cards de vidro que dobram nas bordas). Rolagem nativa com scroll-snap,
// entao roda do mouse, trackpad, toque e teclado funcionam; o efeito 3D e so transform, calculado num
// requestAnimationFrame por rolagem (sem re-render do React). Sem movimento (Harness ou sistema): plano.
// Em loop: a lista aparece 3 vezes e a rolagem salta uma volta inteira quando chega perto das pontas,
// entao sempre ha cards dos dois lados. So a copia do meio e alcancavel por teclado e leitor de tela.

const reduced = () =>
  document.documentElement.dataset.motion === "off" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const COPIES = 3;

export function Carousel3D({ label, children, className }: { label: string; children: React.ReactNode[]; className?: string }) {
  const track = useRef<HTMLDivElement>(null);
  const frame = useRef(0);
  const n = children.length;

  /** Largura de uma volta (distancia entre o 1o item da copia 0 e o 1o da copia 1). */
  const lap = () => {
    const el = track.current;
    const a = el?.children[0] as HTMLElement | undefined;
    const b = el?.children[n] as HTMLElement | undefined;
    return a && b ? b.offsetLeft - a.offsetLeft : 0;
  };

  const paint = useCallback(() => {
    frame.current = 0;
    const el = track.current;
    if (!el) return;
    const w = lap();
    if (w > 0) {
      if (el.scrollLeft < w * 0.5) el.scrollLeft += w;
      else if (el.scrollLeft > w * 1.5) el.scrollLeft -= w;
    }
    const flat = reduced();
    const mid = el.scrollLeft + el.clientWidth / 2;
    for (const item of Array.from(el.children) as HTMLElement[]) {
      const c = item.offsetLeft + item.offsetWidth / 2;
      const d = Math.max(-2.2, Math.min(2.2, (c - mid) / (item.offsetWidth * 1.15)));
      const a = Math.min(Math.abs(d), 1.6);
      item.style.transform = flat
        ? ""
        : `perspective(1100px) translateZ(${-a * 120}px) rotateY(${-d * 32}deg) scale(${1 - Math.min(a, 1) * 0.06})`;
      item.style.opacity = flat ? "" : String(Math.max(0, 1 - Math.max(0, a - 0.95) * 0.7));
      item.style.zIndex = String(100 - Math.round(a * 10));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [n]);

  const schedule = useCallback(() => {
    if (!frame.current) frame.current = requestAnimationFrame(paint);
  }, [paint]);

  // Comeca no 1o item da copia do meio, centralizado
  useLayoutEffect(() => {
    const el = track.current;
    const first = el?.children[n] as HTMLElement | undefined;
    if (el && first) el.scrollLeft = first.offsetLeft + first.offsetWidth / 2 - el.clientWidth / 2;
    paint();
  }, [n, paint]);

  useEffect(() => {
    const el = track.current;
    if (!el) return;
    const ro = new ResizeObserver(schedule);
    ro.observe(el);
    return () => {
      ro.disconnect();
      cancelAnimationFrame(frame.current);
    };
  }, [schedule]);

  const step = (dir: number) => {
    const el = track.current;
    const first = el?.children[0] as HTMLElement | undefined;
    if (!el || !first) return;
    el.scrollBy({ left: dir * (first.offsetWidth + 20), behavior: reduced() ? "auto" : "smooth" });
  };

  return (
    <section aria-roledescription="carrossel" aria-label={label} className={cn("relative", className)}>
      <div
        ref={track}
        onScroll={schedule}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") (e.preventDefault(), step(1));
          if (e.key === "ArrowLeft") (e.preventDefault(), step(-1));
        }}
        className="carousel-track flex snap-x snap-mandatory gap-5 overflow-x-auto py-8"
      >
        {Array.from({ length: COPIES }, (_, copy) =>
          children.map((child, i) => {
            const real = copy === 1;
            return (
              <div
                key={`${copy}-${i}`}
                className="carousel-item shrink-0 snap-center"
                aria-hidden={real ? undefined : true}
                {...(real ? {} : ({ inert: "" } as Record<string, string>))}
                aria-roledescription={real ? "slide" : undefined}
                aria-label={real ? `${i + 1} de ${n}` : undefined}
              >
                {child}
              </div>
            );
          }),
        )}
      </div>
      <div className="pointer-events-none absolute inset-x-0 top-1/2 z-[200] flex -translate-y-1/2 justify-between px-4">
        <IconButton icon="arrow-left" label="Anterior" className="pointer-events-auto" onClick={() => step(-1)} />
        <IconButton icon="arrow-right" label="Próximo" className="pointer-events-auto" onClick={() => step(1)} />
      </div>
    </section>
  );
}
