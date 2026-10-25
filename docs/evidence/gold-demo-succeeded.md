# Primeira execução Gold concluída

Fonte: JSON da última célula de 03_gold_demo, compartilhado pelo candidato nesta conversa em 2026-10-25 e preservado em [gold-demo-succeeded.json](gold-demo-succeeded.json). É uma transcrição fornecida pelo usuário; o export do notebook com outputs e uma consulta independente às tabelas ainda não foram recebidos.

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

O resultado identifica IDs e versões Delta das seis entradas Silver; todas estavam na versão 1. O código emite o status de sucesso após aplicar e reconciliar os oito destinos. Isso comprova a execução operacional informada e a volumetria por produto, sem demonstrar por si só os valores de cada cenário ou o plano da consulta SQL.

O notebook exibe T_PARTIAL, T_FULL, cancelamentos e moeda estrangeira, mas o JSON recebido não contém essas linhas. Para registrar a validação de negócio, falta preservar o notebook executado com os outputs dessas células ou um resultado de consulta equivalente. A consulta 01_anomalias_cliente.sql também ainda precisa de execução e evidência de saída/Query Profile.
