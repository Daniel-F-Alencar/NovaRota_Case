# Primeira execução Gold concluída

Fontes: JSON da última célula preservado em [gold-demo-succeeded.json](gold-demo-succeeded.json) e export do notebook executado em [notebooks/03_gold_demo.html](notebooks/03_gold_demo.html). O export contém as células concluídas, os outputs tabulares de Gold e a auditoria da execução.

Resultado informado: **GOLD_PIPELINE_SUCCEEDED**, tentativa ddb1e31e37d3426e8b1d97550cfe576f, sobre a Silver 5e3210757d82445cad0bfa0cbe38e9c2. O catálogo foi workspace, o schema de origem novarota_case01_silver, o destino novarota_case01_gold, as regras gold_v1 e a data de corte das features 2026-10-24. A execução terminou em 2026-10-24T00:25:55.037839+00:00.

| Produto | Linhas reconciliadas |
| --- | ---: |
| gold_fato_transacao | 50 |
| gold_dim_cliente | 12 |
| gold_dim_conta | 15 |
| gold_dim_cartao | 20 |
| gold_dim_estabelecimento | 1 |
| gold_cliente_mes | 27 |
| gold_indicadores_risco | 27 |
| gold_features_cliente | 10 |

O resultado identifica IDs e versões Delta das seis entradas Silver; todas estavam na versão 1. O código emite o status de sucesso após aplicar e reconciliar os oito destinos. A saída tabular do notebook também preserva os cenários: estorno parcial 100/30/70, estorno total 80/80/0, transação antes do cancelamento elegível e transações após cancelamento, cancelada e em moeda estrangeira excluídas dos indicadores. A conferência está resumida em [notebook-exports-reviewed.md](notebook-exports-reviewed.md).

O CSV e o Query Profile da consulta `01_anomalias_cliente.sql` agora estão preservados. O perfil comprova uma execução bem-sucedida da versão anterior das janelas analíticas; a versão atual no repositório separa corretamente histórico e quartis por cidade/segmento e precisa de uma nova execução para validar a saída corrigida. Veja [a evidência SQL e as etapas restantes](anomalias-sql-execution.md).
