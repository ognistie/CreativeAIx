import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Prose } from "../components/Prose";
import { Button, Segmented } from "../components/ui";
import { openExternal } from "../lib/host";
import { LEVEL_LABEL } from "../lib/topics";

// Leitor de livro da Biblioteca. Dois modelos, como livros digitais:
//  - "ereader": uma pagina por vez, papel de e-ink, texto justificado, rodape com % e localizacao (estilo Kindle)
//  - "livro": livro aberto, duas paginas lado a lado, abertura de capitulo com moldura e numero das paginas
// A paginacao e feita pelo proprio navegador (colunas CSS): o texto flui de uma pagina para a outra e a
// leitura anda uma pagina (ou um par) por vez, com as setas, os botoes ou clique nas bordas.
// A pagina atual e mostrada pela ROLAGEM do quadro (scrollLeft), nao por transform: o texto em colunas tem
// milhares de pixels de largura e, transformado com transicao, virava uma camada gigante na GPU que fazia a
// barra lateral (vidro com desfoque) piscar e sumir.

export type ReaderModel = "ereader" | "livro";
const MODEL_KEY = "creative-aix.reader";

interface Reading { title: string; authors: string; year: number; url: string; venue: string; note: string }
export interface BookTopic {
  id: string; title: string; level: string; order: number; intro: string; why: string; practice: string;
  minutes: number; readings: Reading[]; markdown?: string;
}

export function readModel(): ReaderModel {
  try { return localStorage.getItem(MODEL_KEY) === "livro" ? "livro" : "ereader"; } catch { return "ereader"; }
}

