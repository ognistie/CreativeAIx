// Mapa de responsabilidades do código. A atividade ao vivo vem da telemetria do panorama.
const LAYERS = [
  { name: "Entrada e conversa", node: "stage:pedido", parts: "React, Qt, Bridge, voz e ChatAgent",
    detail: "Recebe texto e áudio, resolve referências da conversa e entrega respostas em streaming." },
  { name: "Planejamento", node: "MAESTRO", parts: "Maestro, perfis, atalhos e planos aprendidos",
    detail: "Escolhe responder, usar uma rota conhecida ou delegar um plano aos agentes." },
  { name: "Contexto e memória", node: "region:memory", parts: "Segundo Cérebro, Obsidian, sessão, dicionário e skills",
    detail: "Seleciona referências para a tarefa. Memória orienta decisões sem conceder permissões." },
  { name: "Modelos", node: "region:model", parts: "AIClient, registro de capacidades, adaptadores e orçamento",
    detail: "Envia as requisições permitidas para o modelo selecionado e acompanha o uso reportado." },
  { name: "Autorização e privacidade", node: "stage:politicas", parts: "Validador, políticas de efeito, escopo de arquivos e egress",
    detail: "Valida o plano e controla efeitos sensíveis e saída de dados." },
  { name: "Execução e ferramentas", node: "region:spine", parts: "RunContext, agenda, Desktop, Web, Code, Data, File, CLIs e MCP",
    detail: "Despacha ações permitidas e preserva dependências, limites e cancelamento." },
  { name: "Percepção", node: "region:perception", parts: "UI Automation, Vision, leitor e pilotos",
    detail: "Observa o ambiente, localiza alvos e fornece evidência para o executor." },
  { name: "Verificação e registro", node: "region:verify", parts: "Verificadores, ledger, histórico e observatório",
    detail: "Confere resultados, registra execução e mantém explícitos os efeitos incertos." },
  { name: "Pesquisa e evolução", node: "region:learning", parts: "Research Lab, RSI, planos aprendidos e memória científica",
    detail: "Compara variantes e registra resultados. Publicação experimental depende de decisão humana." },
] as const;

export function HarnessArchitecture({ onFocus }: { onFocus: (node: string) => void }) {
  return (
    <details className="hp-architecture">
      <summary>Arquitetura do harness</summary>
      <ul>
        {LAYERS.map(({ name, node, parts, detail }) => (
          <li key={node}>
            <button type="button" onClick={() => onFocus(node)}>{name}</button>
            <strong>{parts}</strong>
            <p>{detail}</p>
          </li>
        ))}
      </ul>
    </details>
  );
}
