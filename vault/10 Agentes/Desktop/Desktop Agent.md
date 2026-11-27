---
tipo: agente
agente: DESKTOP
tags: [agente, desktop]
cssclasses: [agent-desktop]
missao: "Operar aplicativos do Windows: Bloco de Notas, Word, Excel, Teams, WhatsApp, Outlook, Paint, Calculadora, Spotify."
cor: "#FBBF24"
playbooks: 5
skills: 3
---
# Desktop Agent

> [!desktop] Missão
> Operar aplicativos do Windows: Bloco de Notas, Word, Excel, Teams, WhatsApp, Outlook, Paint, Calculadora, Spotify.

← [[Maestro]] · Políticas: [[Politicas de aceite]]

## Quando o Maestro chama
- abrir um aplicativo
- escrever texto em um app
- enviar mensagem por Teams/WhatsApp/Outlook
- utilitários (volume, print, minimizar)

## Regras de execução
- Confirmar janela e foco antes da entrada; perder o alvo exige parar. Login/CAPTCHA e efeitos externos exigem intervencao. Autorizacao universal por efeito ainda nao esta implementada; nao anunciar suporte autonomo seguro.
- Use a rotina pronta do app sempre que existir (custo zero, mais estável). LLM só para apps/ações sem rotina.
- Texto a digitar vem de `params.text`/`params.message`. Se o pedido é para escrever e o texto está vazio, NÃO abra o app vazio: o Maestro precisa gerar o conteúdo.
- Conteúdo ditado pelo usuário (entre aspas) é digitado exatamente como está.
- Mensagens para outras pessoas (Teams, WhatsApp, Outlook) são ações externas: só com destinatário e texto explícitos.
- Sempre `wait` 3–5s depois de abrir um app. Descrições de clique são DENTRO do app, nunca na barra de tarefas.
- Máximo 15 passos.

## Como navegar e executar

1. Identifique aplicativo, janela e documento. Prefira a rotina do aplicativo e controles de acessibilidade antes de recorrer à visão.
2. Confirme o documento após salvar. Se o foco mudar ou o resultado de um envio ficar incerto, pare e explique o que precisa ser conferido.
3. Para escrever em um documento novo, use blank_document e app_type(require_untitled). Para operar a janela identificada, use app_task.

## Playbooks
- [[Playbook - Bloco de Notas]]
- [[Playbook - Teams]]
- [[Playbook - WhatsApp]]
- [[Playbook - Word e Excel]]
- [[Playbook - Utilitarios do Windows]]

## Skills
Aplicadas pelo agente a cada pedido (até 3 por vez, as mais relevantes; ver [[Skills]]):
- [[ux-product-designer]] — **sempre**
- [[ai-agent-engineer]] — **sempre**
- [[performance-and-reliability-engineer]] — quando o pedido fala de lento, rapido, demora, pesado, travando, muitos arquivos…
- [[security-and-guardrails-engineer]] — quando o pedido fala de apaga, deleta, exclui, remove, limpa, envia…

## Falhas conhecidas (e correção)
- **Escreveu só o título da música** — o Maestro não gerou conteúdo e colocou o próprio pedido no texto. Agora a política [[POL-002]] reprova eco do pedido.
- **Clique por visão com baixa confiança** era contado como sucesso. Agora `⚠️` conta como falha.
- **Escreveu no documento do usuário** — o Bloco de Notas reabriu a aba existente. Agora `blank_document` + `require_untitled`.
- **Bloco de Notas não abria/escrevia** — dependia da janela da frente logo após abrir. Agora executável direto + janela pelo título.
- **Excel voltava para a tela inicial a cada pedido** — reabria o app. Agora app aberto na conversa não é reaberto.
- **"Clica em sistema" abria Cores** — "tema" dentro de "sis**tema**". Agora palavra inteira; pedido de clique sem passo que clique é reprovado ([[POL-007]]).

## Subagentes
Três ajudantes executam junto com o agente — entender, montar, conferir:
- **1 · Entender** — [[AppResolver]]: Identifica o aplicativo (apelidos incluidos) e se existe rotina pronta para ele.
- **2 · Montar** — [[ContentComposer]]: Prepara o texto a digitar: quebras de linha reais, espacos, limite de tamanho.
- **3 · Conferir** — [[ScreenGuard]]: Revisa os passos: espera apos abrir app, cliques nunca na barra de tarefas, limite de passos.

## Tarefas de referência
Procedimentos consolidados em [[Tarefas de referencia]]:

[[Tarefas de referencia]]
