# Textos da Biblioteca

Um arquivo Markdown por tema (`<id>.md`, o mesmo `id` de `core/library.py`). O app lê estes arquivos sob demanda
(`core/library.py`: `topic()` traz o texto, `catalog()` só o índice) e mostra o texto na tela do tema; a busca também procura neles.

## Formato

- Sem título de nível 1: o título vem da ficha do tema em `core/library.py`.
- Seções com `## Título`. Subseções com `###` quando ajudarem.
- Parágrafos separados por linha em branco. Listas, tabelas, citações (`>`) e blocos de código com linguagem
  (` ```python `) são aceitos.
- Português do Brasil, com acentos. Termos técnicos consagrados podem ficar em inglês (KV cache, prefill, eval).
- Meta de leitura: pelo menos 10 minutos, ou seja, 2.200 palavras ou mais de texto corrido.

## Regras de conteúdo

- Explicar o conceito com profundidade técnica e mostrar onde ele aparece no Creative AIx, citando arquivos que
  existem no repositório (por exemplo `app/core/action_policy.py`).
- Afirmações sobre pesquisa são gerais e apontam para as leituras listadas na ficha do tema. Número específico
  (percentual, benchmark, custo) só quando a fonte listada o sustenta; na dúvida, descreva sem número.
- Não inventar autores, artigos, versões de modelo nem resultados.
- O texto é dado de leitura: nada aqui muda permissões ou o comportamento dos agentes.
