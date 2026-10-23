# Validação local da primeira mudança

Sessão: 2026-10-23. Windows, Python 3.12.14. Execução local, sem Spark/Delta.

Resultados observados:

- `python -m unittest discover -s tests -v`: **29 testes passaram**, cobrindo configuração, cenários, referências inválidas, determinismo, evolução CSV, manifestos, publicação imutável, reconciliação, hash lexical e auditoria/propagação de exceções.
- Temporários do teste foram direcionados para `.test-tmp/` no workspace na última execução. Uma tentativa inicial com o diretório temporário do sandbox falhou por permissão; o teste foi repetido com a permissão necessária e depois concluído no diretório do projeto. Essa falha não foi tratada como sucesso nem motivou relaxamento das asserções.
- `compileall` de src/tests/notebooks/scripts concluído.
- `scripts/build_artifacts.py`: ZIP produzido com 20 entradas; IPYNB com 8 células, todas as células de código analisadas por AST; integridade do ZIP verificada.
- Wheel puro `novarota_lakehouse_case-0.1.0-py3-none-any.whl` construído sem baixar dependências e instalado em `.venv` independente. `python -I -m novarota --version` retornou `0.1.0`.
- Perfis `sample` e `demo` foram gerados localmente; todos os arquivos demo foram verificados contra hash, tamanho e contagem dos manifestos.

Totais observados no perfil demo (incluem fixtures, atualizações e duplicatas):

| Fonte | Linhas |
| --- | ---: |
| clientes_cdc | 104 |
| contas_cdc | 151 |
| cartoes_cdc | 186 |
| transacoes | 10014 |
| eventos_risco | 3 |
| estornos | 3 |

No perfil sample, as contagens totais por lote foram 79, 21, 10 e 1. A massa demo inclui 10000 transações aleatórias de fundo e 14 registros de transação dos cenários fixos, incluindo versões e duplicatas.

Isso comprova geração, publicação local, testes puros e empacotamento. As expressões Spark de hash/metadados, o filesystem do Volume, ingestão das seis fontes e escrita da auditoria no Databricks continuam pendentes da execução do notebook 01_bronze_demo. A amostra inicial aprovada foi documentada separadamente e não é substituída por esses testes locais.

Após a falha de importação reportada pelo candidato, o empacotamento foi corrigido para declarar pastas explicitamente. A suíte passou a 34 testes; ver [registro da correção](import-archive-fix.md). Os resultados de integridade anteriores não demonstravam aceitação pelo importador Databricks.

Atualização posterior: o candidato forneceu o resumo da execução integrada BRONZE_DEMO_PASSED em modo FRESH; ver [evidência remota](bronze-demo-passed.md). As pendências descritas acima representam o estado na data da validação local, antes desse resultado.
