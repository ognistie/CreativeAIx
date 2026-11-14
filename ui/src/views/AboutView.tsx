import { GlassPanel, Icon } from "../components/ui";
import { openExternal } from "../lib/host";
import { Page } from "./Page";

// AboutView.qml
const STEPS = [
  { n: "1", t: "Entender", d: "O Maestro lê o pedido, pergunta se faltar algo e divide em etapas." },
  { n: "2", t: "Planejar", d: "Cada etapa vai para o agente especialista, que monta os passos." },
  { n: "3", t: "Executar", d: "Os passos rodam no seu computador e você acompanha em tempo real." },
];

const AGENTS = [
  { n: "Maestro", d: "Entende o pedido e distribui o trabalho" },
  { n: "Código", d: "Cria sites, scripts e sistemas completos" },
  { n: "Dados", d: "Monta planilhas Excel com fórmulas e gráficos" },
  { n: "Web", d: "Pesquisa e navega em sites" },
  { n: "Desktop", d: "Opera apps como Teams, Word e Bloco de Notas" },
  { n: "Arquivos", d: "Organiza, move e encontra arquivos" },
  { n: "Memória", d: "Lembra quais caminhos funcionaram, sem repetir conteúdo" },
];

const LINKS = [
  { l: "GitHub", u: "https://github.com/ognistie" },
  { l: "Portfólio", u: "https://ognistie.github.io/portfolio/" },
  { l: "LinkedIn", u: "https://www.linkedin.com/in/guilherme-moraes-franco-b4b1a0353/" },
];

export function AboutView() {
  return (
    <Page
      title="Creative AIx"
      subtitle="Você descreve o que precisa em linguagem natural e um time de agentes planeja, executa no seu computador e confere o resultado."
    >
      <h2 className="mb-3 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">Como funciona</h2>
      <div className="mb-8 grid gap-3 sm:grid-cols-3">
        {STEPS.map((s) => (
          <GlassPanel key={s.n} className="p-4" raised={false}>
            <span className="grid size-7 place-items-center rounded-full bg-chip text-sm font-medium text-fg">{s.n}</span>
            <p className="mt-3 text-md font-medium text-fg">{s.t}</p>
            <p className="mt-1 text-sm text-fg-muted">{s.d}</p>
          </GlassPanel>
        ))}
      </div>

      <h2 className="mb-3 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">Agentes</h2>
      <ul className="mb-2 overflow-hidden rounded-r3 border border-edge bg-glass">
        {AGENTS.map((a) => (
          <li key={a.n} className="flex gap-4 border-b border-hairline px-4 py-2.5 last:border-0">
            <span className="w-24 shrink-0 text-md font-medium text-fg">{a.n}</span>
            <span className="text-md text-fg-muted">{a.d}</span>
          </li>
        ))}
      </ul>
      <p className="mb-8 text-sm text-fg-subtle">Todos os agentes usam Claude Sonnet 5.</p>

      <h2 className="mb-3 text-xs font-medium uppercase tracking-[0.1em] text-fg-muted">Desenvolvido por</h2>
      <p className="text-md text-fg">Guilherme Moraes Franco</p>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {LINKS.map((l) => (
          <li key={l.l}>
            <button type="button" onClick={() => void openExternal(l.u)} className="flex items-center gap-1 text-accent hover:underline">
              <Icon name="external" size={12} /> {l.l}
            </button>
          </li>
        ))}
      </ul>
    </Page>
  );
}
