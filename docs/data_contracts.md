# Contratos das fontes sinteticas

Versao de contrato 1, com extensao 2 para transacoes. Todos os valores recebidos sao strings (ou null em JSON). Datas/decimais passam a ser tipados na Prata. JSON e JSON Lines UTF-8; CSV tem cabecalho, virgula como separador, aspas duplas e LF. Numeros monetarios usam ponto e duas casas, sem float nas regras de negocio. CSV reserva `\N` como null; texto vazio e null permanecem distintos.

## Campos por fonte

| Fonte/formato | Campos do payload |
| --- | --- |
| clientes_cdc / JSONL | id_cliente, cpf, nome, cidade, estado, renda, segmento, data_atualizacao, operacao, id_evento_cdc, sequencia_origem |
| contas_cdc / JSONL | id_conta, id_cliente, tipo_conta, status_conta, data_abertura, data_atualizacao, operacao, id_evento_cdc, sequencia_origem |
| cartoes_cdc / JSONL | id_cartao, id_conta, tipo_cartao, limite, status_cartao, data_atualizacao, operacao, id_evento_cdc, sequencia_origem |
| transacoes / CSV | id_transacao, id_cartao, data_transacao, valor, mcc, estabelecimento, canal, pais, moeda, id_estabelecimento, status_transacao, data_atualizacao, sequencia_origem |
| eventos_risco / CSV | id_evento, id_transacao, tipo_evento, severidade, data_evento |
| estornos / CSV | id_estorno, id_transacao, data_estorno, motivo, valor_estorno, moeda |

Extensoes ao minimo do briefing: CDC recebe identidade e sequencia; transacoes recebem status, atualizacao, sequencia e estabelecimento estavel; estornos recebem valor/moeda. A versao 2 de transacoes acrescenta `dispositivo` em CSV para testar schema rescue. Campos de origem sao planos; nomes reservados do leitor (`_rescued_data`, `_corrupt_record`, `_metadata`, `_file_path`) nao sao usados como campos de negocio pelo gerador.

## Semantica temporal e identidades

Instantes ISO 8601 em UTC (`Z`); `data_abertura` e uma data ISO. Neste case `data_atualizacao` do CDC representa a vigencia de negocio. Ordem da origem: timestamp e sequencia numerica, nunca ordem de chegada dos arquivos. Operacoes CDC `I`, `U` e `D`; mesmo nas delecoes logicas o payload possui a chave e atributos necessarios para auditar o evento.

`id_evento_cdc` identifica uma versao. Repeticao identica e cenario de deduplicacao futura; versoes diferentes da mesma entidade sao historico. Em transacoes, `id_transacao` identifica o negocio e `sequencia_origem` distingue atualizacoes. Contas usam ATIVA/ENCERRADA; cartoes ATIVO/CANCELADO; transacoes APROVADA/PENDENTE/CANCELADA.

CPF e produzido matematicamente a partir de indices ficticios, com digitos verificadores e sem consulta a cadastros. Nomes sao `Cliente Sintetico NNNNNN`. Casos invalidos sao inseridos deliberadamente para exercitar qualidade; nenhum dado foi obtido de pessoas reais.

## Lotes, caminhos e manifestos

Cada lote possui `manifest.json` e `files/`. Caminho relativo de um arquivo:

```text
transacoes/batch_001_initial/schema_v1/event_date=2026-05-01/part_0001.csv
clientes_cdc/batch_001_initial/schema_v1/part_0001.json
```

`event_date` e organizacao da fonte; nao implica particionamento fisico das tabelas Delta. O leitor ignora inferencia de particoes para nao introduzir campos extras na Bronze. Batch e versao sao extraidos do caminho original. Tabelas guardam o caminho completo em `arquivo_origem`.

Manifestos declaram versao, versao do gerador, seed, data de referencia, parametros, cenarios e uma entrada por arquivo: fonte, formato, path relativo, schema_version, rows, bytes e sha256. Caminhos absolutos, traversal, arquivos duplicados e divergencias de hash/tamanho/contagem sao recusados. Arquivos vazios continuam declarados; JSONL pode ter zero bytes e CSV somente cabecalho.

Publicar copia apenas o lote selecionado para landing e finaliza com um manifesto em `published/`. A geracao acontece fora da landing. Repetir a mesma publicacao e permitido; mudar conteudo de arquivo ou manifesto publicado e recusado. Publicacao e ingestao devem ser sequenciais, com uma unica execucao concorrente. Nao ha transacao atomica entre todos os arquivos e o manifesto: uma publicacao incompleta nao autoriza ingestao, e a verificacao da landing identifica arquivos sem manifesto. Retry conclui copias identicas; um arquivo parcial divergente exige recuperacao explicita.

## Cenarios verificaveis

| Lote | Casos fixos |
| --- | --- |
| batch_001_initial | C001 possui A001/A002 e K001/K002; T_PARTIAL=100 com R_PARTIAL=30; T_FULL=80; T_CANCELLED; T_DUP; T_INVALID_AMOUNT=abc; T_FX em USD; T_VERSION pendente. |
| batch_002_incremental | C001-v3; A004 encerrada; K001 cancelado; limite K002 alterado; delete logico K004; T_AFTER_CANCEL; T_VERSION aprovada; R_FULL=80; E_CHARGEBACK. |
| batch_003_late | C001-v2 chega depois de v3; duplicata C001-v1 e T_DUP; CPF invalido; conta/cartao/transacao/evento/estorno com referencia invalida; T_LATE anterior a compras iniciais. |
| batch_004_schema | T_SCHEMA com dispositivo=mobile-sintetico, schema_version=2; demais fontes com arquivos vazios. |

Fixture de expectativas independente em `tests/fixtures/scenario_expectations.json`. Valores líquidos 70/0 para estorno parcial/total são expectativas de negócio para Silver/Gold; a Bronze preserva os registros e não aplica essas regras. A execução Gold foi informada como concluída, mas a confirmação desses valores depende de preservar o output das células de cenário. Gera-se volume adicional sem mudar os cenários. `sample`: 10 clientes válidos iniciais e 40 transações de fundo; `demo`: 100 clientes iniciais e 10000 transações de fundo. Fixtures, atualizações e registros inválidos somam linhas adicionais.

## Hash de linha

SHA-256 UTF-8 de uma lista JSON de objetos `{"key":...,"value":...}`, ordenada por nome do campo, sem espacos extras, com null explicito e Unicode preservado. Incluir todos os campos base do contrato, campos resgatados e `_corrupt_record` quando presente. Excluir apenas o `_file_path` tecnico inserido pelo Auto Loader no rescue; arquivo e metadados de execucao nao fazem parte do hash. Os valores permanecem lexicais: `10.0` e `10.00` possuem hashes distintos. Duplicatas da origem recebem o mesmo hash e permanecem em linhas diferentes na Bronze.

O modulo Python fornece um oracle independente das expressoes Spark. O notebook compara resultados reais para null, vazio, Unicode, caracteres especiais, conteudo resgatado, corrupcao e alteracao de run_id. Depois compara todos os hashes ingeridos com os arquivos originais. Essa verificacao completa e adequada a amostra; em escala deve ser amostrada ou distribuida.
