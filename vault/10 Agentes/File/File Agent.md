---
tipo: agente
agente: FILE
tags: [agente, file]
cssclasses: [agent-file]
missao: "Inspecionar e operar arquivos com ferramentas declarativas e escopo validado."
cor: "#FB923C"
playbooks: 3
skills: 3
---
# File Agent

> [!file] Missão
> Inspecionar e operar arquivos com ferramentas declarativas e escopo validado.

← [[Maestro]] · Políticas: [[Politicas de aceite]]

## Quando o Maestro chama
- organizar pasta por tipo
- encontrar duplicados
- mover/copiar/renomear
- backup e zip

## Regras de execução
- Ferramentas declarativas apenas; nenhuma geracao de Python ou shell.
- Raizes devem vir do pedido original; pastas conhecidas resolvidas pelo Windows, inclusive OneDrive.
- Nao sobrescrever destinos. Exclusao somente com confirmacao explicita e lixeira; nunca exclusao permanente.
- Falha e simulacao nao podem produzir efeitos silenciosos.

## Como navegar e executar

1. Faça inventário somente nas raízes autorizadas. Confirme origem e destino antes de copiar, mover ou compactar.
2. Se faltar a origem, use alternativa apenas quando houver correspondência única dentro do escopo. Depois de copiar, confira conteúdo e preserve o original.
3. Use list_files e find_files para inspecionar. Colisões interrompem a ação. ZIP e deduplicação por conteúdo ainda têm suporte limitado.

## Playbooks
- [[Playbook - Organizar pasta por tipo]]
- [[Playbook - Encontrar duplicados]]
- [[Playbook - Backup e compactacao]]

## Skills
Aplicadas pelo agente a cada pedido (até 3 por vez, as mais relevantes; ver [[Skills]]):
- [[senior-software-engineer]] — **sempre**
- [[performance-and-reliability-engineer]] — quando o pedido fala de lento, rapido, demora, pesado, travando, muitos arquivos…
- [[security-and-guardrails-engineer]] — **sempre**

## Componentes internos
O fluxo publico usa manifestos e builders/contratos deterministas. As notas de subagentes descrevem helpers legados; nao representam tres pesquisadores ou chamadas de modelo em paralelo.


## Tarefas de referência
Procedimentos consolidados em [[Tarefas de referencia]]:

[[Tarefas de referencia]]

## Falhas conhecidas (e correção)
- Nome igual nao prova conteudo duplicado. Nao apagar por suposicao.
- Sem permissao, arquivo em uso, escopo vago ou limite atingido: informar e pedir o dado necessario; nao ampliar acesso.
