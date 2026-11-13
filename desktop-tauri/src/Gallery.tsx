import { useEffect, useState } from "react";
import {
  AppDialog,
  AppMenu,
  Button,
  Chip,
  DialogClose,
  EmptyState,
  Field,
  GlassPanel,
  Hint,
  HintProvider,
  Icon,
  IconButton,
  Segmented,
  Skeleton,
  Spinner,
  StatusDot,
  TogglePill,
  type IconName,
} from "./components/ui";
import { applyAppearance } from "./lib/appearance";
import { ICONS } from "./lib/icons.gen";

// Galeria do design system (abrir com #galeria). Serve para revisar os componentes nos dois temas,
// nas paletas e nos tres estilos de canto, sem precisar do nucleo.

const PALETTES = ["abismo", "aurora", "ameixa", "brisa", "oceano", "matcha", "lavanda", "areia"] as const;

export function Gallery() {
  const [mode, setMode] = useState<"escuro" | "claro">("escuro");
  const [palette, setPalette] = useState<string>("abismo");
  const [radius, setRadius] = useState<"suave" | "reto" | "redondo">("suave");
  const [motion, setMotion] = useState(true);
  const [chip, setChip] = useState("todos");
  const [dialog, setDialog] = useState(false);

  useEffect(() => applyAppearance({ mode, palette, radius, motion }), [mode, palette, radius, motion]);

  return (
    <HintProvider>
      <div
        className="min-h-full p-8"
        style={{
          background:
            "radial-gradient(60% 50% at 15% 10%, var(--tone-1), transparent 70%), radial-gradient(50% 45% at 85% 20%, var(--tone-3), transparent 70%), radial-gradient(60% 50% at 50% 100%, var(--tone-2), transparent 70%), var(--bg-base)",
        }}
      >
        <header className="mx-auto mb-8 flex max-w-5xl flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.1em] text-fg-muted">Creative AIx · design system</p>
            <h1 className="font-display text-hero font-medium tracking-[-0.03em]">Componentes base</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              label="Tema"
              value={mode}
              onValueChange={setMode}
              options={[
                { value: "escuro", label: "Escuro" },
                { value: "claro", label: "Claro" },
              ]}
            />
            <Segmented
              label="Cantos"
              value={radius}
              onValueChange={setRadius}
              options={[
                { value: "suave", label: "Suave" },
                { value: "reto", label: "Reto" },
                { value: "redondo", label: "Redondo" },
              ]}
            />
            <TogglePill checked={motion} onCheckedChange={setMotion} icon="sparkle">
              Movimento
            </TogglePill>
          </div>
        </header>

        <main className="mx-auto grid max-w-5xl gap-5 md:grid-cols-2">
          <Section title="Paleta">
            <div className="flex flex-wrap gap-2">
              {PALETTES.map((p) => (
                <Chip key={p} selected={palette === p} onClick={() => setPalette(p)}>
                  {p}
                </Chip>
              ))}
            </div>
          </Section>

          <Section title="Botões">
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="primary" icon="play">
                Executar
              </Button>
              <Button icon="edit">Editar</Button>
              <Button variant="ghost">Cancelar</Button>
              <Button variant="danger" icon="stop">
                Parar
              </Button>
              <Button disabled>Indisponível</Button>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button size="compact" icon="plus">
                Nova nota
              </Button>
              <Hint text="Microfone">
                <IconButton icon="mic" label="Gravar voz" />
              </Hint>
              <IconButton icon="settings" label="Configurações" flat />
              <AppMenu
                trigger={<IconButton icon="more" label="Mais ações" />}
                items={[
                  { label: "Renomear", icon: "edit", onSelect: () => {} },
                  { label: "Abrir pasta", icon: "folder-open", onSelect: () => {} },
                  "separator",
                  { label: "Apagar conversa", icon: "x", danger: true, onSelect: () => setDialog(true) },
                ]}
              />
            </div>
          </Section>

          <Section title="Filtros e campos">
            <div className="mb-3 flex flex-wrap gap-2">
              {["todos", "concluídos", "com falha"].map((c) => (
                <Chip key={c} selected={chip === c} onClick={() => setChip(c)}>
                  {c}
                </Chip>
              ))}
              <Chip swatch="var(--accent)">destaque</Chip>
            </div>
            <Field placeholder="Pesquisar no cérebro…" aria-label="Pesquisar" />
          </Section>

          <Section title="Estado">
            <div className="flex flex-wrap items-center gap-4 text-sm text-fg-muted">
              {(["ok", "warn", "clarify", "cancelled", "failed"] as const).map((s) => (
                <span key={s} className="flex items-center gap-2">
                  <StatusDot status={s} /> {s}
                </span>
              ))}
              <span className="flex items-center gap-2">
                <Spinner /> carregando
              </span>
            </div>
            <div className="mt-4 space-y-2">
              <Skeleton className="h-3 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </Section>

          <Section title="Vazio">
            <EmptyState
              icon="history"
              title="Nenhuma execução ainda"
              action={
                <Button size="compact" variant="primary">
                  Fazer um pedido
                </Button>
              }
            >
              O que o agente fizer aparece aqui, com os passos e a evidência de cada um.
            </EmptyState>
          </Section>

          <Section title={`Ícones (${Object.keys(ICONS).length})`}>
            <div className="grid grid-cols-10 gap-3 text-fg-muted">
              {(Object.keys(ICONS) as IconName[]).map((n) => (
                <Hint key={n} text={n}>
                  <span tabIndex={0} className="grid place-items-center rounded-r1 py-1 hover:bg-hover hover:text-fg">
                    <Icon name={n} size={18} />
                  </span>
                </Hint>
              ))}
            </div>
          </Section>
        </main>

        <AppDialog
          open={dialog}
          onOpenChange={setDialog}
          title="Apagar esta conversa?"
          description="Os pedidos e as respostas somem da lista. O histórico de execuções continua."
          actions={
            <>
              <DialogClose asChild>
                <Button variant="ghost">Cancelar</Button>
              </DialogClose>
              <Button variant="danger" onClick={() => setDialog(false)}>
                Apagar
              </Button>
            </>
          }
        />
      </div>
    </HintProvider>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <GlassPanel className="p-5">
      <h2 className="mb-4 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">{title}</h2>
      {children}
    </GlassPanel>
  );
}
