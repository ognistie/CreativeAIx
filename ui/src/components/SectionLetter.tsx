import * as Dialog from "@radix-ui/react-dialog";
import type { Page } from "../App";
import { Button, IconButton } from "./ui";

const LETTERS: Record<Page, string[]> = {
  task: ["Escreva ou fale o que precisa. Acompanhe o plano, os passos e os arquivos gerados na conversa.", "Use /claude ou /codex na caixa de mensagem para trabalhar em uma pasta de projeto."],
  history: ["Reveja o resultado, as etapas e os arquivos de tarefas anteriores."],
  activity: ["Acompanhe a execução atual, pendências e o uso dos agentes ao longo do tempo."],
  brain: ["Clique em uma pasta no fim de um ramo para avançar. Use as setas para percorrer todos os ramos ou a busca para ir direto à nota.", "Use Mapa para ver ligações entre notas. Você pode editar sua própria cópia das notas de fábrica."],
  journal: ["Organize anotações por pasta. Escolha quais entradas podem servir de contexto para a conversa."],
  library: ["Abra uma capa para ler o tema, consultar referências e encontrar uma prática no app. Use a busca e os filtros para escolher por assunto ou nível."],
  lab: ["Percorra os quadros com as setas e clique em um quadro para abrir o editor do agente.", "Use o Explorador para ler arquivos e propor mudanças revisadas. Nas outras abas, ajuste instruções e memória ou compare versões."],
  settings: ["Em Geral, ajuste voz, confirmações, atalhos e integrações. Use Aparência para personalizar a interface.", "As opções de respostas, navegação e versões ficam aqui. Abra Sobre para conhecer o projeto."],
};

export function SectionLetter({ page, title }: { page: Page; title: string }) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <IconButton icon="help" label={`Como usar ${title}`} flat className="size-8" />
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="section-letter-overlay" />
        <Dialog.Content className="section-letter">
          <div className="section-letter-paper">
            <Dialog.Title>Como usar {title}</Dialog.Title>
            <Dialog.Description className="sr-only">Bilhete de apresentação da seção</Dialog.Description>
            {LETTERS[page].map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
          </div>
          <div className="section-letter-envelope">
            <Dialog.Close asChild><Button variant="primary">Entendi</Button></Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
