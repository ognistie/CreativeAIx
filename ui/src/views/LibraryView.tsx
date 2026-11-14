import { useEffect, useMemo, useState } from "react";
import { Button, Chip, EmptyState, Field, GlassPanel, Icon, Skeleton } from "../components/ui";
import { core, openExternal } from "../lib/host";
import { Page } from "./Page";

// LibraryView.qml: trilha de temas de AI Engineering (conteudo estatico do core/library.py, sem rede).

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
  article?: Array<{ h: string; p: string[] }>;
}

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
  const [all, setAll] = useState<Topic[]>([]);
  const [verified, setVerified] = useState("");
  const [open, setOpen] = useState<Topic | null>(null);

  useEffect(() => {
    core()
      .call("librarySearch", "", "", "")
      .then((r) => {
        const items = (r as { items?: Topic[] }).items ?? [];
        setAll(items);
        const hit = openTopic && items.find((t) => t.id === openTopic);
        if (hit) setOpen(hit);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      core()
        .call("librarySearch", query, level, "")
        .then((r) => {
          const v = r as { items?: Topic[]; verified_on?: string };
          setItems(v.items ?? []);
          setVerified(v.verified_on ?? "");
        })
        .catch(() => setItems([]));
    }, 150);
    return () => clearTimeout(t);
  }, [query, level]);

  const byId = useMemo(() => new Map(all.map((t) => [t.id, t])), [all]);

  if (open) return <TopicView topic={open} byId={byId} verified={verified} onBack={() => setOpen(null)} onOpen={setOpen} />;

  return (
    <Page wide title="Biblioteca" subtitle="Temas de AI Engineering para ler em ordem, cada um com prática no app.">
      <div className="mb-5 flex flex-wrap items-center gap-2">
        {LEVELS.map((x) => (
          <Chip key={x.v} selected={level === x.v} onClick={() => setLevel(x.v)}>
            {x.l}
          </Chip>
        ))}
        <Field value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar tema, termo ou autor" aria-label="Buscar na biblioteca" className="ml-auto h-8 w-64 text-sm" />
      </div>
      {!items ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-44 rounded-r4" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon="search" title="Nenhum tema com essa busca">
          Tente outro termo ou tire o filtro de nível.
        </EmptyState>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((t) => (
            <li key={t.id}>
              <button type="button" onClick={() => setOpen(t)} className="press block h-full w-full text-left">
                <GlassPanel className="flex h-full flex-col p-5 transition-colors hover:border-hairline-hi">
                  <div className="mb-3 flex items-center gap-2">
                    <span className="grid size-7 place-items-center rounded-full bg-primary text-sm font-medium text-fg-inverse">{t.order}</span>
                    <span className="text-xs uppercase tracking-[0.08em] text-fg-muted">{t.level}</span>
                    {t.order === 1 && <span className="ml-auto rounded-full bg-accent/15 px-2 py-0.5 text-xs text-accent">comece aqui</span>}
                  </div>
                  <p className="font-display text-lg font-medium tracking-[-0.01em] text-fg">{t.title}</p>
                  <p className="mt-1.5 line-clamp-3 text-sm text-fg-muted">{t.intro}</p>
                  <p className="mt-auto pt-3 text-xs text-fg-subtle">{t.readings.length} leituras</p>
                </GlassPanel>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}

function TopicView({
  topic,
  byId,
  verified,
  onBack,
  onOpen,
}: {
  topic: Topic;
  byId: Map<string, Topic>;
  verified: string;
  onBack: () => void;
  onOpen: (t: Topic) => void;
}) {
  return (
    <div className="h-full overflow-y-auto px-8">
      <article className="mx-auto max-w-[var(--content-max)] select-text py-12">
        <Button variant="ghost" size="compact" icon="arrow-right" onClick={onBack} className="mb-6 [&_svg]:rotate-180">
          Biblioteca
        </Button>
        <p className="text-xs uppercase tracking-[0.1em] text-fg-muted">
          Tema {topic.order} · {topic.level}
        </p>
        <h1 className="mt-1 font-display text-[28px] font-medium tracking-[-0.03em] text-fg">{topic.title}</h1>
        {topic.prereqs.length > 0 && (
          <p className="mt-3 flex flex-wrap items-center gap-2 text-sm text-fg-muted">
            Antes, leia:
            {topic.prereqs.map((id) => {
              const t = byId.get(id);
              return t ? (
                <Chip key={id} onClick={() => onOpen(t)}>
                  {t.title}
                </Chip>
              ) : null;
            })}
          </p>
        )}
        <p className="mt-5 text-md leading-relaxed text-fg">{topic.intro}</p>

        <h2 className="mt-8 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">Por que importa</h2>
        <p className="mt-2 text-md leading-relaxed text-fg">{topic.why}</p>

        {(topic.article ?? []).map((sec) => (
          <section key={sec.h} className="mt-8">
            <h2 className="font-display text-xl font-medium tracking-[-0.01em] text-fg">{sec.h}</h2>
            {sec.p.map((p, i) => (
              <p key={i} className="mt-2.5 text-md leading-relaxed text-fg">
                {p}
              </p>
            ))}
          </section>
        ))}

        <GlassPanel className="mt-8 p-5" raised={false}>
          <h2 className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">
            <Icon name="sparkle" size={13} /> Pratique no app
          </h2>
          <p className="text-md leading-relaxed text-fg">{topic.practice}</p>
          {topic.terms.length > 0 && <p className="mt-3 text-sm text-fg-muted">Termos-chave: {topic.terms.join(" · ")}</p>}
          {topic.limits && <p className="mt-2 text-sm text-fg-subtle">{topic.limits}</p>}
        </GlassPanel>

        <h2 className="mt-10 font-display text-xl font-medium tracking-[-0.01em] text-fg">Leituras e referências</h2>
        <ul className="mt-3 space-y-3">
          {topic.readings.map((r) => (
            <li key={r.url} className="rounded-r3 border border-edge bg-glass p-4">
              <p className="text-md font-medium text-fg">{r.title}</p>
              <p className="mt-0.5 text-sm text-fg-muted">
                {[r.authors, r.venue, r.year].filter(Boolean).join(" · ")} · {r.kind}
              </p>
              {r.note && <p className="mt-1.5 text-sm text-fg">{r.note}</p>}
              <button type="button" onClick={() => void openExternal(r.url)} className="mt-1.5 flex items-center gap-1 break-all text-left text-xs text-accent hover:underline">
                <Icon name="external" size={11} /> {r.url.replace(/^https:\/\//, "")}
              </button>
            </li>
          ))}
        </ul>
        {verified && <p className="mt-4 text-xs text-fg-subtle">Links e títulos conferidos na fonte em {fmtDate(verified)}.</p>}
      </article>
    </div>
  );
}
