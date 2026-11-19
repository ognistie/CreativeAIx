import { useEffect, useMemo, useState } from "react";
import { TopicArt } from "../components/art/TopicArt";
import { Button, Chip, EmptyState, Field, Icon, Skeleton } from "../components/ui";
import { core } from "../lib/host";
import { LEVEL_LABEL, lookFor } from "../lib/topics";
import { Page } from "./Page";
import { BookReader } from "./BookReader";

// Biblioteca: trilha de AI Engineering (core/library.py + core/library_texts/*.md, sem rede).
// A estante pede so o indice (libraryCatalog); o texto longo vem quando o livro abre (libraryTopic).
// Cada tema e um livro 3D (a lombada engrossa com o nivel) e abre num leitor paginado (BookReader).

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


const fmtDate = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" });
};

export function LibraryView({ openTopic }: { openTopic?: string } = {}) {
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("");
  const [items, setItems] = useState<Topic[] | null>(null);
  const [catalog, setCatalog] = useState<Topic[] | null>(null);
  const [verified, setVerified] = useState("");
  const [openId, setOpenId] = useState<string | null>(openTopic ?? null);

  useEffect(() => {
    let active = true;
    void core().call("libraryCatalog", "", "", "").then((result) => {
      if (!active) return;
      const reply = result as Reply;
      setCatalog(reply.items ?? []);
      setVerified(reply.verified_on ?? "");
    }).catch(() => { if (active) setCatalog([]); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!query && !level) return;
    setItems(null);
    let active = true;
    const timer = window.setTimeout(() => {
      void core().call("libraryCatalog", query, level, "").then((result) => {
        if (active) setItems((result as Reply).items ?? []);
      }).catch(() => { if (active) setItems([]); });
    }, 150);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [query, level]);

  const visible = query || level ? items : catalog;
  const byId = useMemo(() => new Map((catalog ?? []).map((t) => [t.id, t])), [catalog]);

  if (openId) return <BookOpen id={openId} byId={byId} onBack={() => setOpenId(null)} onOpen={setOpenId} />;

  return (
    <Page wide title="Biblioteca" subtitle="Dez temas de AI Engineering para ler em ordem. Cada um tem um texto longo, referências conferidas e prática no app.">
      <div className="mb-5 flex flex-wrap items-center gap-2">
        {LEVELS.map((x) => (
          <Chip key={x.v} selected={level === x.v} onClick={() => setLevel(x.v)}>
            {x.l}
          </Chip>
        ))}
        <Field value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar tema, termo, autor ou trecho" aria-label="Buscar na biblioteca" className="ml-auto h-8 w-72 text-sm" />
      </div>

      {!visible ? (
        <div className="editorial-shelf">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[420px] rounded-r4" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <EmptyState icon="search" title="Nenhum tema com essa busca">
          Tente outro termo ou tire o filtro de nível.
        </EmptyState>
      ) : (
        <ul className="book-shelf">
          {visible.map((t) => (
            <li key={t.id}>
              <Book topic={t} onOpen={() => setOpenId(t.id)} />
            </li>
          ))}
        </ul>
      )}
      {verified && <p className="mt-6 text-xs text-fg-subtle">Links e títulos das referências conferidos na fonte em {fmtDate(verified)}.</p>}
    </Page>
  );
}

/** Livro na estante: capa editorial, lombada com o titulo, borda das paginas e contracapa (CSS 3D).
 *  A espessura vem do nivel: iniciante fino, intermediario medio, avancado grosso. */
function Book({ topic, onOpen }: { topic: Topic; onOpen: () => void }) {
  const look = lookFor(topic.id);
  return (
    <>
      <button type="button" onClick={onOpen} className="book3d" data-level={topic.level} aria-label={`Abrir o livro ${topic.title}`}
        style={{ "--book-ink": look.deep } as React.CSSProperties}>
        <span className="book3d-shadow" aria-hidden />
        <span className="book3d-back" aria-hidden />
        <span className="book3d-pages" aria-hidden />
        <span className="book3d-spine" aria-hidden><em>{topic.title}</em></span>
        <span className="book3d-cover"><TopicCard topic={topic} /></span>
      </button>
      <span className="book3d-meta"><span>{LEVEL_LABEL[topic.level] ?? topic.level}</span><span>{topic.minutes} min · {topic.toc.length} capítulos</span></span>
    </>
  );
}

/** Capa: um plano editorial e um plano de arte, alternando papel e tinta. */
function TopicCard({ topic }: { topic: Topic }) {
  const look = lookFor(topic.id);
  return (
    <span className="editorial-cover" data-ink={topic.order % 2 === 0}
      style={{ "--book-ink": look.deep } as React.CSSProperties}>
      <span className="editorial-heading">
        <span className="editorial-meta"><Icon name={look.icon} size={14} /> {LEVEL_LABEL[topic.level] ?? topic.level}</span>
        <span className="editorial-title">{topic.title}</span>
        <span className="editorial-line"><span>{topic.minutes} min de leitura</span><span>Ler <Icon name="arrow-right" size={13} /></span></span>
      </span>
      <span className="editorial-plate"><TopicArt look={look} variant={topic.order % 2 === 0 ? "glass" : "dots"} className="editorial-figure" /></span>
    </span>
  );
}

/** Abre o livro: carrega o texto e entrega ao leitor paginado. */
function BookOpen({ id, byId, onBack, onOpen }: { id: string; byId: Map<string, Topic>; onBack: () => void; onOpen: (id: string) => void }) {
  const [topic, setTopic] = useState<Topic | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setTopic(null);
    setError("");
    core().call("libraryTopic", id)
      .then((r) => { const v = r as Reply; if (v.ok && v.topic) setTopic(v.topic); else setError(v.error || "Não deu para abrir o livro."); })
      .catch((e: Error) => setError(e.message));
  }, [id]);
  const next = useMemo(() => {
    const order = (byId.get(id)?.order ?? 0) + 1;
    return Array.from(byId.values()).find((t) => t.order === order) ?? null;
  }, [byId, id]);
  if (error) return <Page title="Biblioteca"><EmptyState icon="alert-circle" title="Livro indisponível" action={<Button onClick={onBack}>Voltar</Button>}>{error}</EmptyState></Page>;
  if (!topic) return <div className="p-8"><Skeleton className="mx-auto h-[70vh] max-w-[720px] rounded-r3" /></div>;
  return <BookReader topic={topic} onBack={onBack} onNext={next ? () => onOpen(next.id) : undefined} nextTitle={next?.title} />;
}
