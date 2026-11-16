import { useEffect, useRef, useState } from "react";
import { IntroCard } from "../components/IntroCard";
import { ProgressRing } from "../components/ProgressRing";
import { Button, GlassPanel, Icon, Skeleton, type IconName } from "../components/ui";
import { cn } from "../lib/cn";
import { core } from "../lib/host";
import { Page } from "./Page";

// YouView: secoes do perfil que vao junto dos pedidos. Salva sozinho (1 s depois de parar de digitar).

interface Section {
  name: string;
  hint: string;
  rel: string;
  text: string;
}

const MAX = 700; // core/harness.py > YOU_MAX
const ICONS: Record<string, IconName> = {
  Perfil: "user",
  Rotinas: "calendar",
  "Tarefas frequentes": "checklist",
  "Jeito de falar": "messages",
  "Padrão de respostas": "file-text",
  "Skills para os agentes": "layers",
};

export function YouView({ onOpenBrain }: { onOpenBrain?: () => void }) {
  const [sections, setSections] = useState<Section[] | null>(null);
  const [filled, setFilled] = useState<Record<string, boolean>>({});
  const [writable, setWritable] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    core()
      .call("youProfile")
      .then((r) => {
        const v = r as { ok: boolean; writable?: boolean; sections?: Section[]; error?: string };
        if (!v.ok) setError(v.error || "Não deu para ler o perfil.");
        setWritable(v.writable !== false);
        setSections(v.sections ?? []);
        setFilled(Object.fromEntries((v.sections ?? []).map((s) => [s.name, !!s.text.trim()])));
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const total = sections?.length ?? 0;
  const done = Object.values(filled).filter(Boolean).length;

  return (
    <Page
      wide
      title="Você"
      subtitle="O que os agentes devem saber sobre você. Escreva do seu jeito: salva sozinho e vale para as próximas tarefas."
      actions={
        sections && total > 0 ? (
          <div className="flex items-center gap-3 rounded-full border border-edge bg-glass py-1.5 pl-1.5 pr-4 backdrop-blur-xl">
            <ProgressRing done={done} total={total} size={34} className="text-accent-ink" />
            <span className="text-sm text-fg">
              {done} de {total} preenchidos
            </span>
          </div>
        ) : undefined
      }
    >
      {error && <p className="mb-4 rounded-r2 bg-bad/10 p-3 text-sm text-bad-ink">{error}</p>}
      <IntroCard which="you" />
      {!writable && <p className="mb-4 rounded-r2 bg-warn/10 p-3 text-sm text-fg">A pasta do seu cérebro não está disponível: dá para ler, mas não salvar.</p>}
      {!sections ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 rounded-r4" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 [&>*]:min-w-0">
          {sections.map((s, i) => (
            <div key={s.name} className="animate-enter" style={{ animationDelay: `${i * 40}ms` }}>
              <SectionEditor section={s} disabled={!writable} onFilled={(f) => setFilled((x) => (x[s.name] === f ? x : { ...x, [s.name]: f }))} />
            </div>
          ))}
        </div>
      )}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <p className="flex max-w-xl items-start gap-2 text-sm text-fg-muted">
          <Icon name="shield-check" size={15} className="mt-0.5 shrink-0" />
          Guardado na pasta do seu cérebro e enviado junto com os pedidos ao modelo de IA. É preferência: não libera nada que os agentes não possam fazer.
        </p>
        {onOpenBrain && (
          <Button size="compact" icon="brain" onClick={onOpenBrain}>
            Abrir no Cérebro
          </Button>
        )}
      </div>
    </Page>
  );
}

function SectionEditor({ section, disabled, onFilled }: { section: Section; disabled: boolean; onFilled: (f: boolean) => void }) {
  const [text, setText] = useState(section.text);
  const [state, setState] = useState<"" | "saving" | "saved" | "error">("");
  const saved = useRef(section.text);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const id = `you-${section.name.replace(/\s+/g, "-")}`;

  useEffect(() => onFilled(!!text.trim()), [text, onFilled]);

  useEffect(() => {
    if (text === saved.current || disabled) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setState("saving");
      core()
        .call("youSave", section.name, text)
        .then((r) => {
          const ok = (r as { ok?: boolean }).ok !== false;
          if (ok) saved.current = text;
          setState(ok ? "saved" : "error");
        })
        .catch(() => setState("error"));
    }, 1000);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [text, section.name, disabled]);

  const has = !!text.trim();
  return (
    <GlassPanel className={cn("flex h-full flex-col p-4 transition-colors", has && "border-hairline-hi")}>
      <div className="flex items-start gap-3">
        <span className={cn("grid size-9 shrink-0 place-items-center rounded-r2", has ? "bg-accent/15 text-accent-ink" : "bg-chip text-fg-muted")}>
          <Icon name={ICONS[section.name] ?? "pen"} size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <label htmlFor={id} className="block text-md font-semibold text-fg">
            {section.name}
          </label>
          <p className="mt-0.5 text-sm text-fg-muted">{section.hint}</p>
        </div>
        <span className="shrink-0 pt-1 text-xs text-fg-muted" aria-live="polite">
          {state === "saving" ? "Salvando…" : state === "saved" ? "Salvo" : state === "error" ? <span className="text-bad-ink">Não salvou</span> : has ? "" : "Vazio"}
        </span>
      </div>
      <textarea
        id={id}
        value={text}
        maxLength={MAX}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        placeholder="Escreva aqui. Um item por linha funciona bem."
        className="mt-3 w-full flex-1 select-text resize-y rounded-r2 border border-hairline bg-surface p-3 text-md leading-relaxed text-fg outline-none placeholder:text-fg-subtle focus:border-accent/45 disabled:opacity-60"
      />
      <p className="mt-1.5 text-right text-xs tabular-nums text-fg-muted">
        {text.length}/{MAX}
      </p>
    </GlassPanel>
  );
}
