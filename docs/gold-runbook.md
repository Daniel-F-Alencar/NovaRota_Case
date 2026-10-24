# Executar a Gold

Pré-requisito: executar `02_silver_demo` no mesmo workspace e obter `SILVER_PIPELINE_SUCCEEDED`. A primeira Silver do `case01` foi [informada como concluída](evidence/silver-demo-succeeded.md). A Gold ainda não foi executada no Databricks; as tabelas e métricas abaixo são contratos de implementação, não resultados observados.

## Importar e executar

1. Gerar `dist/novarota_gold_demo.zip` com `python scripts/build_artifacts.py --name novarota_gold_demo.zip`.
2. No mesmo workspace, importar o ZIP em uma nova pasta sob Workspace > Users > sua conta. Não executar novamente os notebooks Bronze/Silver sobre `case01` para esta primeira Gold.
3. Abrir `03_gold_demo` em Python/Serverless. Manter `catalog=workspace` e `dataset_id=case01`. O widget `feature_date` assume a data UTC atual; ela deve ser igual ou posterior à data UTC de conclusão da Silver. Deixar `run_id` vazio para nova tentativa.
4. Usar Run all. Guardar o `run_id` impresso antes do processamento. A última célula exibe a fato dos cenários, cliente-mês, risco, features, auditoria e o JSON final.
5. Se o notebook importar pacote antigo em cache, reiniciar a sessão Python e preencher `project_root` com a pasta `/Workspace/.../novarota_case` recém-importada.

Status esperado: `GOLD_PIPELINE_SUCCEEDED`. Confirmar no output: `T_PARTIAL` bruto 100, estornado 30 e líquido 70; `T_FULL` 80, 80 e zero; `T_CANCELLED`, `T_FX` e `T_AFTER_CANCEL` permanecem na fato com métricas BRL nulas. Esses valores são expectativas a conferir, não evidência de execução.

## Destinos e consulta SQL

Tabelas em `workspace.novarota_case01_gold`: `gold_fato_transacao`, `gold_dim_cliente`, `gold_dim_conta`, `gold_dim_cartao`, `gold_dim_estabelecimento`, `gold_cliente_mes`, `gold_indicadores_risco` e `gold_features_cliente`. Filtrar `_dataset_id='workspace.novarota_case01_bronze.novarota_case01_silver'`. Contratos e grãos estão em [gold-contracts.md](gold-contracts.md).

A consulta [01_anomalias_cliente.sql](../sql/01_anomalias_cliente.sql) usa CTEs encadeadas, ROW_NUMBER, LAG, FIRST_VALUE e NTILE; compara cada cliente com meses anteriores e com cidade/segmento de suas compras. Para executar no SQL Editor, substituir `__CATALOG__` por `workspace`, `__GOLD_SCHEMA__` por `novarota_case01_gold` e `__DATASET_KEY__` pelo identificador acima. A classificação exige pelo menos dois períodos anteriores e três clientes no grupo; a amostra pequena pode resultar em `BASELINE_INSUFICIENTE`, o que é esperado. Exportar plano/Query Profile e outputs se for usar como evidência de execução SQL.

## Retomada e consistência

Uma execução por dataset de cada vez. Não iniciar Silver enquanto Gold captura/publica suas seis tabelas de entrada. A Gold fixa IDs e versões Delta das dimensões, transações, risco e estornos e grava inventário/staging em `/Volumes/<catalog>/<ops>/<volume>/gold_staging/<gold_schema>/<run_id>/`. Falha exige repetir o mesmo `run_id`, `feature_date` e versão do código; a tentativa reutiliza o inventário. Após estágio pronto, reaplica MERGEs e reconcilia todos os destinos.

O controle fica em `workspace.novarota_ops.gold_execution_state` e a auditoria em `pipeline_events`. Consumidores devem exigir Gold SUCCEEDED e conferir `silver_run_id` com o estado Silver atual. Não há transação entre as oito tabelas; STARTED/FAILED bloqueiam consumo. Se a Silver mudar durante Gold, a tentativa falha. Não apagar staging, controle ou fontes para forçar sucesso; conservar erro e recuperar deliberadamente.

O algoritmo reconstrói o **dataset completo** a cada execução; MERGE evita duplicatas e sincroniza linhas retiradas por correção, mas não reduz leitura por partição. Em ambiente maior, avaliar atualização por chaves afetadas, compactação/OPTIMIZE quando suportado, distribuição dos joins e retenção de staging. A amostra não prova escala. Sem PySpark local, a primeira execução no Databricks é o próximo critério de verificação.
