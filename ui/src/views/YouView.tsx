import { useEffect, useRef, useState } from "react";
import { Button, Skeleton } from "../components/ui";
import { core } from "../lib/host";
import { IntroCard } from "../components/IntroCard";
import { Page } from "./Page";

// YouView.qml: secoes do perfil que vao junto dos pedidos. Salva sozinho (1 s depois de parar de digitar).

interface Section {
  name: string;
  hint: string;
  rel: string;
  text: string;
}

export function YouView({ onOpenBrain }: { onOpenBrain?: () => void }) {
  const [sections, setSections] = useState<Section[] | null>(null);
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
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <Page title="Você" subtitle="O que os agentes devem saber sobre você. Escreva do seu jeito: salva sozinho e vale para as próximas tarefas.">
      {error && <p className="mb-4 rounded-r2 bg-bad/10 p-3 text-sm text-bad">{error}</p>}
      <IntroCard which="you" />
      {!writable && <p className="mb-4 rounded-r2 bg-warn/10 p-3 text-sm text-fg">A pasta do seu cérebro não está disponível: dá para ler, mas não salvar.</p>}
      {!sections ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 rounded-r3" />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {sections.map((s) => (
            <SectionEditor key={s.name} section={s} disabled={!writable} />
          ))}
        </div>
      )}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-lg text-sm text-fg-subtle">
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

function SectionEditor({ section, disabled }: { section: Section; disabled: boolean }) {
  const [text, setText] = useState(section.text);
  const [state, setState] = useState<"" | "saving" | "saved" | "error">("");
  const saved = useRef(section.text);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  return (
    <label className="block rounded-r3 border border-edge bg-glass p-4">
      <span className="flex items-baseline justify-between gap-3">
        <span className="text-md font-medium text-fg">{section.name}</span>
        <span className="text-xs text-fg-subtle" aria-live="polite">
          {{ "": "", saving: "Salvando…", saved: "Salvo", error: "Não salvou" }[state]}
        </span>
      </span>
      <span className="mt-0.5 block text-sm text-fg-muted">{section.hint}</span>
      <textarea
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        rows={4}
        className="mt-3 w-full select-text resize-y rounded-r2 border border-hairline bg-surface p-3 text-md text-fg outline-none focus:border-accent/45 disabled:opacity-60"
      />
    </label>
  );
}
