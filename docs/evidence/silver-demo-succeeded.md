# Primeira execução Silver concluída

Fonte: JSON da última célula de `02_silver_demo`, copiado pelo candidato nesta conversa em 2026-10-23. O resultado integral está em [silver-demo-succeeded.json](silver-demo-succeeded.json). Trata-se de transcrição fornecida pelo usuário; o notebook exportado com outputs e consultas independentes às tabelas ainda não foram recebidos.

Resultado informado: **SILVER_PIPELINE_SUCCEEDED**, tentativa `5e3210757d82445cad0bfa0cbe38e9c2`, concluída em 2026-10-23 às 23:57:57 UTC (20:57:57 em São Paulo). Catálogo `workspace`; origem `novarota_case01_bronze`; destino `novarota_case01_silver`; regras `silver_v1`. O modo solicitado foi `incremental`, com escopo efetivo `FULL_DATASET`, conforme a implementação documentada.

| Fonte | Entrada | Aprovadas | Duplicatas | Quarentena |
| --- | ---: | ---: | ---: | ---: |
| clientes_cdc | 14 | 12 | 1 | 1 |
| contas_cdc | 16 | 15 | 0 | 1 |
| cartoes_cdc | 21 | 20 | 0 | 1 |
| transacoes | 54 | 51 | 1 | 2 |
| eventos_risco | 3 | 2 | 0 | 1 |
| estornos | 3 | 2 | 0 | 1 |
| **Total** | **111** | **102** | **2** | **7** |

Cada fonte satisfaz `entrada = aprovadas + duplicatas + quarentena`. As 111 linhas de entrada coincidem com a [execução Bronze informada](bronze-demo-passed.md). A classificação operacional contém 111 linhas e o histórico de avaliações contém 111 nesta primeira tentativa. Os destinos têm 12 eventos/versões de clientes, 15 de contas, 20 de cartões, 51 versões e 50 transações atuais, 2 eventos de risco e 2 estornos.

O JSON inclui nomes, IDs Delta e versões das seis tabelas Bronze fixadas na tentativa. O status é emitido pelo código após sincronizar e reconciliar os destinos. O resumo demonstra o sucesso operacional desta execução e a reconciliação por fonte. Ele não contém linhas de cenários individuais, códigos de quarentena, intervalos SCD2 ou uma tentativa de falha e retomada. Esses critérios permanecem para evidência específica antes de declarar a Silver integralmente validada.
