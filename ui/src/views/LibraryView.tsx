import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { TopicArt } from "../components/art/TopicArt";
import { Carousel3D } from "../components/Carousel3D";
import { Prose } from "../components/Prose";
import { Button, Chip, EmptyState, Field, GlassPanel, Icon, Skeleton } from "../components/ui";
import { cn } from "../lib/cn";
import { core, openExternal } from "../lib/host";
import { slug } from "../lib/slug";
import { LEVEL_LABEL, lookFor } from "../lib/topics";
import { Page } from "./Page";

// Biblioteca: trilha de AI Engineering (core/library.py + core/library_texts/*.md, sem rede).
// A grade pede so o indice (libraryCatalog); o texto longo vem quando o tema abre (libraryTopic).

interface Reading {
  title: string;
  authors: string;
  year: number;
  url: string;
  kind: string;
  venue: string;
  note: string;
}

interface Topic {
  id: string;
  title: string;
  level: string;
  order: number;
  intro: string;
  why: string;
  prereqs: string[];
  readings: Reading[];
  practice: string;
  terms: string[];
  limits: string;
  minutes: number;
  toc: string[];
  markdown?: string;
}

type Reply = { ok?: boolean; items?: Topic[]; topic?: Topic; verified_on?: string; error?: string };

const LEVELS = [
  { v: "", l: "Todos" },
  { v: "iniciante", l: "Iniciante" },
  { v: "intermediario", l: "Intermediário" },
  { v: "avancado", l: "Avançado" },
];

const KIND_LABEL: Record<string, string> = { documentacao: "Documentação", pesquisa: "Pesquisa", preprint: "Preprint", didatico: "Didático" };

const fmtDate = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" });
};
const two = (n: number) => String(n).padStart(2, "0");

export function LibraryView({ openTopic }: { openTopic?: string } = {}) {
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("");
  const [items, setItems] = useState<Topic[] | null>(null);
  const [all, setAll] = useState<Topic[]>([]);
  const [verified, setVerified] = useState("");
  const [openId, setOpenId] = useState<string | null>(openTopic ?? null);

  useEffect(() => {
    void core()
      .call("libraryCatalog", "", "", "")
      .then((r) => setAll((r as Reply).items ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      core()
        .call("libraryCatalog", query, level, "")
        .then((r) => {
          const v = r as Reply;
          setItems(v.items ?? []);
          setVerified(v.verified_on ?? "");
        })
        .catch(() => setItems([]));
    }, 150);
    return () => clearTimeout(t);
  }, [query, level]);

  const byId = useMemo(() => new Map(all.map((t) => [t.id, t])), [all]);
  const filtering = !!query || !!level;

  if (openId) return <TopicReader id={openId} byId={byId} onBack={() => setOpenId(null)} onOpen={setOpenId} />;

  return (
    <Page wide title="Biblioteca" subtitle="Dez temas de AI Engineering para ler em ordem. Cada um tem um texto longo, referências conferidas e prática no app.">
      {!filtering && all.length > 0 && (
        <section aria-label="Trilha" className="-mx-8 mb-6">
          <p className="photo-label mx-8 mb-1 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">Trilha · comece pelo centro</p>
          <Carousel3D label="Trilha de temas">
            {all.map((t) => (
              <TrailCard key={t.id} topic={t} onOpen={() => setOpenId(t.id)} />
            ))}
          </Carousel3D>
        </section>
      )}

      <div className="mb-5 flex flex-wrap items-center gap-2">
        {LEVELS.map((x) => (
          <Chip key={x.v} selected={level === x.v} onClick={() => setLevel(x.v)}>
            {x.l}
          </Chip>
        ))}
        <Field value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar tema, termo, autor ou trecho" aria-label="Buscar na biblioteca" className="ml-auto h-8 w-72 text-sm" />
      </div>

      {!items ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[420px] rounded-r4" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon="search" title="Nenhum tema com essa busca">
          Tente outro termo ou tire o filtro de nível.
        </EmptyState>
      ) : (
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((t, i) => (
            <li key={t.id} className="animate-enter" style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}>
              <TopicCard topic={t} onOpen={() => setOpenId(t.id)} />
            </li>
          ))}
        </ul>
      )}
      {verified && <p className="mt-6 text-xs text-fg-subtle">Links e títulos das referências conferidos na fonte em {fmtDate(verified)}.</p>}
    </Page>
  );
}

