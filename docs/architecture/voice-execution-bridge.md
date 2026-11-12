# Ponte voz ↔ execução — prompt de desenvolvimento (v1)

Contrato de trabalho para corrigir os incidentes do modo Conversa (GPT-Live delegando aos agentes)
e entregar a ponte em que a pessoa fala enquanto o app executa. Serve de prompt para quem
implementa e de critério de aceite.

## 1. Objetivo

Enquanto a pessoa conversa, a voz entrega cada pedido aos agentes de execução sem perder,
duplicar ou inventar nada; responde o andamento real; para, corrige e confirma por voz. Nenhum
efeito fora do computador (enviar, publicar, comprar, pagar, transferir, excluir, aceitar termos)
acontece sem confirmação explícita, e nunca acontece duas vezes por engano.

## 2. Incidentes que motivam (registros de tarefa, sessão, autorização; sem dados pessoais)

| # | O que houve | Causa raiz |
|---|---|---|
| I1 | "escrever 'Oi' na conversa" virou 5 mensagens enviadas a uma pessoa real | (a) o Maestro acrescentou "e enviar" ao plano; (b) digitar + Enter num campo cujo rótulo não dizia "mensagem" passou sem classificação; (c) a autorização estava em modo sombra; (d) "Isso, pode escrever" virou uma segunda tarefa igual; (e) o piloto viu o campo vazio (porque já tinha enviado) e reenviou |
| I2 | "verificar o estado do site" criou um projeto novo | pergunta de andamento foi tratada como pedido de criação |
| I3 | "abrir o projeto no VS Code" bateu no limite de ações | caminho digitado na janela de abrir pasta, em vez de abrir a pasta direto |
| I4 | depois de uma pergunta do agente, 5 pedidos seguidos viraram "resposta à pergunta" | a pergunta pendente captura qualquer fala que não comece com verbo + app conhecido, e não expira |
| I5 | conexão do GPT-Live caiu por tempo esgotado e não voltou | sem nova tentativa antes de cair para a voz local |

## 3. Regras inegociáveis

- **Autorização em código**, nunca no prompt. Modo `enforce` para efeitos externos.
- **Cada autorização vale uma vez**: repetir um efeito já tentado na mesma tarefa exige
  nova confirmação, em qualquer modo exceto `off`.
- **O plano não acrescenta efeito** que o pedido não fez (política POL-009).
- **Pedido igual ao que já roda ou está na fila não vira tarefa nova.**
- **Pergunta de andamento nunca executa nada**: responde com o registro de tarefas.
- **Confirmação é da pessoa**: botão Confirmar ou "confirmo" seguido do código exibido para
  aquela ação. Recusar, cancelar ou deixar expirar interrompe a execução antes do efeito.
- Sem regressão: testes, smoke, QML e gate verdes; sem dado pessoal em testes, docs ou commits.
- Sem custo de API nos testes (modelo e conexões simulados).

## 4. Desenho

```
fala ─► voz (GPT-Live) ─► app decide (understand)
           │                 ├─ andamento?  ─► task_status (ledger + fila) ─► resposta falada
           │                 ├─ repetido?   ─► "já está em andamento"
           │                 ├─ confirmação pendente? código válido ─► libera a ação em espera
           │                 └─ comando ─► fila ─► controller ─► Maestro (POL-009) ─► agentes
           │                                                      └─ pilotos ─► porta de efeito
           │                                                         (enforce + uma vez por tarefa)
           └◄── "precisa de você: confirma?" ◄── pendência do tipo confirmação
```

## 5. Entregas e aceite

| Entrega | Aceite (teste que falharia sem ela) |
|---|---|
| P0.1 Porta de efeito | digitar + Enter no navegador fora de busca/endereço = enviar; enforce bloqueia sem confirmação |
| P0.2 Uso único | segundo envio na mesma tarefa exige uma nova aprovação e um código diferente |
| P0.3 POL-009 | plano "escrever ... e enviar" para pedido "escrever" é reprovado e replanejado |
| P0.4 Confirmação falada | o código exibido libera só a ação pendente e "não" encerra sem executá-la |
| P0.5 Sem duplicata | o mesmo pedido falado duas vezes enquanto roda gera uma tarefa |
| P1.1 Andamento | "como está o site?" / "verificar o estado" não cria tarefa e cita a tarefa real |
| P1.2 Pendência | comando de navegação ("abre o VS", "trazer o VS Code para frente") não vira resposta; pendência expira |
| P1.3 VS Code | abrir projeto da conversa no VS Code em uma ação, sem diálogo |
| P1.4 Reconexão | tempo esgotado tenta reconectar uma vez antes da voz local |
| P2 Correção | "na verdade é X" com tarefa rodando para a atual e executa X |

## 6. Verificação

1. `tests/test_voice_bridge_incidents.py`: replay de I1–I5 com estado final checado
   (envios executados, tarefas criadas, pendência), não só o texto da resposta.
2. `scripts/check_release.py --code-only` com o ambiente do projeto.
3. Varredura de dados pessoais no diff.
