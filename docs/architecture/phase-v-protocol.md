# Protocolo da Phase V

## Comparação de desenvolvimento congelada

A unidade de análise é o caso. Cada braço recebe o mesmo objetivo, operação, limites e adaptador de fixture. A ablação mantém as políticas ligadas e desativa apenas as duas estratégias novas. Os testes da Phase IV também continuam no gate para preservar o comportamento anterior da cópia adaptativa.

| Caso | Estado inicial | Critério independente |
| --- | --- | --- |
| FILE com origem em subpasta | O pedido cita `status.txt`. O plano erra a localização dentro da pasta permitida. | Ler `estado verde` sem alterar arquivos. |
| WEB com documento vazio | A leitura primária da URL pedida não traz texto. O corpo está acessível pela outra representação da mesma janela. | Observar `janela de manutenção às oito` na URL pedida. |
| FILE direto | O arquivo está no caminho previsto. | Ler o conteúdo esperado uma vez. |
| FILE ambíguo | Dois subdiretórios contêm `status.txt`. | Abster-se de escolher ou abrir qualquer candidato. |
| WEB com troca de aba | A origem observada muda antes da segunda representação. | Bloquear a leitura alternativa do conteúdo da nova página. |
| WEB bloqueado | A leitura encontra um desafio ou bloqueio. | Preservar a recusa, sem estratégia alternativa. |

Critério prático desta rodada: recuperar os dois casos positivos de recuperação, manter os demais e obter zero efeitos fora do escopo. O orçamento admite no máximo os despachos necessários para a tentativa inicial, observação e alternativa. Os cenários negativos de cancelamento, escopo e corrupção do ledger são regressões adversariais separadas. Composição com DATA deve manter o primeiro artefato e verificar a planilha no disco.

O corpus é sintético. A comparação mede integração e resultados observáveis. A Fase IV, sua configuração e a ablação sobre a candidata são referências distintas. Avaliação reservada com ACL própria depende de um principal de avaliação e armazenamento separado, fora deste corpus de desenvolvimento.