/** Card do carrossel (vidro com gradiente vivo; texto sobre veu escuro para manter contraste). */
function TrailCard({ topic, onOpen }: { topic: Topic; onOpen: () => void }) {
  const look = lookFor(topic.id);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="trail-card group relative block h-[360px] w-[280px] overflow-hidden rounded-[22px] text-left text-white shadow-[0_24px_60px_-20px_rgb(0_0_0/0.55)] outline-offset-4"
    >
      <TopicArt look={look} variant="glass" className="absolute inset-0 size-full transition-transform duration-700 ease-out group-hover:scale-[1.06]" />
      <span aria-hidden className="absolute inset-0 bg-[linear-gradient(to_bottom,rgb(0_0_0/0.5),transparent_38%,transparent_55%,rgb(0_0_0/0.62))]" />
      <span className="absolute inset-x-5 top-5">
        <span className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.12em] text-white/90">
          <Icon name={look.icon} size={14} /> Tema {two(topic.order)}
        </span>
        <span className="mt-2 block font-display text-[22px] font-semibold leading-tight tracking-[-0.02em]">{topic.title}</span>
        <span className="mt-1 block text-sm text-white/85">{LEVEL_LABEL[topic.level] ?? topic.level}</span>
      </span>
      <span className="absolute inset-x-5 bottom-5 flex items-center justify-between text-sm">
        <span className="flex items-center gap-1.5 text-white/90">
          <Icon name="clock-read" size={14} /> {topic.minutes} min · {topic.readings.length} leituras
        </span>
        <span className="flex items-center gap-1 rounded-full bg-white/20 px-3 py-1 font-medium backdrop-blur-md transition-colors group-hover:bg-white/30">
          Ler <Icon name="arrow-right" size={13} />
        </span>
      </span>
    </button>
  );
}

/** Card da grade (arte pontilhada em cima, rodape solido na cor do tema). */
function TopicCard({ topic, onOpen }: { topic: Topic; onOpen: () => void }) {
  const look = lookFor(topic.id);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="topic-card group flex h-full w-full flex-col overflow-hidden rounded-r4 border border-edge text-left shadow-[0_1px_2px_var(--shadow-soft),0_10px_30px_var(--shadow-soft)] transition-[transform,box-shadow] duration-300 ease-out hover:-translate-y-1 hover:shadow-[0_18px_40px_-12px_rgb(0_0_0/0.35)]"
    >
      <span className="relative block aspect-[4/3] overflow-hidden">
        <TopicArt look={look} className="size-full" />
        <span className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-[var(--art-chip)] px-2.5 py-1 text-xs font-medium text-[var(--art-chip-ink)] backdrop-blur-md">
          <Icon name={look.icon} size={13} /> {two(topic.order)}
        </span>
        {topic.order === 1 && <span className="absolute right-3 top-3 rounded-full bg-[var(--art-chip)] px-2.5 py-1 text-xs font-medium text-[var(--art-chip-ink)]">comece aqui</span>}
      </span>
      <span className="flex flex-1 flex-col p-5 text-white" style={{ background: look.deep }}>
        <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-white/85">{LEVEL_LABEL[topic.level] ?? topic.level}</span>
        <span className="mt-1.5 font-display text-[19px] font-semibold leading-snug tracking-[-0.015em]">{topic.title}</span>
        <span className="mt-2 line-clamp-3 text-sm leading-relaxed text-white/90">{topic.intro}</span>
        <span className="mt-auto flex items-center justify-between pt-4 text-xs text-white/90">
          <span className="flex items-center gap-1.5">
            <Icon name="clock-read" size={13} /> {topic.minutes} min de leitura
          </span>
          <span className="flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 font-medium transition-colors group-hover:bg-white/25">
            Abrir <Icon name="arrow-right" size={12} />
          </span>
        </span>
      </span>
    </button>
  );
}