export function BookReader({ topic, onBack, onNext, nextTitle }: { topic: BookTopic; onBack: () => void; onNext?: () => void; nextTitle?: string }) {
  const [model, setModel] = useState<ReaderModel>(readModel);
  const [page, setPage] = useState(0);
  const [pages, setPages] = useState(1);
  const [stride, setStride] = useState(0);
  const frame = useRef<HTMLDivElement>(null);
  const flow = useRef<HTMLDivElement>(null);
  const perView = model === "livro" ? 2 : 1;

  const pick = (next: ReaderModel) => {
    setModel(next);
    // No livro aberto a leitura anda de par em par: a pagina da esquerda e sempre par
    if (next === "livro") setPage((p) => p - (p % 2));
    try { localStorage.setItem(MODEL_KEY, next); } catch { /* preferencia so desta maquina */ }
  };

  // Mede quantas paginas o texto ocupou (muda com o tamanho da janela e o modelo)
  const measure = useCallback(() => {
    const el = flow.current, box = frame.current;
    if (!el || !box) return;
    // Largura de uma pagina = (quadro - vaos) / paginas visiveis; o passo inclui o vao entre colunas
    const gap = parseFloat(getComputedStyle(el).columnGap) || 0;
    const width = (box.clientWidth - gap * (perView - 1)) / perView;
    el.style.columnWidth = `${width}px`;
    const step = width + gap;
    // Conta pelas colunas que existem de fato (largura rolavel do quadro); no livro aberto o total fecha num par
    const raw = Math.max(1, Math.round((box.scrollWidth + gap) / step));
    const total = perView === 2 ? raw + (raw % 2) : raw;
    setStride(step);
    setPages(total);
    setPage((p) => {
      const capped = Math.min(p, Math.max(0, total - perView));
      return capped - (capped % perView);
    });
  }, [perView]);
  useLayoutEffect(() => {
    measure();
    const observer = new ResizeObserver(measure);
    if (frame.current) observer.observe(frame.current);
    // A fonte serifada e as imagens chegam depois do primeiro layout e mudam o numero de paginas
    let alive = true;
    void document.fonts?.ready.then(() => { if (alive) measure(); });
    const late = window.setTimeout(measure, 600);
    return () => { alive = false; observer.disconnect(); window.clearTimeout(late); };
  }, [measure, topic.id]);
  useEffect(() => setPage(0), [topic.id]);
  // Mostra a pagina rolando o quadro (sem transform no texto)
  const shown = useRef(page);
  useLayoutEffect(() => {
    const box = frame.current;
    if (!box) return;
    box.scrollLeft = Math.round(page * stride);
    // Virada: a pagina nova entra com um esmaecer curto (so opacidade, sem mover camadas)
    if (shown.current !== page && !matchMedia("(prefers-reduced-motion: reduce)").matches
        && document.documentElement.dataset.motion !== "off") {
      box.animate?.([{ opacity: 0.25 }, { opacity: 1 }], { duration: 220, easing: "ease-out" });
    }
    shown.current = page;
  }, [page, stride]);

  const go = useCallback((delta: number) => setPage((p) => Math.max(0, Math.min(Math.max(0, pages - perView), p + delta * perView))), [pages, perView]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement || t?.isContentEditable) return;
      // Setas no seletor de modelo trocam o modelo (radiogroup); espaco/Enter num botao e o clique do botao
      if (t?.closest?.("[role=radiogroup], [role=tablist], [role=menu], [role=dialog]")) return;
      if ((e.key === " " || e.key === "Enter") && t?.closest?.("button, a")) return;
      if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") { e.preventDefault(); go(1); }
      else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); go(-1); }
      else if (e.key === "Home") { e.preventDefault(); setPage(0); }
      else if (e.key === "Escape") onBack();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, onBack]);

  const last = page + perView >= pages;
  const percent = Math.min(100, Math.round(((page + perView) / pages) * 100));

  return (
    <div className="book-room" data-model={model}>
      <header className="book-toolbar">
        <Button variant="ghost" size="compact" icon="arrow-left" onClick={onBack}>Biblioteca</Button>
        <span className="book-toolbar-title">{topic.title}</span>
        <Segmented label="Modelo do leitor" value={model} onValueChange={pick}
          options={[{ value: "ereader", label: "E-reader" }, { value: "livro", label: "Livro aberto" }]} />
      </header>

      <div className="book-stage">
        <button type="button" className="book-turn" data-side="prev" aria-label="Página anterior" disabled={page === 0} onClick={() => go(-1)} />
        <div className="book-object">
          <div ref={frame} className="book-frame">
            <div ref={flow} className="book-flow" lang="pt-BR">
              <section className="book-opening">
                <p className="book-kicker">Capítulo {topic.order} · {LEVEL_LABEL[topic.level] ?? topic.level}</p>
                <span className="book-ornament" aria-hidden>❦</span>
                <h1>{topic.title}</h1>
                <p className="book-lede">{topic.intro}</p>
                <p className="book-why"><strong>Por que importa.</strong> {topic.why}</p>
              </section>
              <Prose markdown={topic.markdown ?? ""} onLink={(h) => void openExternal(h)} />
              <h2>Pratique no app</h2>
              <p>{topic.practice}</p>
              <h2>Leituras e referências</h2>
              <ol className="book-refs">
                {topic.readings.map((r) => (
                  <li key={r.url}>
                    <strong>{r.title}</strong>. {[r.authors, r.venue, r.year].filter(Boolean).join(", ")}.{" "}
                    <a href={r.url} onClick={(e) => { e.preventDefault(); void openExternal(r.url); }}>{r.url.replace(/^https:\/\//, "")}</a>
                  </li>
                ))}
              </ol>
              <p className="book-end" aria-hidden>❧</p>
            </div>
          </div>
          <footer className="book-footer">
            {model === "ereader" ? (
              <>
                <span>{percent}%</span>
                <span className="book-meter" aria-hidden><i style={{ width: `${percent}%` }} /></span>
                <span>Página {page + 1} de {pages}</span>
              </>
            ) : (
              <>
                <span>{page + 1}</span>
                <span className="book-running">{topic.title}</span>
                <span>{Math.min(pages, page + 2)} · {percent}%</span>
              </>
            )}
          </footer>
        </div>
        <button type="button" className="book-turn" data-side="next" aria-label="Próxima página" disabled={last} onClick={() => go(1)} />
      </div>

      <p className="book-hint" aria-live="polite">
        {last && onNext ? <Button size="compact" icon="arrow-right" onClick={onNext}>Próximo livro: {nextTitle}</Button>
          : <>Use ← → ou clique nas bordas para virar a página · {topic.minutes} min de leitura</>}
      </p>
    </div>
  );
}
