# Executar a demonstracao Bronze

Pre-requisito verificado: amostra `00_workspace_smoke` aprovada no Databricks Free Edition com Auto Loader, Volume UC, Delta, CSV rescue e replay. A demonstracao das seis fontes tambem foi aprovada: ver [resumo fornecido pelo candidato](evidence/bronze-demo-passed.md), com 111 linhas em modo FRESH.

## Importar no Databricks

1. Gerar `dist/novarota_bronze_demo.zip` executando `python scripts/build_artifacts.py` no repositorio local.
2. Em Workspace > Users > sua conta, usar o menu de tres pontos > Import e selecionar esse ZIP. O Databricks pode sugerir uma pasta com o nome do ZIP e timestamp. Manter notebook IPYNB e pacote `novarota/` juntos dentro da pasta importada; o nome dessa pasta externa pode variar.
3. Abrir `01_bronze_demo`. Usar Python e Serverless. Executar **Run all**.
4. Manter `catalog=workspace`, `dataset_id=case01` e `profile=sample` na primeira execucao desta conta. Os nomes sao parametros, nao dependencias fixas. Se o catalogo da conta for outro, ajustar antes de executar setup.
5. Se o pacote nao for localizado, informar em `project_root` o caminho absoluto da pasta que contem o notebook e `novarota/`, por exemplo `/Workspace/Users/<sua-conta>/novarota_case`. A importacao segue o suporte oficial a modulos de workspace; nao depende de `os.getcwd()`.

Se a tentativa anterior retornou `RESOURCE_DOES_NOT_EXIST` para uma pasta `novarota`, usar o ZIP corrigido gerado por `python scripts/build_artifacts.py --name novarota_bronze_demo_v2.zip`. Ele declara explicitamente as cinco pastas antes dos arquivos. Importar novamente a partir da pasta da conta, em vez de dentro de uma pasta de pacote parcialmente importada. O candidato confirmou a reimportacao e a execucao com sucesso em 2026-10-23.

Recursos padrao criados: schema `workspace.novarota_case01_bronze`, schema de operacao `workspace.novarota_ops`, Volume `workspace.novarota_ops.case01_files` e tabela de eventos `workspace.novarota_ops.pipeline_events`. O catalogo precisa permitir criar schemas; o schema ops precisa permitir criar Volume e tabela. Sao usados recursos gerenciados, sem buckets ou credenciais cloud externos.

## O que o notebook executa

Setup repetivel; verificacoes das expressoes Spark; geracao de quatro lotes fora da landing; publicacao e ingestao sequenciais; replay apos lote incremental; atrasos; evolucao CSV; reconciliacao dos payloads; falha esperada de lote nao publicado, com auditoria FAILED; resumo final.

Saida final esperada e informada pelo candidato na execucao documentada: `status=BRONZE_DEMO_PASSED`. Na primeira carga de um dataset vazio, `proof_mode=FRESH`. Reexecutar um dataset ja publicado mostra `RESUME`, preserva dados/checkpoints e pode exibir zero linhas adicionadas nas etapas. Use outro `dataset_id` para uma nova demonstracao inicial; nao apagar checkpoint.

O teste negativo imprime `EXPECTED_FAILURE` e logs de erro como parte do cenario. Ele captura apenas `BatchNotPublishedError`; qualquer outro erro continua interrompendo a demonstracao. Uma linha FAILED nesse run_id e esperada na auditoria. As demais execucoes precisam terminar SUCCEEDED.

## Ingestao e recuperacao

- Uma tabela Delta por fonte, schema lexical explicito e `rescue`; corrupcao de parse e preservada em `_corrupt_record` e gera falha de reconciliacao. Invalidade de negocio, como valor `abc`, continua na Bronze.
- Um checkpoint/schemaLocation por fonte, `AvailableNow`, append Delta, arquivos imutaveis e uma execucao concorrente. Nao usar ProcessingTime no serverless.
- Verificar hashes/tamanhos/contagens dos manifestos antes de ler; conferir contagens por arquivo depois de escrever. Fontes ja reconciliadas geram NOOP registrado em metrics_json (`no_new_rows=true`); nao precisam iniciar outro stream. O replay do checkpoint foi exercitado na amostra inicial.
- Arquivos vazios contam na auditoria mesmo sem linhas Bronze. Os manifests publicados determinam o inventario esperado; arquivos incompletos ou nao declarados impedem ingestao.
- Nunca apagar/recriar checkpoint para corrigir regra de negocio. Se Bronze ja possui linhas e checkpoint desapareceu, a execucao falha antes de acrescentar dados. Recuperar o checkpoint original ou projetar uma reconstrucao em recursos separados com reconciliacao explicita.
- Tabela de dados e auditoria nao formam uma transacao unica. Se uma tentativa falhar depois de gravar, a proxima valida as tabelas e pode retomar como NOOP; STARTED sem finalizacao precisa de investigacao. Falha ao escrever evento de erro nao mascara a excecao original.

## Teste e evidencia

Exportar o notebook executado como IPYNB ou HTML incluindo outputs. Registrar run_ids, proof_mode, catalogo/schema/Volume, totais por fonte, hash do ZIP utilizado e timestamp. A transcricao local da amostra inicial nao substitui esse export. Logs locais e verificacoes de sintaxe tambem nao comprovam execucao Spark/Delta.

As validacoes locais usam unittest. As expressoes Spark e Auto Loader sao verificadas no Databricks real, sem mocks que simulem suporte da plataforma. Limite atual: cota Free Edition, massa pequena e inventario/hashes completos coletados pelo driver para demonstracao. Nao se afirma desempenho em escala com esses numeros.

## Referencias

- [Importacao de notebooks/ZIP](https://docs.databricks.com/aws/en/notebooks/notebook-export-import)
- [Modulos de workspace](https://docs.databricks.com/aws/en/notebooks/share-code)
- [Arquivos em Volumes](https://docs.databricks.com/aws/en/volumes/volume-files)
- [Schema explicito/rescue](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema)
- [Streaming serverless](https://docs.databricks.com/aws/en/compute/serverless/streaming)
