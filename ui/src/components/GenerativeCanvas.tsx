import { useEffect, useRef } from "react";
import { currentColors, drawGenerative, prepareGenerative, zoneRamps, type Generative, type SafeRect } from "../lib/generative";
import { artFor, DEFAULT_PREFS, motionFps, prefsOverride, type ArtPrefs } from "../lib/wallpaper/art";
import { FrameBudget, particlesAt } from "../lib/wallpaper/motion";

// Papel de parede gerativo (lib/generative.ts) num canvas do tamanho do proprio elemento.
// - A cena e montada em fatias fora do caminho da interacao (prepareGenerative) e pintada uma vez; so refaz quando
//   o tamanho, a aparencia ou a area da interface mudam. Trocar paleta/destaque reaproveita o buffer (cache).
// - `live` (o fundo da janela): zonas da interface medidas da tela (barra lateral, coluna do conteudo e caixa de
//   pedido) ficam com menos luz e contraste; e a camada de movimento da cena (estrelas, bolhas, poeira) roda a 30 qps,
//   parando com a janela sem foco ou escondida, com "Movimento" desligado e com redução de movimento do sistema.
// - Miniaturas (sem `live`): so a cena, sem mascara nem movimento.
export function GenerativeCanvas({ art, look, className, live = false, deferred = false, prefs = DEFAULT_PREFS }: {
  art: Generative; look: string; className?: string; live?: boolean; deferred?: boolean;
  /** Opções avançadas da Aparência. */
  prefs?: ArtPrefs;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const { dither, quality } = prefs;
  const motionRef = useRef<HTMLCanvasElement>(null);
  const lastFrame = useRef("");

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    let timer = 0;
    let frame = 0;
    let abort: AbortController | undefined;
    let pending = "";
    let visible = !deferred;
    const override = prefsOverride({ ...DEFAULT_PREFS, dither, quality }, deferred ? { saving: true } : undefined);
    const draw = () => {
      if (!visible) return;
      const { width, height } = canvas.getBoundingClientRect();
      if (!width || !height) return;
      const scale = Math.min(1, 2560 / Math.max(width, height));
      const w = Math.max(1, Math.round(width * scale)), h = Math.max(1, Math.round(height * scale));
      const safe = live ? measureSafe(canvas) : [];
      const key = `${w}x${h}|${art.style}|${art.scene}|${look}|${dither}|${quality}|${safe.map((r) => `${r.x.toFixed(2)},${r.y.toFixed(2)},${r.w.toFixed(2)},${r.h.toFixed(2)}`).join(";")}`;
      if (key === pending) return;
      abort?.abort();
      cancelAnimationFrame(frame);
      pending = "";
      if (key === lastFrame.current) return;
      pending = key;
      abort = new AbortController();
      const { signal } = abort;
      frame = requestAnimationFrame(() => {
        void prepareGenerative(art.style, w, h, art.scene, { signal, art: override, worker: live }).then((ready) => {
          if (signal.aborted) return;
          pending = "";
          if (!ready) return;
          const ctx = canvas.getContext("2d");
          if (!ctx) return;
          if (canvas.width !== w) canvas.width = w;
          if (canvas.height !== h) canvas.height = h;
          drawGenerative(ctx, art.style, w, h, currentColors(canvas), art.scene, { safe, art: override });
          lastFrame.current = key;
        });
      });
    };
    const intersection = deferred ? new IntersectionObserver(([entry]) => {
      visible = !!entry?.isIntersecting;
      if (visible) draw();
      else {
        abort?.abort();
        cancelAnimationFrame(frame);
        pending = "";
      }
    }, { rootMargin: "100px" }) : null;
    intersection?.observe(canvas);
    draw();
    const observer = new ResizeObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(draw, 160);
    });
    observer.observe(canvas);
    // a barra lateral abre/fecha sem mudar o tamanho do fundo: observa a area principal tambem.
    // Trocar de pagina NAO redesenha: as zonas (measureSafe) so dependem do tamanho da barra e da area principal.
    // Antes cada troca de pagina refazia o canvas inteiro (ate 2560 px) e o reenviava a GPU; no QtWebEngine essa
    // carga fazia a barra lateral sumir por alguns quadros logo depois do clique.
    const main = live ? document.querySelector("main") : null;
    if (main) observer.observe(main);
    return () => {
      observer.disconnect();
      intersection?.disconnect();
      window.clearTimeout(timer);
      cancelAnimationFrame(frame);
      abort?.abort();
    };
  }, [art.style, art.scene, look, live, deferred, dither, quality]);

  // Camada de movimento (so no fundo da janela e so nas cenas que tem o que mover)
  const fps = motionFps(prefs);
  const kind = fps ? artFor(art.scene).motion : null;
  useEffect(() => {
    const layer = motionRef.current;
    if (!live || !kind || !layer) return;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0, last = 0, running = false;
    const budget = new FrameBudget(fps);
    const start = performance.now();
    let safe: SafeRect[] = [];
    let color = "#fff";
    const motionEnabled = () => !reduce.matches && document.documentElement.dataset.motion !== "off";
    const allowed = () => motionEnabled() && !document.hidden && document.hasFocus();
    const setup = () => {
      const { width, height } = layer.getBoundingClientRect();
      const scale = Math.min(1, 1920 / Math.max(width, height, 1));
      const w = Math.max(1, Math.round(width * scale)), h = Math.max(1, Math.round(height * scale));
      if (layer.width !== w) layer.width = w;
      if (layer.height !== h) layer.height = h;
      safe = measureSafe(layer);
      const ramps = zoneRamps(currentColors(layer), artFor(art.scene).hues);
      color = (kind === "dust" ? ramps[1]! : ramps[3]!)[6]!;
    };
    const tick = (now: number) => {
      frame = requestAnimationFrame(tick);
      if (now - last < 1000 / budget.fps) return;
      last = now;
      const t0 = performance.now();
      const ctx = layer.getContext("2d");
      if (!ctx) return;
      const w = layer.width, h = layer.height, scale = Math.min(1.4, Math.max(0.3, w / 1440));
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = color;
      const mark = (art.style === "dither" ? 3 : 3.2) * scale;
      for (const p of particlesAt(kind, (now - start) / 1000, w / h, safe)) {
        ctx.globalAlpha = p.alpha;
        const s = mark * p.size, x = p.x * w, y = p.y * h;
        if (art.style === "dither") ctx.fillRect(Math.round(x / s) * s, Math.round(y / s) * s, s, s);
        else { ctx.beginPath(); ctx.arc(x, y, s / 2, 0, Math.PI * 2); ctx.fill(); }
      }
      ctx.globalAlpha = 1;
      budget.record(performance.now() - t0);
    };
    const sync = () => {
      const ok = allowed();
      if (ok && !running) { running = true; setup(); frame = requestAnimationFrame(tick); }
      else if (!ok && running) { running = false; cancelAnimationFrame(frame); }
      if (!motionEnabled()) layer.getContext("2d")?.clearRect(0, 0, layer.width, layer.height);
    };
    sync();
    const attrs = new MutationObserver(sync);
    attrs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-motion"] });
    const resize = new ResizeObserver(() => running && setup());
    resize.observe(layer);
    window.addEventListener("focus", sync);
    window.addEventListener("blur", sync);
    document.addEventListener("visibilitychange", sync);
    reduce.addEventListener("change", sync);
    return () => {
      cancelAnimationFrame(frame);
      attrs.disconnect();
      resize.disconnect();
      window.removeEventListener("focus", sync);
      window.removeEventListener("blur", sync);
      document.removeEventListener("visibilitychange", sync);
      reduce.removeEventListener("change", sync);
    };
  }, [live, kind, fps, art.style, art.scene, look]);

  return (
    <span className={className} style={{ position: "relative", display: "block" }} aria-hidden>
      <canvas ref={ref} className="absolute inset-0 size-full" style={{ imageRendering: "pixelated" }} />
      {live && kind && <canvas ref={motionRef} className="absolute inset-0 size-full" />}
    </span>
  );
}

