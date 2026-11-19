# Preparação para testes internos — 19/11/2026

## Escopo e estado

Revisão do estado local posterior à auditoria de 17/11, preservando as alterações de produto já existentes.
Objetivo: consolidar uma versão na `main` para testes internos autorizados. Não é certificação de produção.

## Correções desta rodada

- Preferências: gravação protegida por lock, arquivo temporário único e atualização apenas dos campos editados.
  Aparência, instruções dos agentes e Configurações usam `harnessPatch`, evitando sobrescrever outras telas.
- Interface Qt: recursos restritos ao pacote local, papéis de parede e WebSocket da própria execução.
  Conexões externas por imagem, requisição e outro WebSocket foram bloqueadas em uma prova sintética real.
  Navegação externa automática não abre o navegador; links HTTPS clicados continuam disponíveis.
- Conversas: dados salvos incompatíveis não quebram a lista; títulos e datas inválidos recebem tratamento.
  Conversas com identificador divergente ou turnos malformados não são reabertas.
- Preferências booleanas: texto como `"false"` é recusado na gravação, evitando conversão silenciosa para ligado.
- Cérebro: nomes reservados do Windows e nomes terminados em ponto são recusados.
- Propostas de código: caminhos absolutos e travessia de diretórios são recusados; identificadores únicos
  evitam colisões de propostas criadas no mesmo segundo.
- Dependências de testes da interface: Vitest atualizado para 4.1.12, compatível com o Vite instalado.
- Gate: inspeção de credenciais ampliada para fontes da interface e PowerShell. A suíte completa dispõe de
  até dez minutos; os demais passos mantêm cinco minutos. Uma execução passou em aproximadamente quatro
  minutos, enquanto uma repetição simultânea com outros testes havia atingido o limite anterior.

## Evidências verificadas

| Verificação | Resultado |
| --- | --- |
| Suíte Python | 579 testes aprovados |
| Interface | 59 testes aprovados; TypeScript e build aprovados |
| Build versionado | Carimbo de `ui/dist` atualizado e conferido |
| Dependências JavaScript | Auditoria sem vulnerabilidades conhecidas |
| Ambiente Python instalado | `pip-audit` sem vulnerabilidades conhecidas |
| Qt real | Oito seções navegáveis; retomada da conversa e preservação das preferências aprovadas |
| Fluidez observada | 119 quadros de `requestAnimationFrame` em cerca de dois segundos; não é benchmark universal |
| Bloco de Notas | Motor focou a janela de teste, digitou, salvou e o conteúdo foi conferido em disco |
| YouTube no navegador Windows | Abertura em perfil separado e leitura local de título, URL e texto aprovadas |
| Histórico | Recusa real de uma URL proibida registrada como falha, com erro e agente |
| Haiku real | Código sintético 4826 identificado em 4,08 s, uma chamada; custo estimado pelo app: US$ 0,000168 |
| Arquivos candidatos ao Git | Sem arquivos de estado pessoal ou nomes com caracteres de controle; padrões encontrados eram fixtures sintéticas de testes |

As provas de interface e desktop utilizaram dados e perfis separados. Capturas, relatórios de execução,
perfis de navegador, credenciais e repositórios descartáveis não entram no Git.
O catálogo removido de imagens e as mudanças visuais existentes foram preservados.

## Limites e pendências externas

- Claude Code: a CLI foi localizada na instalação do Claude Desktop, mas a consulta de autenticação
  retornou sessão não conectada. A proposta real foi interrompida antes de qualquer geração paga.
  Ainda falta repetir proposta, verificação, aplicação e reversão reais após o login. Os testes locais
  do ciclo de propostas passaram; não substituem essa prova com o provedor.
- Voz humana: microfone e transcrição local capturaram áudio. A frase reconhecida foi
  `Abra computadora.`; o sistema pediu esclarecimento e não executou. Isso comprova captura e recusa
  de uma tarefa não entendida, mas não aprova reconhecimento correto nem execução completa por voz.
  A prova isolada utilizou Whisper small com busca de largura 1; precisa ser comparada à configuração
  normal antes de atribuir o resultado ao produto. Conversação remota longa e interrupção permanecem
  sem validação humana completa.
- Playwright é opcional e não está instalado neste ambiente. Seu caminho legado informou indisponibilidade.
  A prova de navegação concluída utilizou a abertura atual no navegador Windows e leitura local.
- A falha histórica específica do YouTube não foi reproduzida a partir de dados pessoais. O teste atual
  confirma navegação e registro de erro controlado; não demonstra a causa daquele incidente antigo.
- Auditoria automatizada e testes de regressão não demonstram ausência de toda vulnerabilidade nem
  garantem desempenho em outros computadores, serviços, microfones e escalas de tela.

## Arquitetura e continuidade

Mantida a separação entre React, Bridge tipado, servidor local autenticado, Controller, planejamento
e políticas de execução em código. Novas preferências não ampliam permissões de ações. Dados de páginas,
notas e ferramentas continuam sem autoridade para alterar essas políticas.

Para a próxima validação: concluir a autenticação do agente externo, repetir a voz com a configuração
normal e medir reconhecimento, execução, interrupções e memória em uma conversa representativa.
