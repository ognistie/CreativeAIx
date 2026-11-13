import { useEffect, useState } from "react";
import { core } from "../lib/tauri";
import { Button, Icon, type IconName } from "./ui";

// IntroCard.qml: "como usar" de cada tela. "Entendi" recolhe para uma pilula (lembrado entre aberturas,
// em <cerebro pessoal>/.cerebro/interface.json via introSeen/setIntroSeen).

export type IntroKey = "brain" | "you" | "harness" | "diary";

interface Intro {
  title: string;
  place: string;
  lead: string;
  steps: Array<[IconName, string, string]>;
}

export const INTROS: Record<IntroKey, Intro> = {
  brain: {
    title: "Seu segundo cérebro",
    place: "o Cérebro",
    lead: "Tudo o que os agentes sabem para fazer as suas tarefas, em notas que você lê e muda aqui. O que você muda fica na sua pasta pessoal; o original de fábrica continua guardado.",
    steps: [
      ["search", "Encontre", "Navegue pelas pastas ou busque com Ctrl+K. A busca ignora acentos."],
      ["edit", "Edite e ligue", "Abra uma nota e escreva. Use [[Nome da nota]] para ligar ideias; o modo Mapa mostra as ligações."],
      ["plus", "Crie e organize", "Nova nota, nova pasta, renomear (as ligações acompanham) e remover, com restauração."],
      ["sparkle", "Revise sugestões", "Quando uma tarefa falha ou dá certo, os agentes sugerem uma lição ou um caminho. Só vale depois que você aprova."],
    ],
  },
  harness: {
    title: "Ajuste como a plataforma trabalha",
    place: "o Harness",
    lead: "Aqui você muda o jeito dos agentes e a cara do app, sem mexer em código. As regras de segurança ficam no código e continuam valendo.",
    steps: [
      ["sparkle", "Descreva a mudança", "Escreva em uma frase o que quer mudar. O app mostra o antes e depois, e você aplica ou descarta."],
      ["sliders", "Ajuste cada agente", "Escolha um agente em Como os agentes trabalham, veja como ele está programado e escreva suas preferências."],
      ["palette", "Personalize", "Cor de destaque, paleta, luzes de fundo, cantos e as telas da barra lateral."],
      ["history", "Desfaça quando quiser", "Cada vez que você salva, a versão anterior fica em Versões."],
    ],
  },
  diary: {
    title: "Um caderno que o agente pode consultar, se você quiser",
    place: "o Diário",
    lead: "Escreva livremente. Algumas marcas viram contexto útil, extraído no seu computador.",
    steps: [
      ["alert-circle", "Prioridades", "Comece a linha com ! ou “Prioridade:”."],
      ["checklist", "Tarefas", "Use “- [ ] tarefa”; marque feita com “- [x]”."],
      ["list", "Tags", "Escreva #tag no texto para filtrar depois."],
      ["lock", "Privacidade", "Entrada privada nunca vai para a Conversa. Excluir apaga de vez."],
    ],
  },
  you: {
    title: "Seu perfil para os agentes",
    place: "a seção Você",
    lead: "Conte como você trabalha e fala. Os agentes leem isto antes de planejar e executar, e passam a fazer as coisas do seu jeito.",
    steps: [
      ["edit", "Escreva livremente", "Cada cartão é um assunto. Frases curtas funcionam melhor: um item por linha."],
      ["check", "Salva sozinho", "Ao parar de digitar, o texto é guardado na sua pasta pessoal, fora do repositório do projeto."],
      ["sparkle", "Vale na próxima tarefa", "O que você preencher vai junto com cada pedido para o modelo de IA (Maestro e agentes). Cartão vazio não vai."],
    ],
  },
};

let seenCache: Record<string, boolean> | null = null;

export function IntroCard({ which }: { which: IntroKey }) {
  const intro = INTROS[which];
  const [open, setOpen] = useState<boolean | null>(null);

  useEffect(() => {
    if (seenCache) {
      setOpen(!seenCache[which]);
      return;
    }
    core()
      .call("introSeen")
      .then((r) => {
        seenCache = (r && typeof r === "object" ? r : {}) as Record<string, boolean>;
        setOpen(!seenCache[which]);
      })
      .catch(() => setOpen(true));
  }, [which]);

  const set = (show: boolean) => {
    setOpen(show);
    seenCache = { ...(seenCache ?? {}), [which]: !show };
    void core().call("setIntroSeen", which, !show);
  };

  if (open === null) return null;
  if (!open) {
    return (
      <button type="button" onClick={() => set(true)} className="mb-5 inline-flex items-center gap-2 rounded-full bg-chip px-3 py-1.5 text-[13px] text-fg-muted hover:bg-row-hover hover:text-fg">
        <Icon name="help" size={13} /> Como usar {intro.place}
      </button>
    );
  }
  return (
    <section className="animate-enter mb-6 rounded-r4 border border-edge bg-glass p-5 backdrop-blur-xl" aria-label={`Como usar ${intro.place}`}>
      <div className="flex items-start gap-4">
        <div className="flex-1">
          <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">
            <span className="size-1.5 rounded-full bg-accent" /> Como usar
          </p>
          <h2 className="mt-1 font-display text-lg font-medium tracking-[-0.01em] text-fg">{intro.title}</h2>
          <p className="mt-1 max-w-2xl text-md text-fg-muted">{intro.lead}</p>
        </div>
        <Button size="compact" onClick={() => set(false)}>
          Entendi
        </Button>
      </div>
      <ol className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {intro.steps.map(([icon, t, d]) => (
          <li key={t} className="flex gap-2.5">
            <span className="grid size-7 shrink-0 place-items-center rounded-r2 bg-chip text-fg-muted">
              <Icon name={icon} size={14} />
            </span>
            <span>
              <span className="block text-sm font-medium text-fg">{t}</span>
              <span className="block text-sm text-fg-muted">{d}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
