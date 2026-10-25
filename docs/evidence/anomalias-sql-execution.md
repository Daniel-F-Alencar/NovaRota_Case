# Execução da consulta de anomalias

O CSV e o Query Profile recebidos registram uma execução concluída no SQL Warehouse. O perfil tem ID `01f1d084-b11e-1d8c-aaee-496e19470eb7`, status `FINISHED`, 28 linhas produzidas, 118 lidas, 4 arquivos lidos, 3.657 ms de tempo total e resultado não servido do cache. O CSV tem 28 linhas: 25 `BASELINE_INSUFICIENTE`, 2 `NORMAL` e 1 `ANOMALIA`.

Esses arquivos estão preservados em [01_anomalias_cliente_sql.csv](01_anomalias_cliente_sql.csv) e [query-profile_01f1d084-b11e-1d8c-aaee-496e19470eb7.json](query-profile_01f1d084-b11e-1d8c-aaee-496e19470eb7.json). A saída CSV tem a mesma contagem de linhas do perfil.

## Limite dessa evidência

O texto SQL embutido no Query Profile ainda usa as janelas anteriores, que misturavam cidades e segmentos no histórico próprio e misturavam grupos no `NTILE`. O arquivo atual `sql/01_anomalias_cliente.sql` já corrige isso particionando o histórico por cliente, cidade e segmento e os quartis por mês, cidade e segmento. Assim, o CSV e o perfil comprovam que a consulta anterior executou, mas não validam a versão corrigida que está no repositório.

O erro `TABLE_OR_VIEW_NOT_FOUND` com nomes `__CATALOG__` e `__GOLD_SCHEMA__` ocorreu porque os marcadores de modelo foram enviados literalmente ao SQL Warehouse. O arquivo foi configurado com os nomes reais do case: `workspace.novarota_case01_gold` e `_dataset_id = 'workspace.novarota_case01_bronze.novarota_case01_silver'`.

## Para concluir a validação da versão atual

1. No SQL Editor do Databricks, selecione o mesmo workspace e SQL Warehouse que contêm as tabelas do case.
2. Abra `sql/01_anomalias_cliente.sql` no repositório, copie todo o conteúdo e execute sem recolocar os marcadores `__CATALOG__`, `__GOLD_SCHEMA__` ou `__DATASET_KEY__`.
3. Confirme que a consulta termina sem erro e que o filtro usa o dataset `workspace.novarota_case01_bronze.novarota_case01_silver`. O conjunto deve ter 28 grupos cliente/mês/cidade/segmento na amostra atual.
4. Confira a distribuição de `classificacao_comportamento`, selecione algumas linhas de cada classe e valide que `periodos_baseline`, `qt_clientes_pares`, `cidade` e `segmento` são do grupo correto. A classificação pode mudar em relação ao CSV anterior por causa da correção das janelas.
5. Exporte novamente o resultado para CSV e o Query Profile da nova execução. Preserve o novo ID do perfil no nome do arquivo e atualize o resumo desta evidência. Depois disso, a validação SQL estará alinhada com o código versionado.

O candidato também informou que uma consulta separada `COUNT(*)` sobre a fato, filtrada pelo mesmo `_dataset_id`, retornou 50; isso coincide com a saída Gold registrada em [notebook-exports-reviewed.md](notebook-exports-reviewed.md).