/** Zonas da interface sobre o fundo, em fracoes do canvas: a barra lateral, a coluna do meio da area principal
 *  (titulos e o comeco da conversa) e a faixa de baixo dessa coluna (caixa de pedido). Dependem so da geometria
 *  da janela, nunca do conteudo da pagina: trocar de tela nao redesenha o fundo. */
export function measureSafe(canvas: Element): SafeRect[] {
  const box = canvas.getBoundingClientRect();
  if (!box.width || !box.height) return [];
  const frac = (r: DOMRect, strength: number, pad = 0): SafeRect => ({
    x: (r.left - pad - box.left) / box.width, y: (r.top - pad - box.top) / box.height,
    w: (r.width + 2 * pad) / box.width, h: (r.height + 2 * pad) / box.height, strength,
  });
  const out: SafeRect[] = [];
  const side = document.querySelector(".sidebar-panel");
  if (side) out.push(frac(side.getBoundingClientRect(), 0.55, 6));
  const main = document.querySelector("main")?.getBoundingClientRect();
  if (main && main.width && main.height) {
    const colW = Math.min(780, main.width * 0.62), left = main.left + (main.width - colW) / 2;
    out.push(frac(new DOMRect(left, main.top + main.height * 0.12, colW, main.height * 0.3), 0.42));
    const band = Math.min(190, main.height * 0.24);
    out.push(frac(new DOMRect(left, main.bottom - band - 12, colW, band), 0.5));
  }
  return out;
}