/** Leitor: capa em selo, indice com a secao atual, barra de progresso e referencias. */
function TopicReader({ id, byId, onBack, onOpen }: { id: string; byId: Map<string, Topic>; onBack: () => void; onOpen: (id: string) => void }) {
  const [topic, setTopic] = useState<Topic | null>(null);
  const [verified, setVerified] = useState("");
  const [error, setError] = useState("");
  const [active, setActive] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTopic(null);
    setError("");
    scroller.current?.scrollTo({ top: 0 });
    core()
      .call("libraryTopic", id)
      .then((r) => {
        const v = r as Reply;
        if (v.ok && v.topic) (setTopic(v.topic), setVerified(v.verified_on ?? ""));
        else setError(v.error || "Não deu para abrir o tema.");
      })
      .catch((e: Error) => setError(e.message));
  }, [id]);

  // Progresso e secao atual: um listener de rolagem com rAF, sem re-render a cada pixel
  const onScroll = useCallback(() => {
    const el = scroller.current;
    if (!el) return;
    const max = el.scrollHeight - el.clientHeight;
    if (bar.current) bar.current.style.transform = `scaleX(${max > 0 ? el.scrollTop / max : 0})`;
    const heads = Array.from(el.querySelectorAll<HTMLElement>(".prose h2[id]"));
    let cur = heads[0]?.id ?? "";
    for (const h of heads) if (h.getBoundingClientRect().top < 160) cur = h.id;
    setActive((a) => (a === cur ? a : cur));
  }, []);
  const raf = useRef(0);
  const scheduled = () => {
    if (!raf.current) raf.current = requestAnimationFrame(() => ((raf.current = 0), onScroll()));
  };
  useEffect(() => () => cancelAnimationFrame(raf.current), []);

  const look = lookFor(id);
  const next = useMemo(() => {
    const order = (byId.get(id)?.order ?? 0) + 1;
    return Array.from(byId.values()).find((t) => t.order === order) ?? null;
  }, [byId, id]);

  const jump = (h: string) => scroller.current?.querySelector(`#${CSS.escape(slug(h))}`)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div ref={scroller} onScroll={scheduled} className="relative h-full overflow-y-auto px-8">
      <div aria-hidden className="sticky top-0 z-10 -mx-8 h-[3px] bg-transparent">
        <div ref={bar} className="h-full origin-left scale-x-0 bg-accent" />
      </div>
      <div className="mx-auto max-w-6xl py-8">
        <Button variant="ghost" size="compact" icon="arrow-left" onClick={onBack} className="mb-6">
          Biblioteca
        </Button>

        {error ? (
          <EmptyState icon="alert-circle" title="Tema indisponível">
            {error}
          </EmptyState>
        ) : !topic ? (
          <div className="grid gap-6 lg:grid-cols-[1fr_220px]">
            <Skeleton className="h-72 rounded-r4" />
            <Skeleton className="h-40 rounded-r3" />
          </div>
        ) : (
          <>
            <header className="animate-enter grid items-center gap-8 md:grid-cols-[240px_1fr]">
              <div className="stamp mx-auto w-[220px] rotate-[-2.5deg] md:mx-0">
                <div className="relative aspect-[3/4] overflow-hidden">
                  <TopicArt look={look} variant="glass" className="absolute inset-0 size-full" />
                  <span aria-hidden className="absolute inset-0 bg-[linear-gradient(to_bottom,rgb(0_0_0/0.55),transparent_32%,transparent_70%,rgb(0_0_0/0.35))]" />
                  <span className="absolute inset-x-3 top-3 flex items-start justify-between font-display text-white">
                    <span className="text-[26px] font-medium leading-none tracking-[-0.02em] [text-shadow:0_1px_8px_rgb(0_0_0/0.35)]">{two(topic.order)}</span>
                    <span className="text-right font-mono text-[10px] uppercase leading-tight tracking-[0.1em] [text-shadow:0_1px_6px_rgb(0_0_0/0.4)]">
                      tema/
                      <br />
                      {LEVEL_LABEL[topic.level]}
                    </span>
                  </span>
                  <span className="absolute bottom-3 left-3 grid size-9 place-items-center rounded-full bg-black/30 text-white backdrop-blur-md">
                    <Icon name={look.icon} size={18} />
                  </span>
                </div>
              </div>
              <div>
                {verified && (
                  <p className="mb-3 inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.08em]">
                    <span className="rounded-[4px] bg-primary px-2 py-0.5 text-fg-inverse">AIX-{two(topic.order)}</span>
                    <span className="flex items-center gap-1 rounded-[4px] border border-hairline-hi px-2 py-0.5 text-fg-muted">
                      <Icon name="verified" size={12} className="text-ok-ink" /> fontes conferidas · {fmtDate(verified)}
                    </span>
                  </p>
                )}
                <h1 className="font-display text-[34px] font-semibold leading-[1.1] tracking-[-0.03em] text-fg">{topic.title}</h1>
                <p className="mt-3 max-w-2xl text-lg leading-relaxed text-fg-muted">{topic.intro}</p>
                <p className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fg-muted">
                  <span className="flex items-center gap-1.5">
                    <Icon name="clock-read" size={14} /> {topic.minutes} min de leitura
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Icon name="book" size={14} /> {topic.readings.length} referências
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Icon name="toc" size={14} /> {topic.toc.length} seções
                  </span>
                </p>
                {topic.prereqs.length > 0 && (
                  <p className="mt-4 flex flex-wrap items-center gap-2 text-sm text-fg-muted">
                    Antes, leia:
                    {topic.prereqs.map((p) => {
                      const t = byId.get(p);
                      return t ? (
                        <Chip key={p} icon={lookFor(p).icon} onClick={() => onOpen(p)}>
                          {t.title}
                        </Chip>
                      ) : null;
                    })}
                  </p>
                )}
              </div>
            </header>

            <div className="mt-12 grid gap-10 lg:grid-cols-[minmax(0,1fr)_220px]">
              <article className="min-w-0 max-w-[720px]">
                <GlassPanel raised={false} className="mb-8 p-5">
                  <p className="mb-1.5 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">Por que importa</p>
                  <p className="text-md leading-relaxed text-fg">{topic.why}</p>
                </GlassPanel>

                <Prose markdown={topic.markdown ?? ""} onLink={(h) => void openExternal(h)} />

                <GlassPanel className="mt-10 p-5" raised={false}>
                  <h2 className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">
                    <Icon name="sparkle" size={13} /> Pratique no app
                  </h2>
                  <p className="text-md leading-relaxed text-fg">{topic.practice}</p>
                  {topic.terms.length > 0 && (
                    <p className="mt-3 flex flex-wrap gap-1.5">
                      {topic.terms.map((t) => (
                        <span key={t} className="rounded-full bg-chip px-2.5 py-0.5 text-xs text-fg-muted">
                          {t}
                        </span>
                      ))}
                    </p>
                  )}
                  {topic.limits && <p className="mt-3 text-sm text-fg-muted">{topic.limits}</p>}
                </GlassPanel>

                <h2 className="mt-12 font-display text-xl font-semibold tracking-[-0.01em] text-fg">Leituras e referências</h2>
                <ol className="mt-4 space-y-3">
                  {topic.readings.map((r, i) => (
                    <li key={r.url}>
                      <button
                        type="button"
                        onClick={() => void openExternal(r.url)}
                        className="group flex w-full gap-4 rounded-r3 border border-edge bg-glass p-4 text-left transition-colors hover:border-hairline-hi"
                      >
                        <span className="font-mono text-sm text-fg-subtle">{two(i + 1)}</span>
                        <span className="min-w-0 flex-1">
                          <span className="flex items-start justify-between gap-3">
                            <span className="text-md font-medium text-fg">{r.title}</span>
                            <span className="shrink-0 rounded-full bg-chip px-2 py-0.5 text-[11px] text-fg-muted">{KIND_LABEL[r.kind] ?? r.kind}</span>
                          </span>
                          <span className="mt-0.5 block text-sm text-fg-muted">{[r.authors, r.venue, r.year].filter(Boolean).join(" · ")}</span>
                          {r.note && <span className="mt-1.5 block text-sm text-fg">{r.note}</span>}
                          <span className="mt-1.5 flex items-center gap-1 break-all text-xs text-accent-ink group-hover:underline">
                            <Icon name="external" size={11} /> {r.url.replace(/^https:\/\//, "")}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ol>

                {next && (
                  <button type="button" onClick={() => onOpen(next.id)} className="group mt-12 flex w-full items-center gap-5 overflow-hidden rounded-r4 border border-edge bg-glass p-3 text-left transition-colors hover:border-hairline-hi">
                    <span className="relative h-20 w-28 shrink-0 overflow-hidden rounded-r2">
                      <TopicArt look={lookFor(next.id)} variant="glass" className="absolute inset-0 size-full" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="text-xs uppercase tracking-[0.1em] text-fg-muted">Próximo tema · {two(next.order)}</span>
                      <span className="mt-0.5 block font-display text-lg font-semibold text-fg">{next.title}</span>
                      <span className="text-sm text-fg-muted">{next.minutes} min de leitura</span>
                    </span>
                    <Icon name="arrow-right" size={18} className="mr-3 text-fg-muted transition-transform group-hover:translate-x-1" />
                  </button>
                )}
              </article>

              <nav aria-label="Nesta página" className="hidden lg:block">
                <div className="sticky top-6">
                  <p className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">
                    <Icon name="toc" size={13} /> Nesta página
                  </p>
                  <ul className="space-y-0.5 border-l border-hairline">
                    {topic.toc.map((h) => {
                      const on = active === slug(h);
                      return (
                        <li key={h}>
                          <button
                            type="button"
                            onClick={() => jump(h)}
                            aria-current={on ? "location" : undefined}
                            className={cn(
                              "-ml-px block w-full border-l-2 py-1 pl-3 text-left text-sm transition-colors",
                              on ? "border-accent font-medium text-fg" : "border-transparent text-fg-muted hover:text-fg",
                            )}
                          >
                            {h}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </nav>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
