# Executar a Silver

Pré-requisito: seis tabelas Bronze disponíveis. A configuração inicial reutiliza a demonstração Bronze de `case01`, com 111 linhas. A [primeira execução Silver](evidence/silver-demo-succeeded.md) concluiu com sucesso e reconciliou todas as fontes. A retomada após falha e os cenários individuais ainda precisam de evidência específica no Databricks.

## Importação e primeira execução

1. Gerar o pacote com `python scripts/build_artifacts.py --name novarota_silver_demo.zip`.
2. No mesmo workspace Databricks, abrir Workspace > Users > sua conta e importar o ZIP em uma nova pasta. Os diretórios são declarados antes dos arquivos para evitar a falha de pasta pai na importação.
3. Abrir **02_silver_demo**, junto ao pacote atualizado novarota/, usando Python e Serverless. Não é necessário executar novamente 01_bronze_demo sobre case01.
4. Manter catalog=workspace, dataset_id=case01, rule_version=silver_v1, mode=incremental, run_id vazio e datas vazias. Usar Run all.
5. Se o import localizar pacote antigo, encerrar/reiniciar a sessão Python do notebook e usar project_root apontando para a nova pasta importada. O código e os checkpoints Bronze existentes são preservados.
6. Guardar o run_id impresso antes do processamento. A última célula imprime SILVER_PIPELINE_SUCCEEDED somente após a sincronização e reconciliação de todos os destinos.

O status significa sucesso operacional. As tabelas e consultas exibidas permitem revisar cenários de negócio; esse resumo não substitui testes unitários ou uma demonstração específica de falha/retomada.

## Destinos

O schema padrão é `workspace.novarota_case01_silver`, com clientes_eventos, contas_eventos, cartoes_eventos, clientes_scd2, contas_scd2, cartoes_scd2, transacoes_versoes, transacoes_atual, eventos_risco e estornos.

Em `workspace.novarota_ops`: silver_classificacoes (estado atual), silver_avaliacoes (histórico por tentativa), silver_quarentena (view dos rejeitados atuais), silver_execution_state (controle por dataset) e pipeline_events (auditoria compartilhada).

Todos os destinos incluem _dataset_id e _rule_version. O identificador padrão é `workspace.novarota_case01_bronze.novarota_case01_silver`; consumidores devem filtrar esse campo. A separação por schema é o padrão, e a chave adicional protege os MERGEs de datasets que compartilhem destinos.

A versão de regras disponível é silver_v1. O staging guarda também um vínculo imutável com os IDs Delta das seis tabelas Bronze. Recriar essas tabelas exige planejar uma nova Silver em recursos separados; não trocar silenciosamente a origem histórica de um dataset existente.

## O que revisar nos resultados

- Reconciliação por fonte: linhas Bronze = aprovadas + duplicatas + quarentena. Não comparar esse total com a quantidade de versões de uma dimensão.
- C001 apresenta v1, v2 e v3 ordenadas por vigência, embora v2 tenha chegado depois de v3.
- K004 conserva versões anteriores e tombstone lógico; K001 preserva a compra anterior ao cancelamento e sinaliza a posterior como não elegível.
- T_DUP é canônica uma vez; T_VERSION mantém versões e tem estado atual aprovado.
- T_INVALID_AMOUNT, C_BAD e referências ausentes possuem motivos de quarentena.
- T_FX continua USD; T_CANCELLED permanece identificável, sem contribuir como compra aprovada em BRL.
- T_SCHEMA preserva dispositivo=mobile-sintetico.
- R_PARTIAL e R_FULL mantêm 30 e 80 BRL validados, respectivamente. O cálculo líquido pertence à Gold.

Esses critérios exigem consulta às linhas correspondentes. O resumo da primeira execução registra as contagens e o sucesso operacional, sem exibir os valores individuais.

## Replay, atraso e reprocessamento

Com run_id vazio, cada execução inicia nova tentativa e captura as versões Delta correntes das seis fontes. O inventário completo é relido para reavaliar referências e dependentes, inclusive quando não chegam arquivos novos do filho. MERGE mantém o conteúdo canônico estável quando não há mudança. O histórico de avaliações e a auditoria recebem a nova tentativa.

mode=reprocess exige date_from e date_to em YYYY-MM-DD, inclusivas. O resultado informa as linhas nas datas solicitadas. Nesta implementação a reconstrução se expande para **todo o dataset**, preservando histórico nas bordas e dependências; scope=FULL_DATASET fica explícito. Não se alega processamento Silver incremental por linha ou redução de custo pela janela.

## Falha e retomada

Uma única execução concorrente por dataset. Concluir a Bronze antes de iniciar a Silver e evitar ingestão durante a captura das seis versões, que não é uma transação entre tabelas. Não executar dois notebooks para o mesmo dataset ao mesmo tempo. O estado operacional é uma proteção de retomada, não um lock transacional entre processos concorrentes.

Em falha, copiar o ID da tentativa original para o widget run_id e executar novamente com os mesmos parâmetros e a mesma versão de código/regras. Se o erro indicar tentativa incompleta, o próprio erro informa o ID que deve ser retomado. A tentativa conserva input.json com versões/IDs das tabelas, work/, output/ e ready.json em `/Volumes/<catalog>/<ops>/<volume>/silver_staging/<silver_schema>/<run_id>/`.

Antes de ready.json, retry pode reconstruir os arquivos de staging exclusivos da tentativa usando as versões Bronze fixadas. Depois desse marcador, usa os outputs prontos. Eles são Parquet em Volume; tabelas Delta permanecem gerenciadas no catálogo. Somente após todos os MERGEs e reconciliações o controle muda para SUCCEEDED. Um run_id já substituído por tentativa posterior não pode reaplicar snapshot antigo.

Falhas depois de algumas tabelas gravadas podem deixar estado parcial, pois não há transação entre todos os destinos. Consumidores precisam exigir silver_execution_state.status=SUCCEEDED para o dataset; registros pipeline_events sozinhos não bastam. Não consumir Silver durante STARTED/FAILED.

Não apagar controle, staging, tabelas Bronze ou checkpoints para forçar retomada. Se a versão Delta de entrada tiver sido removida por retenção ou a tabela tiver sido recriada, preservar o erro e planejar reconstrução em recursos separados. A recuperação automática não inventa um novo snapshot.

## Evidências e limites

Salvar o JSON final, parâmetros, run_id e export do notebook com outputs. Casos de conflito, pai atrasado, replay, reprocessamento e falha parcial devem ter evidências específicas antes de declarar toda a mudança validada. Nenhum desses resultados foi fabricado nesta etapa.

O staging e a reconciliação completa favorecem a auditabilidade da massa pequena; criam várias operações Spark sequenciais e retêm snapshots de tentativa. Limpeza/retencão desse staging e otimização para escala ficam para operação posterior. Não há coleta das linhas de negócio no driver; apenas estado, metadados de versões e resumos por fonte.

Referências: [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into), [histórico Delta](https://docs.databricks.com/aws/en/delta/history), [funções Spark](https://spark.apache.org/docs/3.5.7/api/python/reference/pyspark.sql/functions.html).
