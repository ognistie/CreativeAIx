import { useEffect, useState } from "react";
import { Button, GlassPanel, Icon, Skeleton } from "../components/ui";
import { core } from "../lib/host";
import { Page } from "./Page";

interface Section {
  name: string;
  hint: string;
  text: string;
}

const MAX = 700; // core/harness.py > YOU_MAX
const WORK_FIELDS: Record<string, { label: string; hint: string }> = {
  Perfil: { label: "Contexto de trabalho", hint: "Inclua o contexto e as ferramentas que ajudam os agentes a preparar suas entregas." },
  "Jeito de falar": { label: "Termos e apelidos", hint: "Explique os nomes e atalhos que usa nos pedidos." },
  "Skills para os agentes": { label: "Convenções e revisão", hint: "Registre os cuidados, formatos de entrega e pontos de revisão que importam no seu trabalho." },
};

export function YouView({ onBack, onOpenBrain }: { onBack: () => void; onOpenBrain?: () => void }) {
  const [sections, setSections] = useState<Section[] | null>(null);
  const [writable, setWritable] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void core().call("youProfile").then((r) => {
      const profile = r as { ok: boolean; writable?: boolean; sections?: Section[]; error?: string };
      if (!profile.ok) {
        setError(profile.error || "Não deu para ler o perfil.");
        return;
      }
      setWritable(profile.writable !== false);
      setSections(profile.sections ?? []);
    }).catch((e: Error) => setError(e.message));
  }, []);

  const previous = sections?.filter((s) => !WORK_FIELDS[s.name] && s.text.trim()) ?? [];
  return (
    <Page wide title="Como trabalhar comigo"
      subtitle="Preferências que ajudam os agentes a entender seus pedidos e preparar entregas."
      actions={<Button size="compact" icon="arrow-left" onClick={onBack}>Diário</Button>}>
      {error ? <p role="alert" className="rounded-r2 bg-bad/10 p-3 text-sm text-bad-ink">{error}</p>
        : !sections ? <Skeleton className="h-48 rounded-r4" />
        : <>
          {!writable && <p className="mb-4 text-sm text-fg-muted">A pasta pessoal está indisponível para salvar.</p>}
          <div className="grid gap-4 xl:grid-cols-3">
            {sections.filter((s) => WORK_FIELDS[s.name]).map((s) => (
              <SectionEditor key={s.name} section={s} disabled={!writable} />
            ))}
          </div>
          {previous.length > 0 && (
            <details className="mt-5 rounded-r3 border border-hairline bg-surface p-4">
              <summary className="cursor-pointer text-sm font-medium text-fg">Dados do perfil anterior</summary>
              <dl className="mt-3 space-y-3">
                {previous.map((s) => (
                  <div key={s.name}>
                    <dt className="text-sm font-medium text-fg">{s.name}</dt>
                    <dd className="mt-1 whitespace-pre-wrap break-words text-sm text-fg-muted">{s.text}</dd>
                  </div>
                ))}
              </dl>
              {onOpenBrain && <Button className="mt-3" size="compact" icon="brain" onClick={onOpenBrain}>Abrir no Cérebro</Button>}
            </details>
          )}
          <p className="mt-5 flex max-w-2xl items-start gap-2 text-sm text-fg-muted">
            <Icon name="shield-check" size={15} className="mt-0.5 shrink-0" />
            O perfil fica na sua pasta pessoal. Trechos salvos, inclusive do perfil anterior, podem acompanhar pedidos
            enviados ao modelo, sujeitos às regras de execução. O compartilhamento das entradas do Diário tem um controle próprio.
          </p>
        </>}
    </Page>
  );
}

function SectionEditor({ section, disabled }: { section: Section; disabled: boolean }) {
  const [text, setText] = useState(section.text);
  const [saved, setSaved] = useState(section.text);
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const id = `you-${section.name.replace(/\s+/g, "-")}`;
  const field = WORK_FIELDS[section.name]!;
  const save = async () => {
    setState("saving");
    try {
      const result = await core().call("youSave", section.name, text) as { ok: boolean };
      if (!result.ok) return setState("error");
      setSaved(text);
      setState("saved");
    } catch {
      setState("error");
    }
  };
  return (
    <GlassPanel className="flex flex-col p-4">
      <label htmlFor={id} className="text-md font-semibold text-fg">{field.label}</label>
      <p id={`${id}-hint`} className="mt-1 text-sm text-fg-muted">{field.hint}</p>
      <textarea id={id} aria-describedby={`${id}-hint`} value={text} maxLength={MAX} rows={5}
        disabled={disabled || state === "saving"}
        onChange={(e) => { setText(e.target.value); setState("idle"); }}
        className="mt-3 w-full flex-1 select-text resize-y rounded-r2 border border-hairline bg-surface p-3 text-md leading-relaxed text-fg outline-none focus:border-accent/45" />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p aria-live="polite" className="text-xs text-fg-muted">
          {state === "error" ? "Falha ao salvar. Tente novamente." : state === "saved" ? "Salvo" : `${text.length}/${MAX}`}
        </p>
        <Button size="compact" disabled={disabled || state === "saving" || text === saved} onClick={() => void save()}>
          {state === "saving" ? "Salvando…" : "Salvar"}
        </Button>
      </div>
    </GlassPanel>
  );
}
